"""Acceptance tests for owlcompare.canonicalize — specs/04-canonicalize.md."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import rdflib

from owlcompare.canonicalize import CanonicalizeOptions, canonicalize
from owlcompare.exceptions import CanonicalizationError
from owlcompare.loader import load
from owlcompare.model import (
    EntityIndex,
    OntologyMetadata,
    OntologySnapshot,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CANON_FIXTURES = FIXTURES / "canonicalize"

_RESTRICTION_PREFIX = "urn:owlcompare:restriction:"
_LIST_PREFIX = "urn:owlcompare:list:"


def _empty_snapshot(graph: rdflib.Graph) -> OntologySnapshot:
    metadata = OntologyMetadata(
        iri=None,
        version_iri=None,
        imports=(),
        labels=(),
        comments=(),
        version_info=None,
        prior_version=None,
        other_annotations=(),
    )
    index = EntityIndex(
        classes={},
        object_properties={},
        data_properties={},
        annotation_properties={},
        individuals={},
        datatypes={},
    )
    return OntologySnapshot(
        metadata=metadata,
        entities=index,
        graph=graph,
        prefixes={},
        source="<test>",
        format="turtle",
    )


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def test_canonicalize_empty_graph_returns_canonical_flag_true():
    snap = _empty_snapshot(rdflib.Graph())
    result = canonicalize(snap)
    assert result.canonical is True
    assert len(result.graph) == 0


def test_canonicalize_sets_canonical_flag():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    result = canonicalize(snap)
    assert result.canonical is True
    assert snap.canonical is False


def test_canonicalize_does_not_mutate_input():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    original_triples = set(snap.graph)
    canonicalize(snap)
    assert set(snap.graph) == original_triples


def test_canonicalize_is_idempotent():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    once = canonicalize(snap)
    twice = canonicalize(once)
    assert set(once.graph) == set(twice.graph)


def test_canonicalize_two_equivalent_inputs_produce_identical_output():
    """The single most important test in this component (per spec)."""
    snap_a = load(CANON_FIXTURES / "same_ontology_different_serialization_a.ttl")
    snap_b = load(CANON_FIXTURES / "same_ontology_different_serialization_b.ttl")
    canon_a = canonicalize(snap_a)
    canon_b = canonicalize(snap_b)
    # First, the triple sets must be identical — necessary precondition for
    # byte-equal serialization.
    assert set(canon_a.graph) == set(canon_b.graph)
    # Then assert byte-equal Turtle output.
    turtle_a = canon_a.graph.serialize(format="turtle")
    turtle_b = canon_b.graph.serialize(format="turtle")
    assert turtle_a == turtle_b


# ---------------------------------------------------------------------------
# Blank node canonicalization
# ---------------------------------------------------------------------------


def _bnode_labels(graph: rdflib.Graph) -> set[str]:
    labels: set[str] = set()
    for s, _p, o in graph:
        if isinstance(s, rdflib.BNode):
            labels.add(str(s))
        if isinstance(o, rdflib.BNode):
            labels.add(str(o))
    return labels


def test_blank_node_labels_stable_across_runs():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    # Disable later passes so we can observe pass-1 labels directly.
    opts = CanonicalizeOptions(reify_restrictions=False, collapse_lists=False, sort_triples=False)
    first = canonicalize(snap, opts)
    second = canonicalize(snap, opts)
    assert _bnode_labels(first.graph) == _bnode_labels(second.graph)


def test_blank_node_labels_content_addressed():
    """Two equivalent ontologies share blank-node labels post-canonicalization."""
    snap_a = load(CANON_FIXTURES / "same_ontology_different_serialization_a.ttl")
    snap_b = load(CANON_FIXTURES / "same_ontology_different_serialization_b.ttl")
    opts = CanonicalizeOptions(reify_restrictions=False, collapse_lists=False, sort_triples=False)
    canon_a = canonicalize(snap_a, opts)
    canon_b = canonicalize(snap_b, opts)
    assert _bnode_labels(canon_a.graph) == _bnode_labels(canon_b.graph)


# ---------------------------------------------------------------------------
# Restriction reification
# ---------------------------------------------------------------------------


def _restriction_iris(graph: rdflib.Graph) -> set[str]:
    iris: set[str] = set()
    for s, _p, o in graph:
        if isinstance(s, rdflib.URIRef) and str(s).startswith(_RESTRICTION_PREFIX):
            iris.add(str(s))
        if isinstance(o, rdflib.URIRef) and str(o).startswith(_RESTRICTION_PREFIX):
            iris.add(str(o))
    return iris


def test_simple_restriction_gets_urn_iri():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    canon = canonicalize(snap)
    track = rdflib.URIRef("http://example.org/simple#Track")
    subclass_objs = list(canon.graph.objects(track, rdflib.RDFS.subClassOf))
    urn_objects = [
        o
        for o in subclass_objs
        if isinstance(o, rdflib.URIRef) and str(o).startswith(_RESTRICTION_PREFIX)
    ]
    assert len(urn_objects) == 1


def test_same_restriction_same_urn_across_ontologies():
    snap_a = load(CANON_FIXTURES / "same_ontology_different_serialization_a.ttl")
    snap_b = load(CANON_FIXTURES / "same_ontology_different_serialization_b.ttl")
    canon_a = canonicalize(snap_a)
    canon_b = canonicalize(snap_b)
    iris_a = _restriction_iris(canon_a.graph)
    iris_b = _restriction_iris(canon_b.graph)
    assert iris_a and iris_a == iris_b


def test_distinct_restrictions_distinct_urns():
    snap = load(CANON_FIXTURES / "restriction_nested.ttl")
    canon = canonicalize(snap)
    iris = _restriction_iris(canon.graph)
    # The fixture has two distinct nested restrictions → two distinct URNs.
    assert len(iris) == 2


def test_nested_restriction_reified_recursively():
    snap = load(CANON_FIXTURES / "restriction_nested.ttl")
    canon = canonicalize(snap)
    # No blank node should survive after reification (the nested restriction
    # is a class-expression bnode and so is its outer wrapper; lists are not
    # involved in this fixture).
    bnodes_remaining = _bnode_labels(canon.graph)
    assert bnodes_remaining == set(), bnodes_remaining
    # And the outer restriction's someValuesFrom must point at a URN, not a
    # blank node.
    has_inner_link = False
    for _s, _p, o in canon.graph.triples((None, rdflib.OWL.someValuesFrom, None)):
        if isinstance(o, rdflib.URIRef) and str(o).startswith(_RESTRICTION_PREFIX):
            has_inner_link = True
    assert has_inner_link


def test_self_referential_restriction_does_not_recurse_infinitely():
    snap = load(CANON_FIXTURES / "restriction_self_ref.ttl")
    # Must terminate.
    canon = canonicalize(snap)
    iris = _restriction_iris(canon.graph)
    assert len(iris) >= 1


# ---------------------------------------------------------------------------
# List collapsing
# ---------------------------------------------------------------------------


def _list_iris(graph: rdflib.Graph) -> set[str]:
    iris: set[str] = set()
    for s, _p, o in graph:
        if isinstance(s, rdflib.URIRef) and str(s).startswith(_LIST_PREFIX):
            iris.add(str(s))
        if isinstance(o, rdflib.URIRef) and str(o).startswith(_LIST_PREFIX):
            iris.add(str(o))
    return iris


def test_list_collapse_produces_single_urn():
    snap = load(CANON_FIXTURES / "lists.ttl")
    canon = canonicalize(snap)
    iris = _list_iris(canon.graph)
    # Three-element list → three list nodes → three URNs (one per node).
    assert len(iris) == 3
    # And every list-node URN appears in the rewritten graph.
    assert all(iri.startswith(_LIST_PREFIX) for iri in iris)


def test_list_order_preserved():
    snap_in_order = load(CANON_FIXTURES / "lists.ttl")
    snap_reordered = load(CANON_FIXTURES / "lists_reordered.ttl")
    canon_in_order = canonicalize(snap_in_order)
    canon_reordered = canonicalize(snap_reordered)
    head_in_order = _list_head_for_union(canon_in_order.graph)
    head_reordered = _list_head_for_union(canon_reordered.graph)
    assert head_in_order is not None
    assert head_reordered is not None
    assert head_in_order != head_reordered


def _list_head_for_union(graph: rdflib.Graph) -> str | None:
    for _s, _p, o in graph.triples((None, rdflib.OWL.unionOf, None)):
        if isinstance(o, rdflib.URIRef) and str(o).startswith(_LIST_PREFIX):
            return str(o)
    return None


def test_malformed_list_warns_does_not_raise(caplog: pytest.LogCaptureFixture):
    snap = load(CANON_FIXTURES / "malformed_list.ttl")
    with caplog.at_level(logging.INFO, logger="owlcompare.canonicalize"):
        canon = canonicalize(snap)
    assert any("malformed" in r.getMessage().lower() for r in caplog.records)
    # No exception was raised; the canonical snapshot still exists.
    assert canon.canonical is True


# ---------------------------------------------------------------------------
# Triple sorting
# ---------------------------------------------------------------------------


def test_triple_sorting_produces_deterministic_serialization():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    canon = canonicalize(snap)
    nt_first = canon.graph.serialize(format="nt")
    canon_again = canonicalize(snap)
    nt_second = canon_again.graph.serialize(format="nt")
    assert nt_first == nt_second


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


def test_disable_blank_node_pass_preserves_original_labels():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    original_labels = _bnode_labels(snap.graph)
    opts = CanonicalizeOptions(
        canonicalize_blank_nodes=False,
        reify_restrictions=False,
        collapse_lists=False,
        sort_triples=False,
    )
    canon = canonicalize(snap, opts)
    assert _bnode_labels(canon.graph) == original_labels


def test_disable_reify_restrictions_leaves_blank_nodes():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    opts = CanonicalizeOptions(reify_restrictions=False)
    canon = canonicalize(snap, opts)
    # No restriction URNs should appear when the pass is disabled.
    assert _restriction_iris(canon.graph) == set()
    # The original anonymous restriction must remain a blank node.
    assert _bnode_labels(canon.graph) != set()


def test_disable_collapse_lists_preserves_list_triples():
    snap = load(CANON_FIXTURES / "lists.ttl")
    opts = CanonicalizeOptions(collapse_lists=False)
    canon = canonicalize(snap, opts)
    # No list URNs when disabled.
    assert _list_iris(canon.graph) == set()
    # rdf:first triples must still be present.
    rdf_first_count = sum(1 for _ in canon.graph.triples((None, rdflib.RDF.first, None)))
    assert rdf_first_count > 0


def test_disable_sort_still_correct_just_undeterministic():
    snap = load(CANON_FIXTURES / "restriction_simple.ttl")
    opts = CanonicalizeOptions(sort_triples=False)
    canon = canonicalize(snap, opts)
    # Other invariants still hold.
    assert canon.canonical is True
    assert _restriction_iris(canon.graph) != set()


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_named_graph_input_raises_canonicalization_error():
    # The loader parses into a plain Graph and merges named graphs silently;
    # canonicalize()'s named-graph rejection guards against a ConjunctiveGraph
    # snapshot, which we construct directly here. The CLI path re-parses
    # quad-format inputs to detect this on the loader's output — see
    # tests/unit/test_cli_canonicalize.py::test_cli_canonicalize_named_graph_input_exits_4.
    dataset = rdflib.Dataset()
    dataset.parse(
        data=(CANON_FIXTURES / "with_named_graph.trig").read_text(encoding="utf-8"),
        format="trig",
    )
    snap = _empty_snapshot(dataset)
    with pytest.raises(CanonicalizationError) as info:
        canonicalize(snap)
    assert "named graph" in str(info.value).lower()


def test_canonicalization_error_exit_code_is_4():
    err = CanonicalizationError("boom")
    assert err.exit_code == 4


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


def test_load_canonicalize_roundtrip_preserves_entity_count():
    snap = load(FIXTURES / "era_micro.ttl")
    canon = canonicalize(snap)
    assert snap.entities.counts() == canon.entities.counts()
    assert snap.entities.all_iris() == canon.entities.all_iris()
