"""Acceptance tests for the severity classifier (Component 10) — specs/10-severity.md.

Individual rules are exercised directly (synthesizing a ``DiffResult`` with the
exact changes a rule's precondition needs) and through :func:`refine`. Rules whose
preconditions depend on the real Layer 1 pipeline (Rule 4's hierarchy widening)
run on hand-crafted fixtures via the orchestrator.
"""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import _severity_rules, orchestrator
from owlcompare.diff._common import Change, DiffResult
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.severity import refine
from owlcompare.loader import load
from owlcompare.severity_config import SeverityConfig, SeverityOverride

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SEV = FIXTURES / "severity"
DIFF = FIXTURES / "diff"

# A real (tiny) snapshot to fill the a/b slots of synthetic DiffResults.
_SNAP = canonicalize(load(str(DIFF / "identical_a.ttl")))


def _change(
    kind: str,
    severity: str,
    *,
    layer: str = "structural",
    subject: str | None = None,
    **details: object,
) -> Change:
    """A Change with a stable change_id stamped into details (as real layers do)."""
    change = Change(
        layer=layer,  # type: ignore[arg-type]
        kind=kind,
        severity=severity,  # type: ignore[arg-type]
        subject=subject,
        summary=f"{kind} {subject or ''}".strip(),
        details=dict(details),
    )
    change.details["change_id"] = SubsumptionRegistry.change_id(change)
    return change


def _result(
    changes: list[Change],
    *,
    registry: SubsumptionRegistry | None = None,
) -> DiffResult:
    metadata = {"subsumption_registry": registry or SubsumptionRegistry()}
    return DiffResult(a=_SNAP, b=_SNAP, changes=tuple(changes), metadata=metadata)


def _run(v1: str, v2: str, **kwargs: object) -> DiffResult:
    a = canonicalize(load(str(SEV / v1)))
    b = canonicalize(load(str(SEV / v2)))
    return orchestrator.run(a, b, **kwargs)  # type: ignore[arg-type]


def _refs_for(result: DiffResult, change_id: str) -> list:
    return [r for r in result.metadata["severity_refinements"] if r.change_id == change_id]


# --------------------------------------------------------------------------- #
# refine() mechanics
# --------------------------------------------------------------------------- #


def test_refine_no_config_no_changes_returns_same_severities():
    change = _change("class_added", "additive", subject="X")
    result = refine(_result([change]))
    assert [c.severity for c in result.changes] == ["additive"]
    assert result.metadata["severity_refinements"] == ()


def test_refine_does_not_mutate_input():
    change = _change("class_added", "additive", subject="X")
    original = _result([change])
    config = SeverityConfig(
        overrides=(SeverityOverride(kind_pattern="class_added", severity="info"),)
    )
    refine(original, config)
    assert original.changes[0].severity == "additive"  # input untouched


def test_refine_records_refinement_in_metadata():
    change = _change("class_added", "additive", subject="X")
    config = SeverityConfig(
        overrides=(SeverityOverride(kind_pattern="class_added", severity="info"),)
    )
    result = refine(_result([change]), config)
    refinements = result.metadata["severity_refinements"]
    assert len(refinements) == 1
    assert refinements[0].refined_severity == "info"


def test_refine_no_refinements_metadata_has_empty_tuple():
    change = _change("class_added", "additive", subject="X")
    result = refine(_result([change]))
    assert result.metadata["severity_refinements"] == ()


# --------------------------------------------------------------------------- #
# Rule 1 — user overrides
# --------------------------------------------------------------------------- #


def test_rule_user_override_wins_over_builtin():
    # Rule 3 (builtin) would demote this restriction_removed to info; a user
    # override to breaking must win instead.
    restriction = _change("restriction_removed", "non_breaking", subject="X", on_property="P")
    prop = _change("object_property_removed", "breaking", subject="P")
    config = SeverityConfig(
        overrides=(SeverityOverride(kind_pattern="restriction_*", severity="breaking"),)
    )
    result = refine(_result([restriction, prop]), config)
    refined = next(c for c in result.changes if c.kind == "restriction_removed")
    assert refined.severity == "breaking"
    ref = _refs_for(result, restriction.details["change_id"])[0]
    assert ref.rule_id == "user-override"


def test_rule_user_override_applied_to_matching_kind():
    change = _change("class_added", "additive", subject="X")
    config = SeverityConfig(
        overrides=(SeverityOverride(kind_pattern="class_added", severity="info"),)
    )
    result = refine(_result([change]), config)
    assert result.changes[0].severity == "info"


def test_rule_user_override_with_subject_pattern_applied():
    match = _change("restriction_removed", "non_breaking", subject="http://x/LegacyTrack")
    miss = _change("restriction_removed", "non_breaking", subject="http://x/Track")
    config = SeverityConfig(
        overrides=(
            SeverityOverride(
                kind_pattern="restriction_*", subject_pattern="*LegacyTrack*", severity="info"
            ),
        )
    )
    result = refine(_result([match, miss]), config)
    by_subject = {c.subject: c.severity for c in result.changes}
    assert by_subject["http://x/LegacyTrack"] == "info"
    assert by_subject["http://x/Track"] == "non_breaking"


def test_rule_user_override_does_not_apply_when_kind_doesnt_match():
    change = _change("class_removed", "breaking", subject="X")
    config = SeverityConfig(
        overrides=(SeverityOverride(kind_pattern="class_added", severity="info"),)
    )
    result = refine(_result([change]), config)
    assert result.changes[0].severity == "breaking"


# --------------------------------------------------------------------------- #
# Rule 2 — annotation on deprecated entity
# --------------------------------------------------------------------------- #


def test_rule_annotation_on_deprecated_demotes_to_info():
    # Severity is forced non-info to make the demotion observable; in the real
    # pipeline annotation changes are already info (see the integration test).
    annotation = _change("annotation_changed", "breaking", subject="X", entity_iri="X")
    deprecated = _change("entity_deprecated", "non_breaking", subject="X", entity_iri="X")
    result = _result([annotation, deprecated])
    ref = _severity_rules.rule_annotation_on_deprecated(annotation, result)
    assert ref is not None
    assert ref.refined_severity == "info"
    assert ref.rule_id == "annotation-on-deprecated"


def test_rule_annotation_on_deprecated_only_applies_if_entity_deprecated_in_same_diff():
    annotation = _change("annotation_changed", "breaking", subject="X", entity_iri="X")
    # entity_deprecated is for a *different* entity → rule abstains.
    deprecated = _change("entity_deprecated", "non_breaking", subject="Y", entity_iri="Y")
    result = _result([annotation, deprecated])
    assert _severity_rules.rule_annotation_on_deprecated(annotation, result) is None


# --------------------------------------------------------------------------- #
# Rule 3 — restriction consequential to property removal
# --------------------------------------------------------------------------- #


def test_rule_restriction_consequential_to_property_removed_demoted_to_info():
    restriction = _change("restriction_removed", "non_breaking", subject="X", on_property="P")
    prop = _change("object_property_removed", "breaking", subject="P")
    result = _result([restriction, prop])
    ref = _severity_rules.rule_restriction_consequential_property_removed(restriction, result)
    assert ref is not None
    assert ref.refined_severity == "info"
    assert ref.rule_id == "restriction-consequential-property-removed"


# --------------------------------------------------------------------------- #
# Rule 5 — reparent + restriction added
# --------------------------------------------------------------------------- #


def test_rule_reparent_with_restriction_added_upgraded_to_breaking():
    reparent = _change("class_reparented", "non_breaking", subject="X")
    restriction = _change("restriction_added", "breaking", subject="X")
    result = _result([reparent, restriction])
    ref = _severity_rules.rule_reparent_with_restriction(reparent, result)
    assert ref is not None
    assert ref.refined_severity == "breaking"
    assert ref.rule_id == "reparent-with-new-restriction"


# --------------------------------------------------------------------------- #
# Rule 6 — subsumed Layer 0
# --------------------------------------------------------------------------- #


def test_rule_subsumed_layer0_changes_severity_info():
    layer0 = _change("triple_removed", "breaking", layer="syntactic", subject="X", subject_iri="X")
    registry = SubsumptionRegistry()
    registry.register("structural:class_removed:abc", [layer0])
    result = _result([layer0], registry=registry)
    ref = _severity_rules.rule_subsumed_layer0(layer0, result)
    assert ref is not None
    assert ref.refined_severity == "info"
    assert ref.rule_id == "subsumed-layer0-info"


def test_rule_subsumed_layer0_unsubsumed_change_untouched():
    layer0 = _change("triple_removed", "breaking", layer="syntactic", subject="X", subject_iri="X")
    result = _result([layer0], registry=SubsumptionRegistry())
    assert _severity_rules.rule_subsumed_layer0(layer0, result) is None


# --------------------------------------------------------------------------- #
# Rule 4 — domain/range widening detected late (the hard one)
# --------------------------------------------------------------------------- #


def test_rule_domain_widening_late_detection_demotes_to_non_breaking():
    # In v1 there is no Track<->Infrastructure relationship, so Component 08
    # defaults the domain swap to breaking. v2 adds Track subClassOf
    # Infrastructure, making the new domain a proven ancestor of the old; Rule 4
    # re-detects the widening and demotes to non_breaking.
    result = _run("domain_widening_late_v1.ttl", "domain_widening_late_v2.ttl")
    domain = next(c for c in result.changes if c.kind == "domain_changed")
    assert domain.severity == "non_breaking"
    ref = _refs_for(result, domain.details["change_id"])
    assert len(ref) == 1
    assert ref[0].rule_id == "dr-widening-detected-late"


# --------------------------------------------------------------------------- #
# Ordering / invariants
# --------------------------------------------------------------------------- #


def test_rule_order_user_override_then_builtin():
    # A change that both a user override and a builtin would touch: the override
    # decides, proving it is consulted before BUILTIN_RULES.
    restriction = _change("restriction_removed", "non_breaking", subject="X", on_property="P")
    prop = _change("object_property_removed", "breaking", subject="P")
    config = SeverityConfig(
        overrides=(SeverityOverride(kind_pattern="restriction_removed", severity="additive"),)
    )
    result = refine(_result([restriction, prop]), config)
    refined = next(c for c in result.changes if c.kind == "restriction_removed")
    assert refined.severity == "additive"  # override, not the builtin's info


def test_rule_first_match_wins_no_double_refinement():
    restriction = _change("restriction_removed", "non_breaking", subject="X", on_property="P")
    prop = _change("object_property_removed", "breaking", subject="P")
    result = refine(_result([restriction, prop]))
    # Exactly one refinement for the restriction change, never two.
    assert len(_refs_for(result, restriction.details["change_id"])) == 1


def test_explain_severity_refinement_carries_rule_id_and_rationale():
    restriction = _change("restriction_removed", "non_breaking", subject="X", on_property="P")
    prop = _change("object_property_removed", "breaking", subject="P")
    result = refine(_result([restriction, prop]))
    ref = _refs_for(result, restriction.details["change_id"])[0]
    assert ref.rule_id == "restriction-consequential-property-removed"
    assert "consequence of property removal" in ref.rationale


def test_refined_diffresult_changes_tuple_not_list_preserves_order():
    changes = [
        _change("class_added", "additive", subject="A"),
        _change("class_removed", "breaking", subject="B"),
        _change("class_added", "additive", subject="C"),
    ]
    result = refine(_result(changes))
    assert isinstance(result.changes, tuple)
    assert [c.subject for c in result.changes] == ["A", "B", "C"]


def test_breaking_remains_breaking_when_no_rule_applies():
    change = _change("class_removed", "breaking", subject="X")
    result = refine(_result([change]))
    assert result.changes[0].severity == "breaking"
    assert result.metadata["severity_refinements"] == ()


def test_exit_code_reflects_refined_severities_not_originals():
    # The only breaking change is demoted to info by a user override → an
    # exit-code computed from the refined changes sees no breaking change.
    change = _change("class_removed", "breaking", subject="X")
    config = SeverityConfig(
        overrides=(SeverityOverride(kind_pattern="class_removed", severity="info"),)
    )
    result = refine(_result([change]), config)
    assert not any(c.severity == "breaking" for c in result.changes)
