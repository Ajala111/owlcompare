"""Integration tests for Layer 0 diff — specs/05-syntactic-diff.md.

The flagship ``era_evolution`` pair drives the realism of the whole component:
its four intended edits (one class added, one property removed, one cardinality
change, one French label change) plus a version bump expand to an exact set of
triple-level changes that we pin here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from rdflib import RDF

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import syntactic
from owlcompare.loader import load

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"
_RDF_TYPE = str(RDF.type)


def _canon(name: str):
    return canonicalize(load(str(DIFF / name)))


def test_era_evolution_fixture_produces_expected_change_counts():
    changes = syntactic.diff(_canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl"))

    removed = [c for c in changes if c.kind == "triple_removed"]
    added = [c for c in changes if c.kind == "triple_added"]
    breaking = [c for c in changes if c.severity == "breaking"]

    assert len(changes) == 18
    assert len(removed) == 10
    assert len(added) == 8
    assert len(breaking) == 5

    # The added class: era:Platform declared as an owl:Class (additive).
    platform_decl = [
        c
        for c in added
        if c.subject == "http://data.europa.eu/949/Platform"
        and c.details["predicate_iri"] == _RDF_TYPE
    ]
    assert len(platform_decl) == 1
    assert platform_decl[0].severity == "additive"

    # The French label change surfaces as one removed + one added rdfs:label.
    fr_removed = [c for c in removed if c.details["object"] == '"Voie"@fr']
    fr_added = [c for c in added if c.details["object"] == '"Voie ferrée"@fr']
    assert len(fr_removed) == 1
    assert len(fr_added) == 1
    assert fr_removed[0].severity == "info"
    assert fr_added[0].severity == "info"

    # The removed property era:locatedOn contributes breaking removals.
    located_on = [c for c in removed if c.subject == "http://data.europa.eu/949/locatedOn"]
    assert len(located_on) == 4


def test_diff_via_python_dash_m_subprocess():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "owlcompare",
            "diff",
            str(DIFF / "era_evolution_v1.ttl"),
            str(DIFF / "era_evolution_v2.ttl"),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    # era_evolution has breaking changes -> exit 10.
    assert proc.returncode == 10
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == 1
    assert payload["summary"]["total"] == 18
    assert payload["summary"]["breaking"] == 5
