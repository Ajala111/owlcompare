"""Acceptance tests for the datatype facet index — specs/12.5-anonymous-structures.md § Part 3."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff.structural import _datatype_facet_index as dfi
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ANON = FIXTURES / "anonstruct"

ERA = "http://data.europa.eu/949/"
XSD = "http://www.w3.org/2001/XMLSchema#"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(ANON / name)))


def test_build_decodes_min_inclusive():
    facets = dfi.build(_canon("facets_numeric.ttl"))[ERA + "decProp"]
    assert facets.min_inclusive == 0


def test_build_decodes_max_inclusive():
    facets = dfi.build(_canon("facets_numeric.ttl"))[ERA + "decProp"]
    assert facets.max_inclusive == 100


def test_build_decodes_min_exclusive():
    facets = dfi.build(_canon("facets_numeric.ttl"))[ERA + "decProp"]
    assert facets.min_exclusive == 1


def test_build_decodes_max_exclusive():
    facets = dfi.build(_canon("facets_numeric.ttl"))[ERA + "decProp"]
    assert facets.max_exclusive == 99


def test_build_decodes_length_facets():
    facets = dfi.build(_canon("facets_length.ttl"))[ERA + "strProp"]
    assert (facets.length, facets.min_length, facets.max_length) == (5, 1, 10)


def test_build_decodes_pattern():
    facets = dfi.build(_canon("facets_pattern.ttl"))[ERA + "codeProp"]
    assert facets.pattern == "[A-Z]+"


def test_build_decodes_base_datatype():
    facets = dfi.build(_canon("facets_numeric.ttl"))[ERA + "decProp"]
    assert facets.base_datatype == XSD + "decimal"


def test_build_records_raw_urn():
    # rdfs:Datatype nodes are not reified into URNs, so a facet restriction's
    # raw_urn is None (it stays a canonicalized blank node).
    facets = dfi.build(_canon("facets_numeric.ttl"))[ERA + "decProp"]
    assert facets.raw_urn is None
