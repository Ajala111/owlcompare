"""Unit tests for post-rename axiom re-diffing (DD-018 fix) — specs/12-rename-refinements.md."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import rename
from owlcompare.diff._common import DiffResult
from owlcompare.diff.orchestrator import run
from owlcompare.loader import load

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "rename"
REDIDIFF = FIXTURES / "redidiff"

_TRACK = "http://data.europa.eu/949/Track"
_RAILWAY_TRACK = "http://data.europa.eu/949/RailwayTrack"
_RAILWAY_SIGNAL = "http://data.europa.eu/949/RailwaySignal"


def _pre_rename(v1: str, v2: str) -> DiffResult:
    """The Layer-1 DiffResult before rename detection or severity refinement."""
    a = canonicalize(load(str(REDIDIFF / v1)))
    b = canonicalize(load(str(REDIDIFF / v2)))
    return run(a, b, detect_renames=False, refine_severity=False)


def _detect(v1: str, v2: str, **kwargs) -> DiffResult:
    return rename.detect(_pre_rename(v1, v2), **kwargs)


def _kinds(result: DiffResult) -> list[str]:
    return sorted(c.kind for c in result.changes if c.layer == "structural")


# --------------------------------------------------------------------------- #
# Re-diff surfacing per kind
# --------------------------------------------------------------------------- #


def test_redidiff_pure_rename_emits_no_new_changes():
    # Regression canary: a clean rename must not produce phantom re-diff changes.
    out = _detect(
        "rename_pure_no_structural_change_v1.ttl", "rename_pure_no_structural_change_v2.ttl"
    )
    assert _kinds(out) == ["class_renamed"]


def test_redidiff_rename_plus_restriction_emits_restriction_added():
    out = _detect("rename_plus_new_restriction_v1.ttl", "rename_plus_new_restriction_v2.ttl")
    added = [c for c in out.changes if c.kind == "restriction_added"]
    assert len(added) == 1
    assert len([c for c in out.changes if c.kind == "class_renamed"]) == 1


def test_redidiff_rename_plus_removed_annotation_emits_annotation_removed():
    out = _detect("rename_plus_removed_annotation_v1.ttl", "rename_plus_removed_annotation_v2.ttl")
    removed = [c for c in out.changes if c.kind == "annotation_removed"]
    assert len(removed) == 1
    assert removed[0].details["language"] == "fr"


def test_redidiff_rename_plus_new_parent_emits_class_parent_added():
    out = _detect("rename_plus_new_parent_v1.ttl", "rename_plus_new_parent_v2.ttl")
    parent_added = [c for c in out.changes if c.kind == "class_parent_added"]
    assert len(parent_added) == 1
    assert parent_added[0].details["parent_iri"] == "http://data.europa.eu/949/Infrastructure"


def test_redidiff_rename_plus_swapped_restriction_emits_restriction_changed():
    out = _detect(
        "rename_plus_swapped_restriction_v1.ttl", "rename_plus_swapped_restriction_v2.ttl"
    )
    changed = [c for c in out.changes if c.kind == "restriction_changed"]
    assert len(changed) == 1


# --------------------------------------------------------------------------- #
# Re-diffed change shape & bookkeeping
# --------------------------------------------------------------------------- #


def test_redidiff_new_change_subject_is_after_iri_not_before():
    out = _detect("rename_plus_new_restriction_v1.ttl", "rename_plus_new_restriction_v2.ttl")
    added = next(c for c in out.changes if c.kind == "restriction_added")
    assert added.subject == _RAILWAY_TRACK
    assert added.subject != _TRACK


def test_redidiff_new_change_appears_in_rename_cascade_subsumes():
    out = _detect("rename_plus_new_restriction_v1.ttl", "rename_plus_new_restriction_v2.ttl")
    added = next(c for c in out.changes if c.kind == "restriction_added")
    renamed = next(c for c in out.changes if c.kind == "class_renamed")
    assert added.details["change_id"] in renamed.details["cascade_subsumes"]


def test_redidiff_new_change_has_fresh_change_id():
    out = _detect("rename_plus_new_restriction_v1.ttl", "rename_plus_new_restriction_v2.ttl")
    added = next(c for c in out.changes if c.kind == "restriction_added")
    assert isinstance(added.details.get("change_id"), str)
    ids = [c.details["change_id"] for c in out.changes if "change_id" in c.details]
    assert len(ids) == len(set(ids))  # no collisions


def test_redidiff_new_change_severity_matches_layer1_slice_default():
    # restriction_added is breaking exactly as Component 08 would have rated it.
    out = _detect("rename_plus_new_restriction_v1.ttl", "rename_plus_new_restriction_v2.ttl")
    added = next(c for c in out.changes if c.kind == "restriction_added")
    assert added.severity == "breaking"


def test_redidiff_multiple_renames_independent():
    out = _detect("era_rename_with_additions_v1.ttl", "era_rename_with_additions_v2.ttl")
    assert len([c for c in out.changes if c.kind == "class_renamed"]) == 2
    assert len([c for c in out.changes if c.kind == "restriction_added"]) == 1
    assert len([c for c in out.changes if c.kind == "annotation_removed"]) == 1
    # Each addition is recorded under its own rename, not mixed up.
    track = next(
        c for c in out.changes if c.kind == "class_renamed" and c.subject == _RAILWAY_TRACK
    )
    signal = next(
        c for c in out.changes if c.kind == "class_renamed" and c.subject == _RAILWAY_SIGNAL
    )
    added = next(c for c in out.changes if c.kind == "restriction_added")
    removed = next(c for c in out.changes if c.kind == "annotation_removed")
    assert added.details["change_id"] in track.details["cascade_subsumes"]
    assert removed.details["change_id"] in signal.details["cascade_subsumes"]


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #


def test_redidiff_does_not_mutate_input_result():
    result = _detect("rename_plus_new_restriction_v1.ttl", "rename_plus_new_restriction_v2.ttl")
    before_changes = result.changes
    renamed_before = dict(next(c for c in result.changes if c.kind == "class_renamed").details)
    rename.re_diff_renamed_entities(result, result.a, result.b)
    assert result.changes is before_changes
    renamed_after = next(c for c in result.changes if c.kind == "class_renamed")
    assert renamed_after.details == renamed_before


def test_redidiff_no_renames_returns_result_unchanged():
    a = canonicalize(load(str(FIXTURES / "no_rename_just_replacement_v1.ttl")))
    b = canonicalize(load(str(FIXTURES / "no_rename_just_replacement_v2.ttl")))
    consolidated = rename.detect(run(a, b, detect_renames=False, refine_severity=False))
    assert consolidated.metadata["renames_applied"] == ()
    out = rename.re_diff_renamed_entities(consolidated, a, b)
    assert out is consolidated
