"""Acceptance tests for the class-set index — specs/12.5-anonymous-structures.md § Part 1."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff.structural import _class_set_index as csi
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ANON = FIXTURES / "anonstruct"

ERA = "http://data.europa.eu/949/"
TIME = "http://www.w3.org/2006/time#"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(ANON / name)))


def test_build_decodes_unionOf_on_domain():
    index = csi.build(_canon("domain_union_member_added_v1.ttl"))
    attachment = index.for_key(ERA + "axleSpacingDistance", "rdfs:domain")
    assert attachment is not None
    assert attachment.operator == "unionOf"
    assert set(attachment.member_iris) == {
        ERA + "VehicleType",
        ERA + "VehicleTypeConfigParameterSet",
    }


def test_build_decodes_unionOf_on_range():
    index = csi.build(_canon("range_union_classes_changed_v1.ttl"))
    attachment = index.for_key(ERA + "borderPointStation", "rdfs:range")
    assert attachment is not None
    assert set(attachment.member_iris) == {ERA + "Station", ERA + "BorderPoint"}


def test_build_decodes_unionOf_on_subClassOf():
    index = csi.build(_canon("subclass_union_member_added_v1.ttl"))
    attachment = index.for_key(ERA + "TemporalFeature", "rdfs:subClassOf")
    assert attachment is not None
    assert set(attachment.member_iris) == {TIME + "TemporalDuration", TIME + "TemporalInstant"}


def test_build_decodes_unionOf_on_equivalentClass():
    index = csi.build(_canon("equivalent_class_union_changed_v1.ttl"))
    attachment = index.for_key(ERA + "Track", "owl:equivalentClass")
    assert attachment is not None
    assert set(attachment.member_iris) == {ERA + "RailwaySegment", ERA + "Segment"}


def test_build_decodes_intersectionOf():
    index = csi.build(_canon("domain_intersection_member_added_v1.ttl"))
    attachment = index.for_key(ERA + "axleSpacingDistance", "rdfs:domain")
    assert attachment is not None
    assert attachment.operator == "intersectionOf"


def test_build_normalizes_single_member_union_to_bare():
    index = csi.build(_canon("single_member_union.ttl"))
    # A union with one named member is logically bare → no set attachment recorded.
    assert index.for_key(ERA + "axleSpacingDistance", "rdfs:domain") is None
    assert index.by_attachment == {}


def test_build_records_member_iris_sorted():
    index = csi.build(_canon("equivalent_class_union_changed_v1.ttl"))
    attachment = index.for_key(ERA + "Track", "owl:equivalentClass")
    assert attachment is not None
    assert list(attachment.member_iris) == sorted(attachment.member_iris)


def test_build_skips_blank_node_members():
    index = csi.build(_canon("union_blank_member.ttl"))
    attachment = index.for_key(ERA + "p", "rdfs:domain")
    assert attachment is not None
    assert set(attachment.member_iris) == {ERA + "A", ERA + "B"}


def test_build_skips_nested_restriction_members():
    index = csi.build(_canon("union_nested_restriction.ttl"))
    attachment = index.for_key(ERA + "p", "rdfs:domain")
    assert attachment is not None
    assert set(attachment.member_iris) == {ERA + "A", ERA + "B"}
    assert not any(m.startswith("urn:owlcompare:") for m in attachment.member_iris)


def test_build_handles_empty_list_gracefully():
    index = csi.build(_canon("union_empty.ttl"))
    assert index.by_attachment == {}  # owl:unionOf () → no attachment, no error
