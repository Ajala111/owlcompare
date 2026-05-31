"""Acceptance tests for the shared diff types — specs/05-syntactic-diff.md."""

from __future__ import annotations

import dataclasses

import pytest

from owlcompare.diff import Change, DiffOptions, DiffResult


def _make_change(**overrides) -> Change:
    base = {
        "layer": "syntactic",
        "kind": "triple_added",
        "severity": "additive",
        "subject": "http://example.org/Foo",
        "summary": "Added: ex:Foo a owl:Class",
    }
    base.update(overrides)
    return Change(**base)


def test_change_is_frozen():
    change = _make_change()
    with pytest.raises(dataclasses.FrozenInstanceError):
        change.kind = "triple_removed"  # type: ignore[misc]


def test_change_is_hashable():
    change = _make_change(details={"predicate_iri": "http://x"})
    # Hashable -> usable in sets/dicts; details/before/after are excluded from hash.
    assert hash(change) == hash(_make_change(details={"predicate_iri": "http://x"}))
    assert {change}  # would raise TypeError if unhashable


def test_change_default_details_is_empty_dict():
    change = _make_change()
    assert change.details == {}
    assert change.before is None
    assert change.after is None


def test_diff_options_defaults_include_all_four_layers():
    assert DiffOptions().include_layers == (
        "syntactic",
        "structural",
        "inferential",
        "impact",
    )


def test_diff_result_changes_is_tuple_not_list():
    result = DiffResult(a=object(), b=object(), changes=(_make_change(),))  # type: ignore[arg-type]
    assert isinstance(result.changes, tuple)
