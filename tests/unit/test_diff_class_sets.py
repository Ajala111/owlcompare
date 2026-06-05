"""Acceptance tests for the class-set union/intersection diff — specs/12.5 § Part 2."""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import syntactic
from owlcompare.diff._common import Change
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.structural import class_sets, entities, hierarchy, restrictions
from owlcompare.exceptions import DiffError
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ANON = FIXTURES / "anonstruct"

ERA = "http://data.europa.eu/949/"
TIME = "http://www.w3.org/2006/time#"
XSD = "http://www.w3.org/2001/XMLSchema#"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(ANON / name)))


def _run(before: str, after: str) -> tuple[list[Change], SubsumptionRegistry, list[Change]]:
    """Run the Layer 1 pipeline through class_sets; return (changes, registry, layer0)."""
    a, b = _canon(before), _canon(after)
    layer0 = syntactic.diff(a, b)
    registry = SubsumptionRegistry()
    entities.diff(a, b, layer0, registry)
    hierarchy.diff(a, b, layer0, registry)
    restrictions.diff(a, b, layer0, registry)
    changes = class_sets.diff(a, b, layer0, registry)
    return changes, registry, layer0


def _pair(stem: str) -> tuple[list[Change], SubsumptionRegistry, list[Change]]:
    return _run(f"{stem}_v1.ttl", f"{stem}_v2.ttl")


def _one(changes: list[Change], kind: str) -> Change:
    matches = [c for c in changes if c.kind == kind]
    assert len(matches) == 1, f"expected one {kind}, got {[c.kind for c in changes]}"
    return matches[0]


def _unexplained(registry: SubsumptionRegistry, layer0: list[Change]) -> list[Change]:
    return [c for c in layer0 if not registry.is_explained(c.details.get("change_id", ""))]


def test_diff_requires_canonical_inputs():
    a = load(str(ANON / "domain_union_member_added_v1.ttl"))
    b = load(str(ANON / "domain_union_member_added_v2.ttl"))
    with pytest.raises(DiffError):
        class_sets.diff(a, b, [], SubsumptionRegistry())


def test_diff_identical_inputs_returns_empty():
    changes, _, _ = _run("domain_union_member_added_v1.ttl", "domain_union_member_added_v1.ttl")
    assert changes == []


def test_domain_union_member_added_emits_union_added():
    changes, _, _ = _pair("domain_union_member_added")
    change = _one(changes, "domain_union_added")
    assert change.details["added_members"] == [ERA + "VehicleTypeOriginal"]
    assert change.details["removed_members"] == []


def test_domain_union_member_removed_emits_union_removed():
    changes, _, _ = _pair("domain_union_member_removed")
    change = _one(changes, "domain_union_removed")
    assert change.details["removed_members"] == [ERA + "VehicleTypeOriginal"]


def test_domain_union_mixed_emits_union_changed():
    changes, _, _ = _pair("domain_union_mixed")
    change = _one(changes, "domain_union_changed")
    assert change.details["added_members"] == [ERA + "VehicleTypeOriginal"]
    assert change.details["removed_members"] == [ERA + "VehicleTypeConfigParameterSet"]


def test_domain_union_flattened_emits_correct_summary():
    changes, _, _ = _pair("domain_union_flattened")
    change = _one(changes, "domain_union_removed")
    assert change.details["shape_change"] == "flattened"
    assert "simplified" in change.summary and "only" in change.summary


def test_domain_union_unflattened_emits_correct_summary():
    changes, _, _ = _pair("domain_union_unflattened")
    change = _one(changes, "domain_union_added")
    assert change.details["shape_change"] == "unflattened"
    assert "extended" in change.summary and "union of" in change.summary


def test_range_union_classes_changed():
    changes, _, _ = _pair("range_union_classes_changed")
    change = _one(changes, "range_union_changed")
    assert change.details["added_members"] == [ERA + "OperationalPoint"]
    assert change.details["removed_members"] == [ERA + "BorderPoint"]


def test_range_union_datatypes_changed():
    changes, _, _ = _pair("range_union_datatypes_changed")
    change = _one(changes, "range_union_removed")
    assert change.details["removed_members"] == [XSD + "integer"]


def test_subclass_union_member_added():
    changes, _, _ = _pair("subclass_union_member_added")
    change = _one(changes, "subclass_union_added")
    assert change.details["added_members"] == [TIME + "TemporalScenario"]


def test_subclass_union_flattened():
    changes, _, _ = _pair("subclass_union_flattened")
    change = _one(changes, "subclass_union_removed")
    assert change.details["shape_change"] == "flattened"
    assert change.details["removed_members"] == [TIME + "TemporalScenario"]


def test_equivalent_class_union_changed():
    changes, _, _ = _pair("equivalent_class_union_changed")
    change = _one(changes, "equivalent_class_union_changed")
    assert change.details["added_members"] == [ERA + "Corridor"]
    assert change.details["removed_members"] == [ERA + "Segment"]


def test_severity_union_added_non_breaking_for_domain():
    changes, _, _ = _pair("domain_union_member_added")
    assert _one(changes, "domain_union_added").severity == "non_breaking"


def test_severity_union_removed_breaking_for_domain():
    changes, _, _ = _pair("domain_union_member_removed")
    assert _one(changes, "domain_union_removed").severity == "breaking"


def test_severity_equivalent_class_union_always_breaking():
    changes, _, _ = _pair("equivalent_class_union_changed")
    assert _one(changes, "equivalent_class_union_changed").severity == "breaking"


def test_severity_intersection_member_added_breaking():
    # Q2: adding to an intersection narrows → breaking (the inverse of a union).
    changes, _, _ = _pair("domain_intersection_member_added")
    assert _one(changes, "domain_union_added").severity == "breaking"


def test_severity_intersection_member_removed_non_breaking():
    # Q2: removing from an intersection broadens → non_breaking.
    changes, _, _ = _pair("domain_intersection_member_removed")
    assert _one(changes, "domain_union_removed").severity == "non_breaking"


_OWL = "http://www.w3.org/2002/07/owl#"
_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def test_subsumes_layer0_unionOf_triples():
    _, registry, layer0 = _pair("domain_union_member_added")
    union_triples = [c for c in layer0 if c.details.get("predicate_iri") == _OWL + "unionOf"]
    assert union_triples
    assert all(registry.is_explained(c.details["change_id"]) for c in union_triples)


def test_subsumes_layer0_list_cell_triples():
    _, registry, layer0 = _pair("domain_union_member_added")
    cells = [c for c in layer0 if c.details.get("predicate_iri") in (_RDF + "first", _RDF + "rest")]
    assert cells
    assert all(registry.is_explained(c.details["change_id"]) for c in cells)


def test_subsumes_layer0_anonymous_class_type_triple():
    # Every reified-structure triple — including the urn rdf:type owl:Class type
    # triple — is subsumed, so nothing is left unexplained.
    _, registry, layer0 = _pair("domain_union_member_added")
    assert _unexplained(registry, layer0) == []


def test_change_id_present_in_details():
    changes, _, _ = _pair("domain_union_member_added")
    assert all("change_id" in c.details for c in changes)


def test_summary_uses_prefixed_iris():
    changes, _, _ = _pair("domain_union_member_added")
    summary = _one(changes, "domain_union_added").summary
    assert "era:" in summary
    assert "http://" not in summary


def test_summary_added_member_uses_plus_notation():
    changes, _, _ = _pair("domain_union_member_added")
    assert "+ era:VehicleTypeOriginal" in _one(changes, "domain_union_added").summary


def test_summary_removed_member_uses_minus_notation():
    changes, _, _ = _pair("domain_union_member_removed")
    assert "- era:VehicleTypeOriginal" in _one(changes, "domain_union_removed").summary
