"""Acceptance tests for the datatype facet diff — specs/12.5-anonymous-structures.md § Part 3."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import syntactic
from owlcompare.diff._common import Change
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.structural import class_sets, entities, hierarchy, restrictions
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ANON = FIXTURES / "anonstruct"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(ANON / name)))


def _run(before: str, after: str) -> list[Change]:
    a, b = _canon(before), _canon(after)
    layer0 = syntactic.diff(a, b)
    registry = SubsumptionRegistry()
    entities.diff(a, b, layer0, registry)
    hierarchy.diff(a, b, layer0, registry)
    restrictions.diff(a, b, layer0, registry)
    return class_sets.diff(a, b, layer0, registry)


def _one(changes: list[Change], kind: str) -> Change:
    matches = [c for c in changes if c.kind == kind]
    assert len(matches) == 1, f"expected one {kind}, got {[c.kind for c in changes]}"
    return matches[0]


def test_facet_min_tightened_emits_facet_changed_breaking():
    changes = _run("range_facet_min_tightened_v1.ttl", "range_facet_min_tightened_v2.ttl")
    change = _one(changes, "datatype_facet_changed")
    assert change.severity == "breaking"
    assert change.details["changed_facets"] == ["min_inclusive"]


def test_facet_max_relaxed_emits_facet_changed_non_breaking():
    # range_facet_tightened reversed: max 100000 → 327670 is a relaxation.
    changes = _run("range_facet_tightened_v2.ttl", "range_facet_tightened_v1.ttl")
    change = _one(changes, "datatype_facet_changed")
    assert change.severity == "non_breaking"
    assert change.details["changed_facets"] == ["max_inclusive"]


def test_facet_added_emits_facet_added_breaking():
    changes = _run("range_facet_added_v1.ttl", "range_facet_added_v2.ttl")
    assert _one(changes, "datatype_facet_added").severity == "breaking"


def test_facet_removed_emits_facet_removed_non_breaking():
    # range_facet_added reversed: the [min 0] facet is dropped.
    changes = _run("range_facet_added_v2.ttl", "range_facet_added_v1.ttl")
    assert _one(changes, "datatype_facet_removed").severity == "non_breaking"


def test_base_datatype_changed_emits_base_changed_breaking():
    changes = _run("range_facet_base_changed_v1.ttl", "range_facet_base_changed_v2.ttl")
    change = _one(changes, "datatype_base_changed")
    assert change.severity == "breaking"
    assert change.details["base_before"].endswith("decimal")
    assert change.details["base_after"].endswith("integer")


def test_facet_summary_includes_arrow_notation():
    changes = _run("range_facet_tightened_v1.ttl", "range_facet_tightened_v2.ttl")
    assert "→" in _one(changes, "datatype_facet_changed").summary
