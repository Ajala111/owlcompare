"""Acceptance tests for Component 02 internal model — specs/02-loader.md."""

from __future__ import annotations

import dataclasses

import pytest
import rdflib

from owlcompare.model import (
    Entity,
    EntityIndex,
    EntityKind,
    OntologyMetadata,
    OntologySnapshot,
)


def _entity(iri: str = "http://example.org/E", kind: EntityKind = "class") -> Entity:
    return Entity(iri=iri, kind=kind, labels=(), comments=(), is_deprecated=False)


def _empty_index(**overrides: dict[str, Entity]) -> EntityIndex:
    base: dict[str, dict[str, Entity]] = {
        "classes": {},
        "object_properties": {},
        "data_properties": {},
        "annotation_properties": {},
        "individuals": {},
        "datatypes": {},
    }
    base.update(overrides)  # type: ignore[arg-type]
    return EntityIndex(**base)  # type: ignore[arg-type]


def _empty_metadata(iri: str | None = None) -> OntologyMetadata:
    return OntologyMetadata(
        iri=iri,
        version_iri=None,
        imports=(),
        labels=(),
        comments=(),
        version_info=None,
        prior_version=None,
        other_annotations=(),
    )


def _snapshot(graph: rdflib.Graph | None = None, iri: str | None = None) -> OntologySnapshot:
    return OntologySnapshot(
        metadata=_empty_metadata(iri=iri),
        entities=_empty_index(),
        graph=graph if graph is not None else rdflib.Graph(),
        prefixes={},
        source="<test>",
        format="turtle",
    )


def test_entity_is_frozen():
    entity = _entity()
    with pytest.raises(dataclasses.FrozenInstanceError):
        entity.iri = "http://example.org/other"  # type: ignore[misc]


def test_entity_is_hashable():
    e1 = _entity("http://example.org/A")
    e2 = _entity("http://example.org/B")
    bag = {e1, e2, _entity("http://example.org/A")}
    assert len(bag) == 2


def test_entity_index_lookup_unknown_iri_returns_none():
    assert _empty_index().lookup("http://example.org/missing") is None


def test_entity_index_kinds_of_punned_iri_returns_multiple():
    iri = "http://example.org/Eagle"
    idx = _empty_index(
        classes={iri: _entity(iri, "class")},
        individuals={iri: _entity(iri, "individual")},
    )
    kinds = idx.kinds_of(iri)
    assert set(kinds) == {"class", "individual"}
    assert "class" in kinds and "individual" in kinds


def test_entity_index_all_iris_unions_kinds():
    idx = _empty_index(
        classes={"http://example.org/C": _entity("http://example.org/C", "class")},
        individuals={"http://example.org/I": _entity("http://example.org/I", "individual")},
        datatypes={"http://example.org/D": _entity("http://example.org/D", "datatype")},
    )
    assert idx.all_iris() == {
        "http://example.org/C",
        "http://example.org/I",
        "http://example.org/D",
    }


def test_entity_index_counts_matches_dict_lengths():
    idx = _empty_index(
        classes={"a": _entity("a"), "b": _entity("b")},
        individuals={"c": _entity("c", "individual")},
    )
    counts = idx.counts()
    assert counts["class"] == 2
    assert counts["individual"] == 1
    assert counts["object_property"] == 0
    assert sum(counts.values()) == len(idx)


def test_snapshot_axiom_count_matches_graph_len():
    graph = rdflib.Graph()
    graph.add(
        (
            rdflib.URIRef("http://example.org/s"),
            rdflib.URIRef("http://example.org/p"),
            rdflib.URIRef("http://example.org/o"),
        )
    )
    snap = _snapshot(graph=graph)
    assert snap.axiom_count() == 1
    assert snap.axiom_count() == len(graph)


def test_snapshot_summary_contains_iri_and_counts():
    snap_named = _snapshot(iri="http://example.org/onto")
    text_named = snap_named.summary()
    assert "http://example.org/onto" in text_named
    assert "Entity counts:" in text_named
    for kind in ("class", "object_property", "individual", "datatype"):
        assert kind in text_named

    snap_anon = _snapshot(iri=None)
    text_anon = snap_anon.summary()
    assert "<no ontology IRI declared>" in text_anon


def test_summary_includes_sample_entity_iris():
    classes = {
        "http://data.europa.eu/949/Track": Entity(
            iri="http://data.europa.eu/949/Track",
            kind="class",
            labels=(),
            comments=(),
            is_deprecated=False,
        ),
        "http://data.europa.eu/949/BaliseGroup": Entity(
            iri="http://data.europa.eu/949/BaliseGroup",
            kind="class",
            labels=(),
            comments=(),
            is_deprecated=False,
        ),
    }
    snap = OntologySnapshot(
        metadata=_empty_metadata(iri="http://data.europa.eu/949/ontology"),
        entities=_empty_index(classes=classes),
        graph=rdflib.Graph(),
        prefixes={"era": "http://data.europa.eu/949/"},
        source="<test>",
        format="turtle",
    )
    text = snap.summary()
    # Full IRIs preserved.
    assert "http://data.europa.eu/949/Track" in text
    assert "http://data.europa.eu/949/BaliseGroup" in text
    # Compact shortened form alongside the full IRI.
    assert "era:Track" in text
    assert "era:BaliseGroup" in text


def test_summary_truncates_long_entity_lists():
    classes = {
        f"http://example.org/E{i}": Entity(
            iri=f"http://example.org/E{i}",
            kind="class",
            labels=(),
            comments=(),
            is_deprecated=False,
        )
        for i in range(7)
    }
    snap = OntologySnapshot(
        metadata=_empty_metadata(iri="http://example.org/o"),
        entities=_empty_index(classes=classes),
        graph=rdflib.Graph(),
        prefixes={},
        source="<test>",
        format="turtle",
    )
    text = snap.summary()
    # 7 entities, limit 5 → overflow of 2.
    assert "...and 2 more" in text
    # First five (sorted) should still appear; the last two should not.
    assert "http://example.org/E0" in text
    assert "http://example.org/E4" in text
    assert "http://example.org/E6" not in text
