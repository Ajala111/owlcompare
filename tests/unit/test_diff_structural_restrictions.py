"""Acceptance tests for the restriction diff — specs/08-structural-restrictions.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import syntactic
from owlcompare.diff._common import Change
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.structural import entities, hierarchy, restrictions
from owlcompare.exceptions import DiffError
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
RESTR = FIXTURES / "diff" / "restrictions"

EX = "http://example.org/"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(RESTR / name)))


def _run(before: str, after: str) -> tuple[list[Change], SubsumptionRegistry, list[Change]]:
    """Run the full Layer 1 pipeline; return (restriction changes, registry, layer0)."""
    a, b = _canon(before), _canon(after)
    layer0 = syntactic.diff(a, b)
    registry = SubsumptionRegistry()
    entities.diff(a, b, layer0, registry)
    hierarchy.diff(a, b, layer0, registry)
    changes = restrictions.diff(a, b, layer0, registry)
    return changes, registry, layer0


def _one(changes: list[Change], kind: str) -> Change:
    matches = [c for c in changes if c.kind == kind]
    assert len(matches) == 1, f"expected exactly one {kind}, got {[c.kind for c in changes]}"
    return matches[0]


def test_diff_requires_canonical_inputs():
    a = load(str(RESTR / "cardinality_tightened_before.ttl"))
    b = load(str(RESTR / "cardinality_tightened_after.ttl"))
    with pytest.raises(DiffError):
        restrictions.diff(a, b, [], SubsumptionRegistry())


def test_diff_identical_inputs_returns_empty():
    changes, _, _ = _run("cardinality_tightened_before.ttl", "cardinality_tightened_before.ttl")
    assert changes == []


def test_cardinality_tightened_severity_breaking():
    changes, _, _ = _run("cardinality_tightened_before.ttl", "cardinality_tightened_after.ttl")
    assert _one(changes, "restriction_changed").severity == "breaking"


def test_cardinality_relaxed_severity_non_breaking():
    changes, _, _ = _run("cardinality_relaxed_before.ttl", "cardinality_relaxed_after.ttl")
    assert _one(changes, "restriction_changed").severity == "non_breaking"


def test_cardinality_kind_change_emits_restriction_changed():
    changes, _, _ = _run("cardinality_kind_change_before.ttl", "cardinality_kind_change_after.ttl")
    change = _one(changes, "restriction_changed")
    assert change.details["before"]["kind"] == "min_cardinality"
    assert change.details["after"]["kind"] == "exact_cardinality"


def test_someValues_to_allValues_severity_breaking():
    changes, _, _ = _run("someValues_to_allValues_before.ttl", "someValues_to_allValues_after.ttl")
    assert _one(changes, "restriction_changed").severity == "breaking"


def test_someValues_filler_narrowed_severity_breaking():
    changes, _, _ = _run(
        "someValues_filler_narrowed_before.ttl", "someValues_filler_narrowed_after.ttl"
    )
    assert _one(changes, "restriction_changed").severity == "breaking"


def test_someValues_filler_widened_severity_non_breaking():
    changes, _, _ = _run(
        "someValues_filler_widened_before.ttl", "someValues_filler_widened_after.ttl"
    )
    assert _one(changes, "restriction_changed").severity == "non_breaking"


def test_restriction_added_severity_breaking():
    changes, _, _ = _run("restriction_added_before.ttl", "restriction_added_after.ttl")
    assert _one(changes, "restriction_added").severity == "breaking"


def test_restriction_removed_severity_non_breaking():
    changes, _, _ = _run("restriction_removed_before.ttl", "restriction_removed_after.ttl")
    removed = _one(changes, "restriction_removed")
    assert removed.severity == "non_breaking"
    # The retained someValuesFrom restriction must not produce a change.
    assert [c.kind for c in changes] == ["restriction_removed"]


def test_multiple_restrictions_one_changed_emits_one_change():
    changes, _, _ = _run(
        "multiple_restrictions_one_changed_before.ttl",
        "multiple_restrictions_one_changed_after.ttl",
    )
    assert [c.kind for c in changes] == ["restriction_changed"]


def test_qualified_cardinality_decoded_correctly():
    changes, _, _ = _run("qualified_cardinality_before.ttl", "qualified_cardinality_after.ttl")
    change = _one(changes, "restriction_changed")
    assert change.details["before"]["kind"] == "min_qualified_cardinality"
    assert change.details["before"]["filler"] == EX + "Gauge"
    assert change.details["before"]["cardinality"] == 1
    assert change.details["after"]["cardinality"] == 2


def test_domain_swap_emits_domain_changed():
    changes, _, _ = _run("domain_swap_before.ttl", "domain_swap_after.ttl")
    change = _one(changes, "domain_changed")
    assert change.severity == "breaking"
    assert change.details["before"] == EX + "Signal"
    assert change.details["after"] == EX + "Asset"


def test_domain_extended_emits_domain_added():
    changes, _, _ = _run("domain_extended_before.ttl", "domain_extended_after.ttl")
    change = _one(changes, "domain_added")
    assert change.severity == "non_breaking"
    assert change.details["value"] == EX + "Platform"


def test_range_removed_emits_range_removed():
    changes, _, _ = _run("range_removed_before.ttl", "range_removed_after.ttl")
    change = _one(changes, "range_removed")
    assert change.severity == "non_breaking"
    assert change.details["value"] == EX + "Axle"


def test_equivalent_class_added_emits_change():
    changes, _, _ = _run("equivalent_class_added_before.ttl", "equivalent_class_added_after.ttl")
    change = _one(changes, "equivalent_class_added")
    assert change.severity == "non_breaking"
    assert change.details["entity_iri"] == EX + "A"
    assert change.details["other_iri"] == EX + "B"


def test_disjoint_with_added_severity_breaking():
    changes, _, _ = _run("disjoint_with_added_before.ttl", "disjoint_with_added_after.ttl")
    change = _one(changes, "disjoint_added")
    assert change.severity == "breaking"
    assert {change.details["entity_iri"], change.details["other_iri"]} == {
        EX + "Track",
        EX + "Person",
    }


def test_complement_set_emits_change_with_before_after():
    changes, _, _ = _run("complement_set_before.ttl", "complement_set_after.ttl")
    change = _one(changes, "complement_set")
    assert change.severity == "breaking"
    assert change.details["before"] is None
    assert change.details["after"] == EX + "Vehicle"


def test_nested_expression_emits_complex_class_expression_changed():
    changes, _, _ = _run(
        "nested_expression_change_before.ttl", "nested_expression_change_after.ttl"
    )
    change = _one(changes, "complex_class_expression_changed")
    assert change.severity == "breaking"
    assert change.details["entity_iri"] == EX + "Track"
    assert change.details["depth"] >= 2


def test_class_removed_does_not_emit_separate_restriction_change():
    changes, registry, layer0 = _run(
        "class_with_restriction_removed_entirely_before.ttl",
        "class_with_restriction_removed_entirely_after.ttl",
    )
    # No standalone restriction change for the deleted class.
    assert not any(c.kind.startswith("restriction_") for c in changes)
    # The restriction triples are subsumed under Component 06's class_removed.
    restriction_triples = [
        c for c in layer0 if "urn:owlcompare:restriction:" in (c.details.get("subject") or "")
    ]
    assert restriction_triples
    for triple in restriction_triples:
        assert registry.is_explained(triple.details["change_id"])


def test_restriction_change_subsumes_corresponding_layer0_triples():
    changes, registry, _ = _run(
        "cardinality_tightened_before.ttl", "cardinality_tightened_after.ttl"
    )
    change = _one(changes, "restriction_changed")
    subsumes = change.details["subsumes"]
    assert subsumes  # both the removed and added URN triples + the subClassOf edges
    for layer0_id in subsumes:
        assert registry.is_explained(layer0_id)


def test_change_id_present_in_details():
    changes, _, _ = _run("cardinality_tightened_before.ttl", "cardinality_tightened_after.ttl")
    assert all("change_id" in c.details for c in changes)


def test_summary_uses_prefixed_iris_when_known():
    changes, _, _ = _run("cardinality_tightened_before.ttl", "cardinality_tightened_after.ttl")
    summary = _one(changes, "restriction_changed").summary
    assert "ex:Track" in summary
    assert EX + "Track" not in summary


def test_summary_cardinality_change_uses_arrow_notation():
    changes, _, _ = _run("cardinality_tightened_before.ttl", "cardinality_tightened_after.ttl")
    assert "max 5 → max 3" in _one(changes, "restriction_changed").summary


def test_summary_someValues_kind_change_readable():
    changes, _, _ = _run("someValues_to_allValues_before.ttl", "someValues_to_allValues_after.ttl")
    summary = _one(changes, "restriction_changed").summary
    assert "some ex:Gauge → all ex:Gauge" in summary


def test_ordering_groups_kind_then_subject():
    # era_restrictions emits a changed, an added and a removed restriction; the
    # changed must sort before the added, which sorts before the removed.
    changes, _, _ = _run("era_restrictions_v1.ttl", "era_restrictions_v2.ttl")
    kinds = [c.kind for c in changes]
    assert kinds == ["restriction_changed", "restriction_added", "restriction_removed"]
