"""Acceptance tests for the dcterms:isReplacedBy diff — specs/12.5 § Part 4."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import orchestrator, syntactic
from owlcompare.diff._common import Change
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.rename import RenameCandidate
from owlcompare.diff.structural import (
    annotations as annotations_slice,
)
from owlcompare.diff.structural import (
    class_sets,
    entities,
    hierarchy,
    replaced_by,
    restrictions,
)
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ANON = FIXTURES / "anonstruct"

ERA = "http://data.europa.eu/949/"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(ANON / name)))


def _run(before: str, after: str, renames: tuple = ()) -> list[Change]:
    """Run the Layer 1 pipeline through annotations, then the replaced_by slice."""
    a, b = _canon(before), _canon(after)
    layer0 = syntactic.diff(a, b)
    registry = SubsumptionRegistry()
    entities.diff(a, b, layer0, registry)
    hierarchy.diff(a, b, layer0, registry)
    restrictions.diff(a, b, layer0, registry)
    class_sets.diff(a, b, layer0, registry)
    annotations_slice.diff(a, b, layer0, registry)
    return replaced_by.diff(a, b, layer0, registry, renames)


def _one(changes: list[Change], kind: str) -> Change:
    matches = [c for c in changes if c.kind == kind]
    assert len(matches) == 1, f"expected one {kind}, got {[c.kind for c in changes]}"
    return matches[0]


def _rename(old: str, new: str) -> RenameCandidate:
    return RenameCandidate(
        removed_iri=old,
        added_iri=new,
        entity_kind="class",
        confidence="high",
        evidence=(),
        score=1.0,
    )


def test_replaced_by_added_emits_replaced_by_set():
    changes = _run("replaced_by_added_v1.ttl", "replaced_by_added_v2.ttl")
    change = _one(changes, "replaced_by_set")
    assert change.details["entity_iri"] == ERA + "TSIMagneticFields"
    assert change.details["target_iri"] == ERA + "tsiMagneticFields"


def test_replaced_by_severity_non_breaking():
    changes = _run("replaced_by_added_v1.ttl", "replaced_by_added_v2.ttl")
    assert _one(changes, "replaced_by_set").severity == "non_breaking"


def test_replaced_by_with_matching_rename_sets_flag_true():
    renames = (_rename(ERA + "TSIMagneticFields", ERA + "tsiMagneticFields"),)
    changes = _run(
        "replaced_by_with_consistent_rename_v1.ttl",
        "replaced_by_with_consistent_rename_v2.ttl",
        renames,
    )
    assert _one(changes, "replaced_by_set").details["matches_detected_rename"] is True


def test_replaced_by_without_matching_rename_sets_flag_false():
    changes = _run(
        "replaced_by_with_inconsistent_rename_v1.ttl",
        "replaced_by_with_inconsistent_rename_v2.ttl",
    )
    assert _one(changes, "replaced_by_set").details["matches_detected_rename"] is False


def test_replaced_by_removed_emits_replaced_by_unset():
    # replaced_by_added reversed: the assertion is withdrawn.
    changes = _run("replaced_by_added_v2.ttl", "replaced_by_added_v1.ttl")
    assert _one(changes, "replaced_by_unset").severity == "info"


def test_replaced_by_promotes_existing_annotation_change():
    # Through the full orchestrator, the annotation_added the annotation slice
    # emits for the dcterms:isReplacedBy triple is retracted and replaced.
    a = load(str(ANON / "replaced_by_added_v1.ttl"))
    b = load(str(ANON / "replaced_by_added_v2.ttl"))
    result = orchestrator.run(a, b)
    kinds = {c.kind for c in result.changes}
    assert "replaced_by_set" in kinds
    is_replaced_by = "http://purl.org/dc/terms/isReplacedBy"
    assert not any(
        c.kind in ("annotation_added", "annotation_removed", "annotation_changed")
        and c.details.get("predicate_iri") == is_replaced_by
        for c in result.changes
    )


def test_replaced_by_does_not_emit_when_entity_was_removed_entirely():
    changes = _run("replaced_by_entity_removed_v1.ttl", "replaced_by_entity_removed_v2.ttl")
    assert changes == []
