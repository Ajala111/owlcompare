"""Unit tests for rename fingerprinting and scoring — specs/11-rename-detection.md.

The scoring weights (0.3 / 0.2 / 0.1 / 0.05) and per-category caps
(0.5 / 0.4 / 0.3 / 0.2) plus the 1.0 clamp are pinned here so an accidental
retune is caught.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff._rename_evidence import EntityFingerprint, build_fingerprint, score
from owlcompare.loader import load

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "rename"

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
_SUBCLASS_OF = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
_DOMAIN = "http://www.w3.org/2000/01/rdf-schema#domain"
_RANGE = "http://www.w3.org/2000/01/rdf-schema#range"

_ASSET = "http://data.europa.eu/949/Asset"
_VEHICLE = "http://data.europa.eu/949/Vehicle"
_TRACK = "http://data.europa.eu/949/Track"
_PLATFORM = "http://data.europa.eu/949/Platform"


def _snapshot(name: str):
    return canonicalize(load(str(FIXTURES / name)))


def _fp(name: str, iri: str, kind: str = "class") -> EntityFingerprint:
    return build_fingerprint(_snapshot(name), iri, kind)


def test_build_fingerprint_captures_labels():
    fp = _fp("fingerprint_rename_v1.ttl", _TRACK)
    assert ("en", "Track") in fp.labels


def test_build_fingerprint_captures_parents():
    fp = _fp("fingerprint_rename_v1.ttl", _TRACK)
    assert set(fp.parents) == {_ASSET, _VEHICLE}


def test_build_fingerprint_captures_incoming_predicates():
    fp = _fp("fingerprint_rename_v1.ttl", _TRACK)
    # era:Tunnel subClassOf Track; era:hasPart domain Track and range Track.
    assert _SUBCLASS_OF in fp.incoming_predicates
    assert _DOMAIN in fp.incoming_predicates
    assert _RANGE in fp.incoming_predicates


def test_build_fingerprint_captures_outgoing_predicates():
    fp = _fp("fingerprint_rename_v1.ttl", _TRACK)
    assert _RDF_TYPE in fp.outgoing_predicates
    assert _LABEL in fp.outgoing_predicates
    assert _SUBCLASS_OF in fp.outgoing_predicates


def test_build_fingerprint_elides_entity_own_iri():
    fp = _fp("fingerprint_rename_v1.ttl", _TRACK)
    # Only predicates are recorded, never the entity's own IRI as a value.
    assert _TRACK not in fp.incoming_predicates
    assert _TRACK not in fp.outgoing_predicates


def test_build_fingerprint_captures_attached_restrictions():
    fp = _fp("class_rename_with_new_restriction_v2.ttl", _PLATFORM)
    assert fp.attached_restrictions
    assert all(u.startswith("urn:owlcompare:restriction:") for u in fp.attached_restrictions)


def _make_fp(**kw) -> EntityFingerprint:
    base = {
        "iri": "urn:x",
        "kind": "class",
        "labels": (),
        "parents": (),
        "children": (),
        "incoming_predicates": (),
        "outgoing_predicates": (),
        "attached_restrictions": (),
    }
    base.update(kw)
    return EntityFingerprint(**base)  # type: ignore[arg-type]


def test_fingerprint_score_perfect_match_is_1():
    fp = _make_fp(
        labels=(("en", "A"), ("fr", "B")),
        parents=("p1", "p2"),
        incoming_predicates=("i1", "i2", "i3"),
        outgoing_predicates=("o1", "o2", "o3", "o4"),
    )
    # Raw 0.5 + 0.4 + 0.3 + 0.2 = 1.4, clamped to 1.0.
    assert score(fp, fp) == 1.0


def test_fingerprint_score_no_overlap_is_0():
    left = _make_fp(labels=(("en", "A"),), parents=("p1",))
    right = _make_fp(labels=(("en", "B"),), parents=("p2",))
    assert score(left, right) == 0.0


def test_fingerprint_score_partial_label_match_below_threshold():
    left = _make_fp(labels=(("en", "Same"),))
    right = _make_fp(labels=(("en", "Same"),))
    s = score(left, right)
    assert s == pytest.approx(0.3)
    assert s < 0.6


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({"labels": (("en", "x"),)}, 0.3),  # 1 label
        ({"labels": (("en", "x"), ("fr", "y"))}, 0.5),  # 2 labels capped at 0.5
        ({"parents": ("p",)}, 0.2),  # 1 parent
        ({"incoming_predicates": ("i",)}, 0.1),  # 1 incoming
        ({"outgoing_predicates": ("o",)}, 0.05),  # 1 outgoing
    ],
)
def test_fingerprint_score_weights_are_pinned(kw, expected):
    fp = _make_fp(**kw)
    assert score(fp, fp) == pytest.approx(expected)
