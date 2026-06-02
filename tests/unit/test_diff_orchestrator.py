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


HIER = DIFF / "hierarchy"


def _canon_hier(name: str) -> OntologySnapshot:
    return canonicalize(load(str(HIER / name)))


def test_orchestrator_runs_hierarchy_after_entities():
    # era_hierarchy reparents era:Signal; only the hierarchy slice emits that.
    result = orchestrator.run(
        _canon_hier("era_hierarchy_v1.ttl"), _canon_hier("era_hierarchy_v2.ttl")
    )
    assert any(c.layer == "structural" and c.kind == "class_reparented" for c in result.changes)


def test_orchestrator_layer1_changes_include_both_entities_and_hierarchy():
    result = orchestrator.run(
        _canon_hier("era_hierarchy_v1.ttl"), _canon_hier("era_hierarchy_v2.ttl")
    )
    kinds = {c.kind for c in result.changes if c.layer == "structural"}
    assert "class_added" in kinds  # entities slice (era:Asset)
    assert "class_reparented" in kinds  # hierarchy slice (era:Signal)


def test_orchestrator_diffresult_metadata_counts_hierarchy_changes():
    result = orchestrator.run(
        _canon_hier("era_hierarchy_v1.ttl"), _canon_hier("era_hierarchy_v2.ttl")
    )
    structural = [c for c in result.changes if c.layer == "structural"]
    assert result.metadata["layer_counts"]["structural"] == len(structural)


RESTR = DIFF / "restrictions"


def _canon_restr(name: str) -> OntologySnapshot:
    return canonicalize(load(str(RESTR / name)))


def _run_restr():
    return orchestrator.run(
        _canon_restr("era_restrictions_v1.ttl"), _canon_restr("era_restrictions_v2.ttl")
    )


def test_orchestrator_runs_restrictions_after_hierarchy():
    # era_restrictions has no hierarchy changes; only the restriction slice emits
    # restriction_* kinds, confirming it ran as part of the pipeline.
    result = _run_restr()
    assert any(c.layer == "structural" and c.kind == "restriction_changed" for c in result.changes)


def test_orchestrator_layer1_changes_include_restrictions():
    result = _run_restr()
    kinds = {c.kind for c in result.changes if c.layer == "structural"}
    assert {"restriction_changed", "restriction_added", "restriction_removed"} <= kinds


def test_orchestrator_diffresult_metadata_counts_restriction_changes():
    result = _run_restr()
    structural = [c for c in result.changes if c.layer == "structural"]
    assert result.metadata["layer_counts"]["structural"] == len(structural)
    assert len([c for c in structural if c.kind.startswith("restriction_")]) == 3
