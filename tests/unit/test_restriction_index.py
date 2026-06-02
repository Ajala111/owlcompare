"""Acceptance tests for the restriction index — specs/08-structural-restrictions.md § Step 1."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff.structural._restriction_index import (
    DecodedRestriction,
    RestrictionIndex,
    build,
)
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
RESTR = FIXTURES / "diff" / "restrictions"

EX = "http://example.org/"
TRACK = EX + "Track"
HAS_SPEED = EX + "hasSpeed"
HAS_PART = EX + "hasPart"
HAS_GAUGE = EX + "hasGauge"
GAUGE = EX + "Gauge"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(RESTR / name)))


def _index(name: str) -> RestrictionIndex:
    return build(_canon(name))


def _only_on(index: RestrictionIndex, entity: str, on_property: str) -> DecodedRestriction:
    """The single restriction attached to ``entity`` for ``on_property``."""
    matches = [r for r in index.by_attached_entity[entity] if r.on_property == on_property]
    assert len(matches) == 1
    return matches[0]


def test_build_decodes_max_cardinality():
    restriction = _only_on(_index("cardinality_tightened_before.ttl"), TRACK, HAS_SPEED)
    assert restriction.kind == "max_cardinality"
    assert restriction.cardinality == 5
    assert restriction.filler is None


def test_build_decodes_min_cardinality():
    restriction = _only_on(_index("cardinality_kind_change_before.ttl"), TRACK, HAS_PART)
    assert restriction.kind == "min_cardinality"
    assert restriction.cardinality == 1


def test_build_decodes_exact_cardinality():
    restriction = _only_on(_index("cardinality_kind_change_after.ttl"), TRACK, HAS_PART)
    assert restriction.kind == "exact_cardinality"
    assert restriction.cardinality == 1


def test_build_decodes_someValues():
    restriction = _only_on(_index("someValues_to_allValues_before.ttl"), TRACK, HAS_GAUGE)
    assert restriction.kind == "some_values_from"
    assert restriction.filler == GAUGE


def test_build_decodes_allValues():
    restriction = _only_on(_index("someValues_to_allValues_after.ttl"), TRACK, HAS_GAUGE)
    assert restriction.kind == "all_values_from"
    assert restriction.filler == GAUGE


def test_build_decodes_hasValue():
    restriction = _only_on(_index("has_value.ttl"), TRACK, HAS_GAUGE)
    assert restriction.kind == "has_value"
    assert restriction.filler == EX + "StandardGauge"


def test_build_decodes_qualified_cardinality_with_filler():
    restriction = _only_on(_index("qualified_cardinality_before.ttl"), TRACK, HAS_GAUGE)
    assert restriction.kind == "min_qualified_cardinality"
    assert restriction.cardinality == 1
    assert restriction.filler == GAUGE


def test_build_collects_domain_per_property():
    index = _index("domain_swap_before.ttl")
    assert index.domains[EX + "locatedOn"] == frozenset({EX + "Signal"})


def test_build_collects_range_per_property():
    index = _index("range_removed_before.ttl")
    assert index.ranges[EX + "hasPart"] == frozenset({EX + "Wheel", EX + "Axle"})


def test_build_collects_equivalent_class_pairs():
    index = _index("equivalent_class_added_after.ttl")
    assert index.equivalent_class_sets[EX + "A"] == frozenset({EX + "B"})


def test_build_collects_disjoint_pairs():
    index = _index("disjoint_with_added_after.ttl")
    # Disjointness is symmetric: both classes list the other.
    assert index.disjoint_sets[EX + "Track"] == frozenset({EX + "Person"})
    assert index.disjoint_sets[EX + "Person"] == frozenset({EX + "Track"})


def test_build_expands_alldisjointclasses_to_pairs():
    index = _index("all_disjoint_classes.ttl")
    assert index.disjoint_sets[EX + "A"] == frozenset({EX + "B", EX + "C"})
    assert index.disjoint_sets[EX + "B"] == frozenset({EX + "A", EX + "C"})
    assert index.disjoint_sets[EX + "C"] == frozenset({EX + "A", EX + "B"})


def test_build_marks_malformed_as_complex():
    index = _index("malformed_restriction.ttl")
    restrictions = index.by_attached_entity[TRACK]
    assert len(restrictions) == 1
    assert restrictions[0].kind == "complex"
    assert restrictions[0].on_property is None


def test_build_records_via_predicate_subclassof_vs_equivalentclass():
    subclass = _only_on(_index("cardinality_tightened_before.ttl"), TRACK, HAS_SPEED)
    assert subclass.via_predicate == "rdfs:subClassOf"

    equivalent_index = _index("equivalent_restriction.ttl")
    equivalent = equivalent_index.by_attached_entity[EX + "Engine"][0]
    assert equivalent.via_predicate == "owl:equivalentClass"


def test_build_attached_to_resolved_for_subclassof_restriction():
    restriction = _only_on(_index("cardinality_tightened_before.ttl"), TRACK, HAS_SPEED)
    assert restriction.attached_to == TRACK


def test_build_handles_nested_filler_urns():
    index = _index("nested_expression_change_before.ttl")
    outer = _only_on(index, TRACK, HAS_PART)
    # The outer someValuesFrom filler is a reified inner restriction URN that
    # exists separately in the by_urn map.
    assert outer.kind == "some_values_from"
    assert outer.filler is not None
    assert outer.filler.startswith("urn:owlcompare:restriction:")
    assert outer.filler in index.by_urn
    inner = index.by_urn[outer.filler]
    assert inner.on_property == HAS_GAUGE
