"""Acceptance tests for Layer 1 hierarchy diff — specs/07-structural-hierarchy.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import syntactic
from owlcompare.diff._common import Change
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.structural import entities, hierarchy
from owlcompare.exceptions import DiffError
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
HIER = FIXTURES / "diff" / "hierarchy"

# Ordering rank mirrors hierarchy._KIND_RANK for the ordering acceptance test.
_KIND_RANK = {
    "class_reparented": 0,
    "property_reparented": 1,
    "class_parent_added": 2,
    "property_parent_added": 3,
    "class_parent_removed": 4,
    "property_parent_removed": 5,
    "class_hierarchy_cycle_introduced": 6,
}


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(HIER / name)))


def _hier(before: str, after: str) -> list[Change]:
    """Run Layer 0 + entities + hierarchy (sharing a registry); return hierarchy changes."""
    return _hier_full(before, after)[0]


def _hier_full(
    before: str, after: str
) -> tuple[list[Change], SubsumptionRegistry, list[Change], list[Change]]:
    """Return (hierarchy_changes, registry, layer0, entity_changes)."""
    a, b = _canon(before), _canon(after)
    registry = SubsumptionRegistry()
    layer0 = syntactic.diff(a, b)
    entity_changes = entities.diff(a, b, layer0, registry)
    hierarchy_changes = hierarchy.diff(a, b, layer0, registry)
    return hierarchy_changes, registry, layer0, entity_changes


def test_diff_requires_canonical_inputs():
    a = load(str(HIER / "parent_added_before.ttl"))
    b = load(str(HIER / "parent_added_after.ttl"))
    with pytest.raises(DiffError):
        hierarchy.diff(a, b, [], SubsumptionRegistry())


def test_diff_identical_inputs_returns_empty():
    snap = _canon("parent_added_before.ttl")
    assert hierarchy.diff(snap, snap, [], SubsumptionRegistry()) == []


def test_class_parent_added_emits_correct_change():
    changes = _hier("parent_added_before.ttl", "parent_added_after.ttl")
    added = [c for c in changes if c.kind == "class_parent_added"]
    assert len(added) == 1
    assert added[0].subject == "http://example.org/Dog"
    assert added[0].details["parent_iri"] == "http://example.org/Animal"
    assert added[0].severity == "additive"


def test_class_parent_added_when_entity_is_newly_added_does_not_emit_hierarchy_change():
    # ex:Child is newly added with a parent; subsumption is Component 06's job.
    changes = _hier("added_class_with_parent_before.ttl", "added_class_with_parent_after.ttl")
    assert [c for c in changes if c.subject == "http://example.org/Child"] == []


def test_class_parent_removed_when_other_parents_remain_severity_non_breaking():
    changes = _hier(
        "parent_removed_keeps_others_before.ttl", "parent_removed_keeps_others_after.ttl"
    )
    removed = [c for c in changes if c.kind == "class_parent_removed"]
    assert len(removed) == 1
    assert removed[0].severity == "non_breaking"


def test_class_parent_removed_when_orphaned_severity_breaking():
    changes = _hier("parent_removed_orphan_before.ttl", "parent_removed_orphan_after.ttl")
    removed = [c for c in changes if c.kind == "class_parent_removed"]
    assert len(removed) == 1
    assert removed[0].severity == "breaking"


def test_class_reparented_single_to_single_generalization():
    changes = _hier(
        "simple_reparent_generalization_before.ttl", "simple_reparent_generalization_after.ttl"
    )
    reparented = [c for c in changes if c.kind == "class_reparented"]
    assert len(reparented) == 1
    assert reparented[0].details["direction"] == "generalization"


def test_class_reparented_single_to_single_specialization():
    changes = _hier(
        "simple_reparent_specialization_before.ttl", "simple_reparent_specialization_after.ttl"
    )
    reparented = [c for c in changes if c.kind == "class_reparented"]
    assert len(reparented) == 1
    assert reparented[0].details["direction"] == "specialization"


def test_class_reparented_single_to_single_lateral():
    changes = _hier("simple_reparent_lateral_before.ttl", "simple_reparent_lateral_after.ttl")
    reparented = [c for c in changes if c.kind == "class_reparented"]
    assert len(reparented) == 1
    assert reparented[0].details["direction"] == "lateral"


def test_class_reparented_severity_generalization_non_breaking():
    changes = _hier(
        "simple_reparent_generalization_before.ttl", "simple_reparent_generalization_after.ttl"
    )
    assert changes[0].severity == "non_breaking"


def test_class_reparented_severity_specialization_breaking():
    changes = _hier(
        "simple_reparent_specialization_before.ttl", "simple_reparent_specialization_after.ttl"
    )
    assert changes[0].severity == "breaking"


def test_class_reparented_severity_lateral_breaking():
    changes = _hier("simple_reparent_lateral_before.ttl", "simple_reparent_lateral_after.ttl")
    assert changes[0].severity == "breaking"


def test_class_reparented_multi_parent_uses_brace_notation():
    changes = _hier("multi_parent_reparent_before.ttl", "multi_parent_reparent_after.ttl")
    reparented = [c for c in changes if c.kind == "class_reparented"]
    assert len(reparented) == 1
    assert "{" in reparented[0].summary and "}" in reparented[0].summary
    assert reparented[0].details["direction"] == "lateral"


def test_class_reparented_emits_single_change_not_add_plus_remove():
    changes = _hier(
        "simple_reparent_generalization_before.ttl", "simple_reparent_generalization_after.ttl"
    )
    for_a = [c for c in changes if c.subject == "http://example.org/A"]
    assert len(for_a) == 1
    assert for_a[0].kind == "class_reparented"
    kinds = {c.kind for c in changes}
    assert "class_parent_added" not in kinds
    assert "class_parent_removed" not in kinds


def test_property_parent_added_emits_correct_kind():
    changes = _hier("property_parent_added_before.ttl", "property_parent_added_after.ttl")
    assert any(c.kind == "property_parent_added" for c in changes)


def test_property_reparented_emits_correct_kind():
    changes = _hier("property_reparent_before.ttl", "property_reparent_after.ttl")
    assert any(c.kind == "property_reparented" for c in changes)


def test_synthetic_restriction_parent_does_not_emit_hierarchy_change():
    changes = _hier(
        "synthetic_restriction_parent_before.ttl", "synthetic_restriction_parent_after.ttl"
    )
    assert not any(c.subject == "http://example.org/Door" for c in changes)


def test_cycle_introduced_emits_cycle_change_with_path():
    changes = _hier("cycle_introduced_before.ttl", "cycle_introduced_after.ttl")
    cycles = [c for c in changes if c.kind == "class_hierarchy_cycle_introduced"]
    # Q3: one change per entity on the cycle (A, B, C) sharing the same path.
    assert len(cycles) == 3
    assert {c.subject for c in cycles} == {
        "http://example.org/A",
        "http://example.org/B",
        "http://example.org/C",
    }
    path = cycles[0].details["path"]
    assert path[0] == path[-1]  # closed loop
    assert set(path[:-1]) == {
        "http://example.org/A",
        "http://example.org/B",
        "http://example.org/C",
    }


def test_cycle_self_loop_emits_cycle_change():
    changes = _hier("self_loop_before.ttl", "self_loop_after.ttl")
    cycles = [c for c in changes if c.kind == "class_hierarchy_cycle_introduced"]
    assert len(cycles) == 1
    assert cycles[0].details["path"] == ["http://example.org/A", "http://example.org/A"]


def test_preexisting_cycle_in_b_not_flagged():
    changes = _hier("preexisting_cycle_before.ttl", "preexisting_cycle_after.ttl")
    assert not any(c.kind == "class_hierarchy_cycle_introduced" for c in changes)


def test_change_subsumes_corresponding_layer0_triples():
    changes, registry, layer0, _ = _hier_full("parent_added_before.ttl", "parent_added_after.ttl")
    added = next(c for c in changes if c.kind == "class_parent_added")
    assert len(added.details["subsumes"]) == 1
    # The subsumed Layer 0 change is the subClassOf triple addition.
    subclass_added = [
        c
        for c in layer0
        if c.subject == "http://example.org/Dog"
        and c.details.get("predicate_iri") == "http://www.w3.org/2000/01/rdf-schema#subClassOf"
    ]
    assert len(subclass_added) == 1
    assert registry.is_explained(subclass_added[0].details["change_id"])


def test_change_id_present_in_details():
    changes = _hier("parent_added_before.ttl", "parent_added_after.ttl")
    assert changes[0].details["change_id"].startswith("structural:class_parent_added:")


def test_reparent_subsumes_list_is_sorted():
    # DD-021: a reparent subsumes the removed + added edge; the list must be sorted.
    changes = _hier(
        "simple_reparent_generalization_before.ttl", "simple_reparent_generalization_after.ttl"
    )
    reparented = next(c for c in changes if c.kind == "class_reparented")
    subsumes = reparented.details["subsumes"]
    assert len(subsumes) >= 2  # a meaningful order check needs >1 element
    assert subsumes == sorted(subsumes)


def test_summary_uses_prefixed_iris_when_known():
    changes = _hier(
        "simple_reparent_generalization_before.ttl", "simple_reparent_generalization_after.ttl"
    )
    summary = changes[0].summary
    assert "ex:A" in summary
    assert "http://example.org/A" not in summary


def test_summary_includes_direction_for_reparent():
    changes = _hier(
        "simple_reparent_generalization_before.ttl", "simple_reparent_generalization_after.ttl"
    )
    assert changes[0].summary.endswith("(generalization)")


def test_summary_multi_parent_uses_braces():
    changes = _hier("multi_parent_reparent_before.ttl", "multi_parent_reparent_after.ttl")
    summary = changes[0].summary
    assert "{ex:B, ex:C}" in summary
    assert "{ex:D, ex:E}" in summary


def test_ordering_groups_kinds_then_subjects():
    changes = _hier("cycle_introduced_before.ttl", "cycle_introduced_after.ttl")
    keys = [(_KIND_RANK[c.kind], c.subject or "") for c in changes]
    assert keys == sorted(keys)


def test_hierarchy_diff_does_not_duplicate_entity_diff_subsumption():
    # ex:Child is newly added AND has a subClassOf edge. Component 06 owns the
    # entity; Component 07 must not emit a parent-added nor override the existing
    # class_added subsumption of ex:Child's rdf:type triple.
    hierarchy_changes, registry, layer0, entity_changes = _hier_full(
        "added_class_with_parent_before.ttl", "added_class_with_parent_after.ttl"
    )
    class_added = next(
        c
        for c in entity_changes
        if c.kind == "class_added" and c.subject == "http://example.org/Child"
    )
    class_added_id = class_added.details["change_id"]
    rdf_type = next(
        c
        for c in layer0
        if c.subject == "http://example.org/Child"
        and c.details.get("predicate_iri") == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    )
    # The entity's rdf:type stays explained by class_added, not by hierarchy.
    assert class_added_id in registry.explainers(rdf_type.details["change_id"])
    assert not any(c.subject == "http://example.org/Child" for c in hierarchy_changes)
    # The subClassOf triple is deferred to the same class_added change.
    subclass = next(
        c
        for c in layer0
        if c.subject == "http://example.org/Child"
        and c.details.get("predicate_iri") == "http://www.w3.org/2000/01/rdf-schema#subClassOf"
    )
    assert registry.explainers(subclass.details["change_id"]) == (class_added_id,)
