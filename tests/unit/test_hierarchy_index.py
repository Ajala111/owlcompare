"""Acceptance tests for the hierarchy index — specs/07-structural-hierarchy.md § Step 1."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff.structural._hierarchy_index import build
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
HIER = FIXTURES / "diff" / "hierarchy"

A = "http://example.org/A"
B = "http://example.org/B"
C = "http://example.org/C"
HAS_GAUGE = "http://example.org/hasGauge"
HAS_DIMENSION = "http://example.org/hasDimension"


def _load(name: str) -> OntologySnapshot:
    return load(str(HIER / name))


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(_load(name))


def test_build_index_captures_direct_class_parents():
    index = build(_load("simple_reparent_generalization_before.ttl"))
    assert index.class_parents[A] == frozenset({B})
    assert index.class_parents[B] == frozenset({C})


def test_build_index_captures_direct_property_parents():
    index = build(_load("property_reparent_before.ttl"))
    assert index.property_parents[HAS_GAUGE] == frozenset({HAS_DIMENSION})


def test_build_index_skips_blank_node_parents():
    # Loaded without canonicalization so the anonymous superclass stays a blank
    # node; build() must not record it as a parent of ex:A.
    index = build(_load("blank_node_parent.ttl"))
    assert A not in index.class_parents


def test_build_index_skips_synthetic_restriction_parents():
    # After canonicalization ex:Door's superclass is a urn:owlcompare:restriction
    # URN, which is not a hierarchy entity and must be excluded.
    index = build(_canon("synthetic_restriction_parent_before.ttl"))
    assert "http://example.org/Door" not in index.class_parents


def test_build_index_empty_ontology_produces_empty_index():
    index = build(_canon("empty_ontology.ttl"))
    assert index.class_parents == {}
    assert index.class_children == {}
    assert index.property_parents == {}
    assert index.property_children == {}


def test_class_children_inverse_of_parents():
    index = build(_load("simple_reparent_generalization_before.ttl"))
    # B is a parent of A, and C is a parent of B.
    assert index.class_children[B] == frozenset({A})
    assert index.class_children[C] == frozenset({B})


def test_property_children_inverse_of_parents():
    index = build(_load("property_reparent_before.ttl"))
    assert index.property_children[HAS_DIMENSION] == frozenset({HAS_GAUGE})
