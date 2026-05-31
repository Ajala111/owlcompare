"""Tests for the shared subsumption registry — specs/06-structural-entities.md."""

from __future__ import annotations

from owlcompare.diff._common import Change
from owlcompare.diff._subsumption import SubsumptionRegistry


def _layer0_change(summary: str = "Added: ex:a ex:p ex:o") -> Change:
    """A Layer 0 change with its change_id populated, like syntactic.diff emits."""
    change = Change(
        layer="syntactic",
        kind="triple_added",
        severity="additive",
        subject="http://example.org/a",
        summary=summary,
        details={
            "subject_iri": "http://example.org/a",
            "predicate_iri": "http://example.org/p",
            "object": "ex:o",
        },
    )
    change.details["change_id"] = SubsumptionRegistry.change_id(change)
    return change


def test_change_id_is_deterministic():
    first = _layer0_change()
    second = _layer0_change()
    assert SubsumptionRegistry.change_id(first) == SubsumptionRegistry.change_id(second)


def test_change_id_includes_layer_and_kind():
    change = _layer0_change()
    assert SubsumptionRegistry.change_id(change).startswith("syntactic:triple_added:")


def test_register_marks_layer0_changes_explained():
    registry = SubsumptionRegistry()
    change = _layer0_change()
    registry.register("structural:class_added:abc", [change])
    assert registry.is_explained(change.details["change_id"])


def test_is_explained_false_for_unregistered():
    registry = SubsumptionRegistry()
    assert not registry.is_explained("structural:class_added:never-seen")


def test_explainers_returns_all_higher_layer_ids():
    registry = SubsumptionRegistry()
    change = _layer0_change()
    registry.register("structural:class_added:one", [change])
    registry.register("structural:object_property_added:two", [change])
    explainers = registry.explainers(change.details["change_id"])
    assert set(explainers) == {
        "structural:class_added:one",
        "structural:object_property_added:two",
    }
