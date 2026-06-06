"""Acceptance tests for the annotation diff — specs/09-structural-annotations.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import syntactic
from owlcompare.diff._common import Change
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.structural import annotations, entities, hierarchy, restrictions
from owlcompare.exceptions import DiffError
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ANNO = FIXTURES / "diff" / "annotations"

EX = "http://example.org/"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(ANNO / name)))


def _run(before: str, after: str) -> tuple[list[Change], SubsumptionRegistry, list[Change]]:
    """Run the full Layer 1 pipeline; return (annotation changes, registry, layer0)."""
    a, b = _canon(before), _canon(after)
    layer0 = syntactic.diff(a, b)
    registry = SubsumptionRegistry()
    entities.diff(a, b, layer0, registry)
    hierarchy.diff(a, b, layer0, registry)
    restrictions.diff(a, b, layer0, registry)
    changes = annotations.diff(a, b, layer0, registry)
    return changes, registry, layer0


def _one(changes: list[Change], kind: str) -> Change:
    matches = [c for c in changes if c.kind == kind]
    assert len(matches) == 1, f"expected exactly one {kind}, got {[c.kind for c in changes]}"
    return matches[0]


def test_diff_requires_canonical_inputs():
    a = load(str(ANNO / "label_changed_same_lang_before.ttl"))
    b = load(str(ANNO / "label_changed_same_lang_after.ttl"))
    with pytest.raises(DiffError):
        annotations.diff(a, b, [], SubsumptionRegistry())


def test_diff_identical_inputs_returns_empty():
    changes, _, _ = _run("label_changed_same_lang_before.ttl", "label_changed_same_lang_before.ttl")
    assert changes == []


def test_label_changed_same_lang_emits_annotation_changed():
    changes, _, _ = _run("label_changed_same_lang_before.ttl", "label_changed_same_lang_after.ttl")
    change = _one(changes, "annotation_changed")
    assert change.details["language"] == "en"
    assert change.details["before"]["value"] == "Track"
    assert change.details["after"]["value"] == "Railway Track"


def test_label_changed_different_lang_emits_annotation_changed():
    changes, _, _ = _run(
        "label_changed_different_lang_before.ttl", "label_changed_different_lang_after.ttl"
    )
    change = _one(changes, "annotation_changed")
    assert change.details["language"] == "fr"
    assert change.details["before"]["value"] == "Voie"
    assert change.details["after"]["value"] == "Voie ferrée"


def test_label_added_emits_annotation_added():
    changes, _, _ = _run("label_added_before.ttl", "label_added_after.ttl")
    change = _one(changes, "annotation_added")
    assert change.details["language"] == "de"
    assert change.details["value"] == "Gleis"


def test_label_removed_emits_annotation_removed():
    changes, _, _ = _run("label_removed_before.ttl", "label_removed_after.ttl")
    change = _one(changes, "annotation_removed")
    assert change.details["language"] == "en"
    assert change.details["value"] == "Track"


def test_comment_changed_emits_annotation_changed_with_no_values_in_summary():
    changes, _, _ = _run("comment_changed_before.ttl", "comment_changed_after.ttl")
    change = _one(changes, "annotation_changed")
    # Summary omits the value text (Q1), but details carry the full before/after.
    assert "'" not in change.summary
    assert change.details["before"]["value"] == "A length of railway on which trains run."
    assert change.details["after"]["value"] == "A pair of rails on which railway vehicles run."


def test_multivalue_one_removed_emits_annotation_removed():
    changes, _, _ = _run(
        "multivalue_altLabel_one_removed_before.ttl",
        "multivalue_altLabel_one_removed_after.ttl",
    )
    change = _one(changes, "annotation_removed")
    assert change.details["value"] == "Track Bed"
    # No annotation_changed for multi-value sets (Q2).
    assert [c.kind for c in changes] == ["annotation_removed"]


def test_deprecated_added_emits_entity_deprecated():
    changes, _, _ = _run("deprecated_added_before.ttl", "deprecated_added_after.ttl")
    change = _one(changes, "entity_deprecated")
    assert change.details["entity_iri"] == EX + "Track"


def test_deprecated_added_does_not_emit_annotation_added():
    changes, _, _ = _run("deprecated_added_before.ttl", "deprecated_added_after.ttl")
    assert not any(c.kind == "annotation_added" for c in changes)


def test_deprecated_removed_emits_entity_undeprecated():
    changes, _, _ = _run("deprecated_removed_before.ttl", "deprecated_removed_after.ttl")
    assert _one(changes, "entity_undeprecated").details["entity_iri"] == EX + "Track"


def test_ontology_versioninfo_change_emits_ontology_metadata_changed():
    changes, _, _ = _run(
        "ontology_versioninfo_changed_before.ttl", "ontology_versioninfo_changed_after.ttl"
    )
    change = _one(changes, "ontology_metadata_changed")
    assert change.details["before"]["value"] == "1.0.0"
    assert change.details["after"]["value"] == "2.0.0"


def test_ontology_modified_change_emits_ontology_metadata_changed():
    changes, _, _ = _run(
        "ontology_modified_changed_before.ttl", "ontology_modified_changed_after.ttl"
    )
    change = _one(changes, "ontology_metadata_changed")
    assert change.details["predicate_short"] == "modified"
    assert change.details["before"]["value"] == "2024-01-15"
    assert change.details["after"]["value"] == "2026-05-30"


def test_iri_valued_annotation_change_records_is_iri_value_true():
    changes, _, _ = _run("iri_valued_annotation_before.ttl", "iri_valued_annotation_after.ttl")
    change = _one(changes, "annotation_changed")
    assert change.details["before"]["is_iri_value"] is True
    assert change.details["after"]["is_iri_value"] is True
    assert change.details["before"]["value"] == EX + "related"
    assert change.details["after"]["value"] == EX + "other"


def test_annotation_changed_severity_info():
    changes, _, _ = _run("label_changed_same_lang_before.ttl", "label_changed_same_lang_after.ttl")
    assert _one(changes, "annotation_changed").severity == "info"


def test_entity_deprecated_severity_non_breaking():
    changes, _, _ = _run("deprecated_added_before.ttl", "deprecated_added_after.ttl")
    assert _one(changes, "entity_deprecated").severity == "non_breaking"


def test_entity_undeprecated_severity_info():
    changes, _, _ = _run("deprecated_removed_before.ttl", "deprecated_removed_after.ttl")
    assert _one(changes, "entity_undeprecated").severity == "info"


def test_ontology_metadata_changed_severity_info():
    changes, _, _ = _run(
        "ontology_versioninfo_changed_before.ttl", "ontology_versioninfo_changed_after.ttl"
    )
    assert _one(changes, "ontology_metadata_changed").severity == "info"


def test_diff_skips_entities_with_class_added_in_registry():
    changes, _, _ = _run(
        "annotation_on_class_added_does_not_emit_separate_change_before.ttl",
        "annotation_on_class_added_does_not_emit_separate_change_after.ttl",
    )
    # ex:Platform was added by Component 06; its label is not re-reported here.
    assert not any(c.subject == EX + "Platform" for c in changes)


def test_diff_skips_entities_with_class_removed_in_registry():
    # Reverse direction: ex:Platform is wholly removed; its annotations subsume
    # under Component 06's class_removed, so no standalone annotation change.
    changes, _, _ = _run(
        "annotation_on_class_added_does_not_emit_separate_change_after.ttl",
        "annotation_on_class_added_does_not_emit_separate_change_before.ttl",
    )
    assert not any(c.subject == EX + "Platform" for c in changes)


def test_diff_skips_restriction_urn_subjects():
    changes, _, _ = _run(
        "annotation_on_restriction_urn_skipped_before.ttl",
        "annotation_on_restriction_urn_skipped_after.ttl",
    )
    assert not any("urn:owlcompare:" in (c.subject or "") for c in changes)


def test_diff_subsumes_corresponding_layer0_triples():
    changes, registry, _ = _run(
        "label_changed_different_lang_before.ttl", "label_changed_different_lang_after.ttl"
    )
    change = _one(changes, "annotation_changed")
    subsumes = change.details["subsumes"]
    assert len(subsumes) == 2  # the removed "Voie"@fr and added "Voie ferrée"@fr triples
    for layer0_id in subsumes:
        assert registry.is_explained(layer0_id)


def test_diff_subsumes_list_is_sorted():
    # DD-021: a changed annotation subsumes the removed + added triple; sorted.
    changes, _, _ = _run(
        "label_changed_different_lang_before.ttl", "label_changed_different_lang_after.ttl"
    )
    subsumes = _one(changes, "annotation_changed").details["subsumes"]
    assert len(subsumes) >= 2  # a meaningful order check needs >1 element
    assert subsumes == sorted(subsumes)


def test_change_id_present_in_details():
    changes, _, _ = _run("label_changed_same_lang_before.ttl", "label_changed_same_lang_after.ttl")
    assert all("change_id" in c.details for c in changes)


def test_summary_uses_prefixed_iris_when_known():
    changes, _, _ = _run("label_changed_same_lang_before.ttl", "label_changed_same_lang_after.ttl")
    summary = _one(changes, "annotation_changed").summary
    assert "ex:Track" in summary
    assert EX + "Track" not in summary


def test_summary_label_includes_language_in_parens():
    changes, _, _ = _run(
        "label_changed_different_lang_before.ttl", "label_changed_different_lang_after.ttl"
    )
    assert "(fr)" in _one(changes, "annotation_changed").summary


def test_summary_label_no_language_omits_paren():
    changes, _, _ = _run("iri_valued_annotation_before.ttl", "iri_valued_annotation_after.ttl")
    summary = _one(changes, "annotation_changed").summary
    assert "(" not in summary


def test_summary_comment_omits_value_text():
    changes, _, _ = _run("comment_changed_before.ttl", "comment_changed_after.ttl")
    summary = _one(changes, "annotation_changed").summary
    assert "railway" not in summary
    assert summary.startswith("Comment changed on ex:Track")


def test_summary_arrow_notation_for_changed():
    changes, _, _ = _run("label_changed_same_lang_before.ttl", "label_changed_same_lang_after.ttl")
    assert "'Track' → 'Railway Track'" in _one(changes, "annotation_changed").summary


def test_ordering_groups_kind_then_subject_then_predicate_then_language():
    # The flagship era_annotations pair emits a mix of kinds; assert the kind
    # groups land in the documented order.
    changes, _, _ = _run("era_annotations_v1.ttl", "era_annotations_v2.ttl")
    ranks = {
        "annotation_changed": 0,
        "annotation_added": 1,
        "annotation_removed": 2,
        "entity_deprecated": 3,
        "entity_undeprecated": 4,
        "ontology_metadata_changed": 5,
    }
    observed = [ranks[c.kind] for c in changes]
    assert observed == sorted(observed)
