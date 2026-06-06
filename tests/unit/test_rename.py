"""Unit tests for rename detection and cascade consolidation — specs/11-rename-detection.md."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import rename
from owlcompare.diff._common import Change, DiffResult
from owlcompare.diff.orchestrator import run
from owlcompare.loader import load
from owlcompare.rename_mapping import RenameMapping

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "rename"

_TRACK = "http://data.europa.eu/949/Track"
_RAILWAY_TRACK = "http://data.europa.eu/949/RailwayTrack"
_STEEL_TRACK = "http://data.europa.eu/949/SteelTrack"
_LOCATED_ON = "http://data.europa.eu/949/locatedOn"
_HAS_LOCATION = "http://data.europa.eu/949/hasLocation"


def _pre_rename(v1: str, v2: str) -> DiffResult:
    """The Layer-1 DiffResult *before* rename detection or severity refinement."""
    a = canonicalize(load(str(FIXTURES / v1)))
    b = canonicalize(load(str(FIXTURES / v2)))
    return run(a, b, detect_renames=False, refine_severity=False)


def _kinds(result: DiffResult) -> list[str]:
    return sorted(c.kind for c in result.changes if c.layer == "structural")


def _renamed(result: DiffResult) -> list[Change]:
    return [c for c in result.changes if c.kind.endswith("_renamed")]


# --------------------------------------------------------------------------- #
# Basic behaviour
# --------------------------------------------------------------------------- #


def test_detect_no_changes_returns_unchanged():
    a = canonicalize(load(str(FIXTURES / "simple_class_rename_v1.ttl")))
    result = run(a, a, detect_renames=False, refine_severity=False)
    out = rename.detect(result)
    assert out.changes == result.changes
    assert out.metadata["renames_applied"] == ()


def test_detect_does_not_mutate_input():
    result = _pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl")
    before = result.changes
    rename.detect(result)
    assert result.changes is before
    assert any(c.kind == "class_removed" for c in result.changes)


def test_detect_user_mapping_certain_confidence():
    result = _pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl")
    mapping = RenameMapping(classes=((_TRACK, _RAILWAY_TRACK),))
    out = rename.detect(result, mapping, min_confidence="certain")
    renamed = _renamed(out)
    assert len(renamed) == 1
    assert renamed[0].details["confidence"] == "certain"
    assert renamed[0].details["evidence"] == ["user-supplied mapping"]


def test_detect_user_mapping_stale_iri_logged_silently():
    result = _pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl")
    mapping = RenameMapping(classes=(("urn:stale:old", "urn:stale:new"),))
    out = rename.detect(result, mapping, min_confidence="certain")
    # Stale entry skipped, no rename, no error.
    assert _renamed(out) == []


def test_detect_label_match_high_confidence():
    result = _pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl")
    out = rename.detect(result, min_confidence="high")
    renamed = _renamed(out)
    assert len(renamed) == 1
    assert renamed[0].details["confidence"] == "high"
    assert renamed[0].details["before_iri"] == _TRACK
    assert renamed[0].details["after_iri"] == _RAILWAY_TRACK


def test_detect_label_match_ambiguous_no_rename_emitted():
    result = _pre_rename("ambiguous_label_match_v1.ttl", "ambiguous_label_match_v2.ttl")
    out = rename.detect(result, min_confidence="high")
    assert _renamed(out) == []
    assert _kinds(out) == ["class_added", "class_added", "class_removed"]


def test_detect_fingerprint_match_medium_confidence():
    result = _pre_rename("fingerprint_rename_v1.ttl", "fingerprint_rename_v2.ttl")
    out = rename.detect(result, min_confidence="medium")
    renamed = _renamed(out)
    assert len(renamed) == 1
    assert renamed[0].details["confidence"] == "medium"
    assert renamed[0].details["score"] >= 0.6


def test_detect_fingerprint_match_score_threshold_not_met_no_rename():
    # no_rename has no structural overlap → best score below the 0.6 acceptance.
    result = _pre_rename("no_rename_just_replacement_v1.ttl", "no_rename_just_replacement_v2.ttl")
    out = rename.detect(result, min_confidence="medium")
    assert _renamed(out) == []


def test_detect_fingerprint_match_separation_threshold_enforced():
    # ambiguous: the removed class scores equally against two added classes
    # (one shared label each), so neither clears the 0.2 separation requirement.
    result = _pre_rename("ambiguous_label_match_v1.ttl", "ambiguous_label_match_v2.ttl")
    out = rename.detect(result, min_confidence="medium")
    assert _renamed(out) == []


# --------------------------------------------------------------------------- #
# Confidence floor
# --------------------------------------------------------------------------- #


def test_detect_min_confidence_certain_rejects_label_matches():
    result = _pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl")
    out = rename.detect(result, min_confidence="certain")
    assert _renamed(out) == []


def test_detect_min_confidence_high_default_accepts_user_and_label():
    result = _pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl")
    out = rename.detect(result)  # default high
    assert len(_renamed(out)) == 1


def test_detect_min_confidence_medium_accepts_fingerprint():
    result = _pre_rename("fingerprint_rename_v1.ttl", "fingerprint_rename_v2.ttl")
    assert _renamed(rename.detect(result, min_confidence="high")) == []
    assert len(_renamed(rename.detect(result, min_confidence="medium"))) == 1


def test_detect_min_confidence_none_skips_detection():
    # The orchestrator owns the 'none' skip; detect itself is simply never called.
    a = canonicalize(load(str(FIXTURES / "simple_class_rename_v1.ttl")))
    b = canonicalize(load(str(FIXTURES / "simple_class_rename_v2.ttl")))
    out = run(a, b, detect_renames=False)
    assert [c for c in out.changes if c.kind.endswith("_renamed")] == []
    assert "renames_applied" not in out.metadata


# --------------------------------------------------------------------------- #
# Emitted change shape
# --------------------------------------------------------------------------- #


def test_rename_emits_class_renamed_change():
    out = rename.detect(_pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl"))
    renamed = _renamed(out)
    assert renamed[0].kind == "class_renamed"
    assert renamed[0].subject == _RAILWAY_TRACK


def test_rename_emits_property_renamed_change():
    out = rename.detect(_pre_rename("property_rename_v1.ttl", "property_rename_v2.ttl"))
    renamed = _renamed(out)
    assert len(renamed) == 1
    assert renamed[0].kind == "object_property_renamed"
    assert renamed[0].details["before_iri"] == _LOCATED_ON
    assert renamed[0].details["after_iri"] == _HAS_LOCATION


def test_rename_subsumes_original_added_and_removed_changes():
    out = rename.detect(_pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl"))
    assert not any(c.kind == "class_added" for c in out.changes)
    assert not any(c.kind == "class_removed" for c in out.changes)
    assert len(_renamed(out)[0].details["subsumes"]) == 2


def test_rename_subsumes_list_is_sorted():
    # DD-021: a rename record's subsumes (primary add+remove pair) is sorted.
    out = rename.detect(_pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl"))
    subsumes = _renamed(out)[0].details["subsumes"]
    assert len(subsumes) >= 2  # a meaningful order check needs >1 element
    assert subsumes == sorted(subsumes)


def test_rename_severity_is_info():
    out = rename.detect(_pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl"))
    assert _renamed(out)[0].severity == "info"


def test_rename_summary_includes_confidence():
    out = rename.detect(_pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl"))
    assert "high" in _renamed(out)[0].summary


def test_rename_details_includes_before_iri_after_iri_evidence():
    out = rename.detect(_pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl"))
    details = _renamed(out)[0].details
    assert details["before_iri"] == _TRACK
    assert details["after_iri"] == _RAILWAY_TRACK
    assert details["evidence"] == ['matching label "Track"@en']


# --------------------------------------------------------------------------- #
# Cascade consolidation
# --------------------------------------------------------------------------- #


def test_cascade_consolidates_referencing_subclass_pair():
    result = _pre_rename("cascade_simple_v1.ttl", "cascade_simple_v2.ttl")
    # Before detection the Tunnel reparent is present.
    assert any(c.kind == "class_reparented" for c in result.changes)
    out = rename.detect(result)
    assert not any(c.kind == "class_reparented" for c in out.changes)
    reparent_id = next(
        c.details["change_id"] for c in result.changes if c.kind == "class_reparented"
    )
    assert reparent_id in _renamed(out)[0].details["cascade_subsumes"]


def test_cascade_consolidates_referencing_domain_range_pair():
    result = _pre_rename("cascade_simple_v1.ttl", "cascade_simple_v2.ttl")
    assert any(c.kind == "range_changed" for c in result.changes)
    out = rename.detect(result)
    assert not any(c.kind == "range_changed" for c in out.changes)
    range_id = next(c.details["change_id"] for c in result.changes if c.kind == "range_changed")
    assert range_id in _renamed(out)[0].details["cascade_subsumes"]


def test_cascade_preserves_independent_changes():
    out = rename.detect(
        _pre_rename(
            "class_rename_with_new_restriction_v1.ttl",
            "class_rename_with_new_restriction_v2.ttl",
        )
    )
    # The genuinely new restriction on the persisting era:Platform survives.
    assert any(c.kind == "restriction_added" for c in out.changes)
    assert len(_renamed(out)) == 1


def test_cascade_subsumes_list_is_sorted():
    # DD-021: a rename record's cascade_subsumes array is sorted (subclass + range).
    out = rename.detect(_pre_rename("cascade_simple_v1.ttl", "cascade_simple_v2.ttl"))
    cascade = _renamed(out)[0].details["cascade_subsumes"]
    assert len(cascade) >= 2  # a meaningful order check needs >1 element
    assert cascade == sorted(cascade)


# --------------------------------------------------------------------------- #
# Guards & metadata
# --------------------------------------------------------------------------- #


def test_rename_does_not_pair_across_kinds():
    result = _pre_rename("cross_kind_v1.ttl", "cross_kind_v2.ttl")
    out = rename.detect(result, min_confidence="medium")
    assert _renamed(out) == []
    assert _kinds(out) == ["class_removed", "object_property_added"]


def test_rename_skips_restriction_urn_subjects():
    synthetic = Change(
        layer="structural",
        kind="class_removed",
        severity="breaking",
        subject="urn:owlcompare:restriction:" + "0" * 64,
        summary="synthetic",
        details={"change_id": "x"},
    )
    index = rename._build_candidate_index([synthetic])
    assert index.removed_by_kind["class"] == {}


def test_user_mapping_overrides_heuristic_pairing():
    result = _pre_rename("mapping_override_v1.ttl", "mapping_override_v2.ttl")
    mapping = RenameMapping(classes=((_TRACK, _STEEL_TRACK),))
    out = rename.detect(result, mapping, min_confidence="high")
    renamed = _renamed(out)
    assert len(renamed) == 1
    assert renamed[0].details["after_iri"] == _STEEL_TRACK
    # RailwayTrack (the heuristic's pick) is left as a plain addition.
    assert any(c.kind == "class_added" and c.subject == _RAILWAY_TRACK for c in out.changes)


def test_rename_metadata_includes_candidates_and_applied():
    out = rename.detect(_pre_rename("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl"))
    assert "rename_candidates" in out.metadata
    assert "renames_applied" in out.metadata
    applied = out.metadata["renames_applied"]
    candidates = out.metadata["rename_candidates"]
    assert len(applied) == 1
    assert set(applied).issubset(set(candidates))
