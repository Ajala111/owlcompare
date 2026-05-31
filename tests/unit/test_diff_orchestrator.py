"""Acceptance tests for the diff orchestrator — specs/06-structural-entities.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import orchestrator
from owlcompare.diff._common import DiffOptions
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.exceptions import DiffError
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"


def _load(name: str) -> OntologySnapshot:
    return load(str(DIFF / name))


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(_load(name))


def test_orchestrator_canonicalizes_non_canonical_inputs():
    a, b = _load("class_added_before.ttl"), _load("class_added_after.ttl")
    assert not a.canonical and not b.canonical
    result = orchestrator.run(a, b)
    assert result.a.canonical and result.b.canonical


def test_orchestrator_passes_canonical_inputs_through():
    a, b = _canon("class_added_before.ttl"), _canon("class_added_after.ttl")
    result = orchestrator.run(a, b)
    # Already canonical → same objects, no re-canonicalization.
    assert result.a is a
    assert result.b is b


def test_orchestrator_runs_layer0_always():
    result = orchestrator.run(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    assert any(c.layer == "syntactic" for c in result.changes)


def test_orchestrator_runs_layer1_entities_by_default():
    result = orchestrator.run(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    assert any(c.layer == "structural" for c in result.changes)


def test_orchestrator_returns_diffresult_with_combined_changes():
    result = orchestrator.run(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    layers = {c.layer for c in result.changes}
    assert layers == {"syntactic", "structural"}


def test_orchestrator_diffresult_metadata_includes_layer_counts():
    result = orchestrator.run(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    counts = result.metadata["layer_counts"]
    assert counts["syntactic"] == sum(1 for c in result.changes if c.layer == "syntactic")
    assert counts["structural"] == sum(1 for c in result.changes if c.layer == "structural")


def test_orchestrator_subsumption_registry_attached_to_metadata():
    result = orchestrator.run(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    assert isinstance(result.metadata["subsumption_registry"], SubsumptionRegistry)


def test_orchestrator_with_only_syntactic_layer_skips_structural():
    result = orchestrator.run(
        _canon("class_added_before.ttl"),
        _canon("class_added_after.ttl"),
        DiffOptions(include_layers=("syntactic",)),
    )
    assert all(c.layer == "syntactic" for c in result.changes)
    assert "structural" not in result.metadata["layer_counts"]


def test_orchestrator_with_only_structural_layer_still_runs_syntactic():
    # Layer 1 depends on Layer 0, so requesting structural without syntactic is
    # an explicit error rather than a silent partial run.
    with pytest.raises(DiffError):
        orchestrator.run(
            _canon("class_added_before.ttl"),
            _canon("class_added_after.ttl"),
            DiffOptions(include_layers=("structural",)),
        )
