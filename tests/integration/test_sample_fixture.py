"""Regression tests for the public documentation sample fixtures.

The ``tests/fixtures/sample/`` Vehicle pair is what the user-facing docs (the
landing page, the first-diff tutorial, the live example reports) are built from,
so its diff output is effectively published. These tests pin that output: if a
future change alters what the sample fixtures produce, the docs silently go stale
and CI catches it here. Structural assertions only — no golden text/HTML file.

The fixtures deliberately mirror ``era_evolution`` (one class added, one property
removed, one cardinality change, one French label change, plus a version bump),
and the rename pair mirrors ``era_renames`` (one rename with cascade
consequences) — but in the domain-neutral ``ex:`` Vehicle vocabulary.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import orchestrator
from owlcompare.loader import load

SAMPLE = Path(__file__).resolve().parent.parent / "fixtures" / "sample"

_EX = "http://example.org/"


def _canon(name: str):
    return canonicalize(load(str(SAMPLE / name)))


def _run(v_a: str, v_b: str):
    return orchestrator.run(_canon(v_a), _canon(v_b))


def _structural(result):
    return [c for c in result.changes if c.layer == "structural"]


def _unexplained_layer0(result):
    registry = result.metadata["subsumption_registry"]
    layer0 = [c for c in result.changes if c.layer == "syntactic"]
    return [c for c in layer0 if not registry.is_explained(c.details["change_id"])]


def test_sample_fixture_produces_the_documented_five_changes():
    """Regression guard for the public documentation example.

    The sample fixture appears on the docs site landing page and drives the
    getting-started tutorial. This single test asserts the diff produces exactly
    the five changes the docs describe — kinds, subjects, severities, the relaxed
    cardinality, the refined French label, the version bump, zero unexplained
    Layer 0, and the exit-10 CI signal. Granular per-aspect correctness tests live
    in test_diff_integration.py (test_era_evolution_*); deliberately, this is one
    end-to-end public-docs correctness contract rather than a dozen micro-tests,
    so the whole documented output moves or breaks together.
    """
    result = _run("sample_v1.ttl", "sample_v2.ttl")
    structural = _structural(result)
    by_kind = {c.kind: c for c in structural}

    # Exactly five Layer 1 changes, one of each documented kind.
    assert len(structural) == 5
    assert sorted(by_kind) == [
        "annotation_changed",
        "class_added",
        "object_property_removed",
        "ontology_metadata_changed",
        "restriction_changed",
    ]

    # 1. class_added — ex:ElectricVehicle, additive.
    added = by_kind["class_added"]
    assert added.subject == f"{_EX}ElectricVehicle"
    assert added.severity == "additive"

    # 2. object_property_removed — ex:assembledAt, breaking.
    removed = by_kind["object_property_removed"]
    assert removed.subject == f"{_EX}assembledAt"
    assert removed.severity == "breaking"

    # 3. restriction_changed — ex:Car's ex:hasWheel max 4 -> max 6 (relaxed),
    #    non-breaking.
    restriction = by_kind["restriction_changed"]
    assert restriction.subject == f"{_EX}Car"
    assert restriction.details["on_property"] == f"{_EX}hasWheel"
    assert restriction.details["before"]["kind"] == "max_cardinality"
    assert restriction.details["before"]["cardinality"] == 4
    assert restriction.details["after"]["cardinality"] == 6
    assert restriction.severity == "non_breaking"

    # 4. annotation_changed — ex:Vehicle French label refined, info.
    label = by_kind["annotation_changed"]
    assert label.subject == f"{_EX}Vehicle"
    assert label.details["predicate_short"] == "label"
    assert label.details["language"] == "fr"
    assert label.details["before"]["value"] == "Véhicule"
    assert label.details["after"]["value"] == "Véhicule à moteur"
    assert label.severity == "info"

    # 5. ontology_metadata_changed — versionInfo 1.0.0 -> 2.0.0, info.
    meta = by_kind["ontology_metadata_changed"]
    assert meta.details["predicate_short"] == "versionInfo"
    assert meta.details["before"]["value"] == "1.0.0"
    assert meta.details["after"]["value"] == "2.0.0"
    assert meta.severity == "info"

    # No leftover, unexplained Layer 0 noise — every raw triple is accounted for.
    assert _unexplained_layer0(result) == []

    # Exactly one breaking change -> the CLI exits 10 (the CI signal the docs
    # promise; see docs/reference/exit-codes.md).
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "owlcompare",
            "diff",
            str(SAMPLE / "sample_v1.ttl"),
            str(SAMPLE / "sample_v2.ttl"),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 10


def test_sample_renames_fixture_produces_one_consolidated_rename():
    """Regression guard for the public rename example.

    The sample rename fixture backs the landing page's "rename example" report,
    so its output is effectively published. This single test asserts the whole
    documented result: one consolidated ex:Vehicle -> ex:MotorVehicle rename at
    high confidence, both cascade consequences subsumed, no leftover changes, and
    zero unexplained Layer 0. Granular per-aspect rename tests live in
    test_diff_integration.py (test_*_rename_*); this is the end-to-end public-docs
    correctness contract for the example, kept whole on purpose.
    """
    result = _run("sample_renames_v1.ttl", "sample_renames_v2.ttl")
    structural = _structural(result)

    renames = [c for c in structural if c.kind == "class_renamed"]
    assert len(renames) == 1
    change = renames[0]
    assert change.details["before_iri"] == f"{_EX}Vehicle"
    assert change.details["after_iri"] == f"{_EX}MotorVehicle"
    assert change.details["confidence"] == "high"

    # The ex:Car reparent and the ex:Garage restriction filler both ride with the
    # rename (cascade subsumption) rather than surfacing as standalone changes.
    assert len(change.details["cascade_subsumes"]) == 2
    leftover = {"class_added", "class_removed", "class_reparented", "restriction_changed"}
    assert not [c for c in structural if c.kind in leftover]

    # And Layer 0 is fully explained.
    assert _unexplained_layer0(result) == []
