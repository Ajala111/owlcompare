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
from owlcompare.diff import orchestrator, syntactic
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.structural import entities
from owlcompare.loader import load

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"
HIER = DIFF / "hierarchy"
_RDF_TYPE = str(RDF.type)
_SUBCLASS_OF = "http://www.w3.org/2000/01/rdf-schema#subClassOf"


def _canon(name: str):
    return canonicalize(load(str(DIFF / name)))


def _canon_hier(name: str):
    return canonicalize(load(str(HIER / name)))


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
            "--layers",
            "syntactic",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    # era_evolution has breaking changes -> exit 10. Pinned to the syntactic
    # layer so the Layer 0 triple totals stay the baseline for this check.
    assert proc.returncode == 10
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == 1
    assert payload["summary"]["total"] == 18
    assert payload["summary"]["breaking"] == 5


def _run(v_a: str, v_b: str):
    return orchestrator.run(_canon(v_a), _canon(v_b))


def test_era_evolution_layer1_emits_class_added_for_platform():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    class_added = [c for c in result.changes if c.layer == "structural" and c.kind == "class_added"]
    assert len(class_added) == 1
    assert class_added[0].subject == "http://data.europa.eu/949/Platform"
    assert class_added[0].severity == "additive"
    assert class_added[0].summary == 'Class added: era:Platform "Platform"@en'


def test_era_evolution_layer1_emits_object_property_removed_for_locatedon():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    removed = [
        c for c in result.changes if c.layer == "structural" and c.kind == "object_property_removed"
    ]
    assert len(removed) == 1
    assert removed[0].subject == "http://data.europa.eu/949/locatedOn"
    assert removed[0].severity == "breaking"


def test_era_evolution_layer1_subsumes_associated_layer0_changes():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    platform = next(
        c
        for c in result.changes
        if c.kind == "class_added" and c.subject == "http://data.europa.eu/949/Platform"
    )
    # Platform's rdf:type + rdfs:label triple additions are both subsumed.
    assert len(platform.details["subsumes"]) == 2
    for layer0_id in platform.details["subsumes"]:
        assert registry.is_explained(layer0_id)


def test_era_evolution_total_change_count_reduces_with_subsumption():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    structural = [c for c in result.changes if c.layer == "structural"]
    layer0 = [c for c in result.changes if c.layer == "syntactic"]
    unexplained = [c for c in layer0 if not registry.is_explained(c.details["change_id"])]
    visible_by_default = len(structural) + len(unexplained)
    assert visible_by_default < len(result.changes)
    # And strictly fewer than Component 05's flat 18 Layer 0 changes.
    assert visible_by_default < 18


def _run_hier(v_a: str, v_b: str):
    return orchestrator.run(_canon_hier(v_a), _canon_hier(v_b))


def test_era_hierarchy_fixture_emits_one_reparented_change():
    result = _run_hier("era_hierarchy_v1.ttl", "era_hierarchy_v2.ttl")
    reparented = [c for c in result.changes if c.kind == "class_reparented"]
    assert len(reparented) == 1
    assert reparented[0].subject == "http://data.europa.eu/949/Signal"
    assert reparented[0].details["parents_before"] == ["http://data.europa.eu/949/Equipment"]
    assert reparented[0].details["parents_after"] == ["http://data.europa.eu/949/Asset"]


def test_era_hierarchy_fixture_emits_one_class_added_for_asset():
    result = _run_hier("era_hierarchy_v1.ttl", "era_hierarchy_v2.ttl")
    class_added = [c for c in result.changes if c.kind == "class_added"]
    assert len(class_added) == 1
    assert class_added[0].subject == "http://data.europa.eu/949/Asset"


def test_era_hierarchy_fixture_subsumes_subclassof_triples():
    result = _run_hier("era_hierarchy_v1.ttl", "era_hierarchy_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    reparented = next(c for c in result.changes if c.kind == "class_reparented")
    # The reparent subsumes both the removed (Signal->Equipment) and added
    # (Signal->Asset) subClassOf triples.
    subclass_changes = [
        c
        for c in result.changes
        if c.layer == "syntactic"
        and c.subject == "http://data.europa.eu/949/Signal"
        and c.details.get("predicate_iri") == _SUBCLASS_OF
    ]
    assert len(subclass_changes) == 2
    assert len(reparented.details["subsumes"]) == 2
    for change in subclass_changes:
        assert registry.is_explained(change.details["change_id"])


def test_era_evolution_fixture_unchanged_results():
    # Regression: era_evolution has no hierarchy changes, so adding Component 07
    # to the orchestrator must not alter the structural output versus running the
    # entity slice alone.
    a, b = _canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl")
    layer0 = syntactic.diff(a, b)
    entities_only = entities.diff(a, b, layer0, SubsumptionRegistry())

    result = orchestrator.run(a, b)
    structural = [c for c in result.changes if c.layer == "structural"]
    assert structural == entities_only
