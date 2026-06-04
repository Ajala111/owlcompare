"""Acceptance tests for the Markdown report — specs/15-markdown-report.md.

The ``_format_change`` tests build ``Change`` objects directly so each per-kind
template is pinned in isolation. The ``test_render_golden_*`` tests assert
byte-for-byte equality against ``tests/fixtures/markdown/*.md`` — those golden
files are the locked contract, so any change to rendering breaks them on purpose.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import orchestrator
from owlcompare.diff._common import Change, DiffResult
from owlcompare.loader import load
from owlcompare.report._markdown_helpers import (
    escape_markdown,
    normalize_source,
    severity_icon,
)
from owlcompare.report.markdown_report import MarkdownOptions, _format_change, render

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"
RENAME = FIXTURES / "rename"
GOLDEN = FIXTURES / "markdown"

_ERA = {"era": "http://data.europa.eu/949/"}
_SPECIALS = ["*", "_", "~", "`", "[", "]", "(", ")", "<", ">", "\\", "|"]


# --------------------------------------------------------------------------- #
# Result builders (sources overridden so goldens stay machine-independent)
# --------------------------------------------------------------------------- #


def _result(name_a: str, name_b: str, base: Path = DIFF, **run_kwargs: object) -> DiffResult:
    a = dataclasses.replace(load(str(base / name_a)), source=name_a)
    b = dataclasses.replace(load(str(base / name_b)), source=name_b)
    return orchestrator.run(a, b, **run_kwargs)  # type: ignore[arg-type]


def _truncation_result(count: int = 55) -> DiffResult:
    """A synthetic diff with ``count`` class_added changes in one section."""
    snapshot = dataclasses.replace(
        canonicalize(load(str(DIFF / "escaping_specials_before.ttl"))), source="big_a.ttl"
    )
    snapshot_b = dataclasses.replace(snapshot, source="big_b.ttl")
    changes = tuple(
        Change(
            layer="structural",
            kind="class_added",
            severity="additive",
            subject=f"http://example.org/C{i:02d}",
            summary=f"Class added: ex:C{i:02d}",
            details={
                "entity_iri": f"http://example.org/C{i:02d}",
                "entity_kind": "class",
                "label": f"Class {i:02d}",
                "language": "en",
            },
        )
        for i in range(count)
    )
    return DiffResult(a=snapshot, b=snapshot_b, changes=changes, metadata={})


def _change(kind: str, severity: str = "additive", summary: str = "", **details: object) -> Change:
    return Change(
        layer="structural",
        kind=kind,
        severity=severity,  # type: ignore[arg-type]
        subject=str(details.get("entity_iri") or details.get("before_iri") or ""),
        summary=summary,
        details=details,
    )


# --------------------------------------------------------------------------- #
# Title / header
# --------------------------------------------------------------------------- #


def test_render_empty_diff_returns_header_only():
    out = render(_result("identical_a.ttl", "identical_b.ttl"))
    assert "owlcompare diff: no changes" in out
    assert "###" not in out  # no sections at all
    assert out.startswith("## ")


def test_render_title_includes_breaking_count_when_positive():
    out = render(_result("removed_class_before.ttl", "removed_class_after.ttl"))
    assert out.startswith("## 🔴 owlcompare diff: 1 breaking change\n")


def test_render_title_says_no_breaking_changes_when_only_non_breaking():
    out = render(_result("escaping_specials_before.ttl", "escaping_specials_after.ttl"))
    assert "🟢 owlcompare diff: no breaking changes" in out


def test_render_title_says_no_changes_when_empty():
    out = render(_result("identical_a.ttl", "identical_b.ttl"))
    assert "⚪ owlcompare diff: no changes" in out


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #


def test_render_renames_section_appears_when_renames_present():
    out = render(_result("era_renames_v1.ttl", "era_renames_v2.ttl", base=RENAME))
    assert "### Renames (3)" in out
    assert "✏️" in out


def test_render_renames_section_omitted_when_no_renames():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert "### Renames" not in out


def test_render_breaking_section_appears_when_breaking_changes_present():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert "### Breaking changes (1)" in out
    assert "**Object property removed:** `era:locatedOn`" in out


def test_render_other_changes_section_groups_non_breaking_additive_info():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert "### Other changes (4)" in out
    # additive (class added), non_breaking (restriction), info (label) all together
    assert "🟢 **Class added:**" in out
    assert "🟡 **Restriction changed on**" in out
    assert "⚪ **Label changed**" in out


def test_render_collapsed_layer0_section_appears_when_unsubsumed_present():
    out = render(_result("unexplained_layer0_before.ttl", "unexplained_layer0_after.ttl"))
    assert "<details>" in out
    assert "<summary>📜 2 unexplained Layer 0 changes</summary>" in out
    assert "</details>" in out


def test_render_collapsed_layer0_section_omitted_when_empty():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert "<details>" not in out


def test_render_collapsed_layer0_section_suppressed_by_option():
    result = _result("unexplained_layer0_before.ttl", "unexplained_layer0_after.ttl")
    out = render(result, MarkdownOptions(include_layer0_collapsed=False))
    assert "<details>" not in out


# --------------------------------------------------------------------------- #
# Footer / options
# --------------------------------------------------------------------------- #


def test_render_footer_included_by_default():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert out.rstrip().endswith("machine-readable output*")
    assert "Generated by owlcompare" in out


def test_render_footer_omitted_when_disabled():
    result = _result("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    out = render(result, MarkdownOptions(include_footer=False))
    assert "Generated by owlcompare" not in out
    assert "---" not in out


def test_render_heading_level_respected():
    result = _result("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    for level, hashes in ((1, "# "), (3, "### "), (4, "#### ")):
        out = render(result, MarkdownOptions(heading_level=level))
        assert out.startswith(f"{hashes}🔴 owlcompare diff:")


def test_render_heading_level_invalid_defaults_to_2():
    result = _result("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    for level in (0, -1, 5, 6):
        out = render(result, MarkdownOptions(heading_level=level))
        assert out.startswith("## 🔴 owlcompare diff:")


def test_render_uses_emoji_by_default():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert "🔴" in out
    assert "[BREAKING]" not in out


def test_render_uses_plain_severity_tags_when_emoji_disabled():
    result = _result("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    out = render(result, MarkdownOptions(emoji_style="plain"))
    assert "[BREAKING]" in out
    assert "[ADDITIVE]" in out
    assert "🔴" not in out


def test_render_truncates_long_sections_with_marker():
    out = render(_truncation_result(55))
    assert "### Other changes (55)" in out
    assert "- ...and 5 more (see JSON output for full list)" in out
    assert out.count("\n- ") == 50 + 1  # 50 bullets + the truncation marker bullet


# --------------------------------------------------------------------------- #
# Per-kind formatting (_format_change)
# --------------------------------------------------------------------------- #


def test_format_change_class_added():
    change = _change(
        "class_added",
        entity_iri="http://data.europa.eu/949/Platform",
        label="Platform",
        language="en",
    )
    assert _format_change(change, _ERA) == '**Class added:** `era:Platform` *"Platform"@en*'


def test_format_change_class_renamed_includes_confidence():
    change = _change(
        "class_renamed",
        before_iri="http://data.europa.eu/949/Track",
        after_iri="http://data.europa.eu/949/RailwayTrack",
        entity_kind="class",
        confidence="high",
        evidence=['matching label "Track"@en'],
    )
    body = _format_change(change, _ERA)
    assert body == (
        "**Class renamed:** `era:Track` → `era:RailwayTrack` "
        '*(high confidence — matching label "Track"@en)*'
    )


def test_format_change_class_renamed_certain_has_no_confidence_word():
    change = _change(
        "class_renamed",
        before_iri="http://data.europa.eu/949/Signal",
        after_iri="http://data.europa.eu/949/RailwaySignal",
        entity_kind="class",
        confidence="certain",
        evidence=["user-supplied mapping"],
    )
    assert "*(certain — user-supplied mapping)*" in _format_change(change, _ERA)


def test_format_change_restriction_changed_uses_arrow():
    change = _change(
        "restriction_changed",
        severity="non_breaking",
        summary="Restriction changed on era:Track: era:hasMaxSpeed max 1 → max 2",
        entity_iri="http://data.europa.eu/949/Track",
    )
    body = _format_change(change, _ERA)
    assert body == "**Restriction changed on** `era:Track`: `era:hasMaxSpeed max 1 → max 2`"
    assert "→" in body


def test_format_change_class_reparented_includes_direction():
    change = _change(
        "class_reparented",
        severity="non_breaking",
        entity_iri="http://data.europa.eu/949/Track",
        parents_before=["http://data.europa.eu/949/Asset"],
        parents_after=["http://data.europa.eu/949/Infrastructure"],
        direction="specialization",
    )
    body = _format_change(change, _ERA)
    assert body == (
        "**Class reparented:** `era:Track`: era:Asset → era:Infrastructure (specialization)"
    )


def test_format_change_annotation_changed_includes_language():
    change = _change(
        "annotation_changed",
        severity="info",
        entity_iri="http://data.europa.eu/949/Track",
        predicate_short="label",
        language="fr",
        before={"value": "Voie", "is_iri_value": False},
        after={"value": "Voie ferrée", "is_iri_value": False},
    )
    body = _format_change(change, _ERA)
    assert body == '**Label changed** on `era:Track` (fr): *"Voie"* → *"Voie ferrée"*'


def test_format_change_uses_prefixed_iri_when_known():
    change = _change("class_added", entity_iri="http://data.europa.eu/949/Track")
    assert "`era:Track`" in _format_change(change, _ERA)


def test_format_change_uses_full_iri_when_prefix_unknown():
    change = _change("class_added", entity_iri="http://unknown.example/Thing")
    body = _format_change(change, _ERA)
    assert "`http://unknown.example/Thing`" in body
    assert "era:" not in body


def test_format_change_escapes_markdown_special_chars_in_labels():
    change = _change(
        "class_added", entity_iri="http://example.org/X", label="a*b_c[d]", language="en"
    )
    body = _format_change(change, {"ex": "http://example.org/"})
    assert "a\\*b\\_c\\[d\\]" in body


def test_format_change_unknown_kind_falls_back_to_summary():
    change = _change("totally_unknown_kind", summary="A bespoke one-liner")
    assert _format_change(change, _ERA) == "A bespoke one-liner"


# --------------------------------------------------------------------------- #
# Whitespace / newline hygiene
# --------------------------------------------------------------------------- #


def test_render_does_not_emit_newlines_in_excess():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert "\n\n\n" not in out


def test_render_output_ends_with_single_newline():
    # render() yields no trailing whitespace (Outputs contract); the CLI appends
    # exactly one newline on emit, so the emitted form ends in a single newline.
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert not out.endswith("\n")
    emitted = out + "\n"
    assert emitted.endswith("\n") and not emitted.endswith("\n\n")


def test_render_no_trailing_whitespace_on_any_line():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    for line in out.split("\n"):
        assert line == line.rstrip(), f"trailing whitespace: {line!r}"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("char", _SPECIALS)
def test_escape_markdown_handles_each_special_char(char):
    assert escape_markdown(char) == f"\\{char}"


def test_escape_markdown_handles_combined_string():
    combined = "".join(_SPECIALS)
    expected = "".join(f"\\{c}" for c in _SPECIALS)
    assert escape_markdown(combined) == expected


def test_escape_markdown_leaves_plain_text_untouched():
    assert escape_markdown("Voie ferrée 123") == "Voie ferrée 123"


def test_normalize_source_converts_windows_path():
    assert normalize_source("tests\\fixtures\\diff\\a.ttl") == "tests/fixtures/diff/a.ttl"
    assert normalize_source("C:\\Users\\me\\ont.ttl") == "C:/Users/me/ont.ttl"


def test_normalize_source_leaves_url_untouched():
    url = "http://data.europa.eu/949/ontology.ttl"
    assert normalize_source(url) == url


def test_normalize_source_leaves_forward_slash_path_untouched():
    assert normalize_source("tests/fixtures/diff/a.ttl") == "tests/fixtures/diff/a.ttl"


def test_render_compared_line_uses_forward_slashes_for_windows_paths():
    result = _result("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    result = dataclasses.replace(
        result,
        a=dataclasses.replace(result.a, source="tests\\fixtures\\diff\\era_evolution_v1.ttl"),
        b=dataclasses.replace(result.b, source="tests\\fixtures\\diff\\era_evolution_v2.ttl"),
    )
    out = render(result)
    assert "Compared `tests/fixtures/diff/era_evolution_v1.ttl` against" in out
    assert "\\" not in out.split("\n")[2]  # the "Compared ..." line carries no backslashes


def test_severity_icon_consistent_across_renderings():
    assert severity_icon("breaking", emoji=True) == severity_icon("breaking", emoji=True) == "🔴"
    assert severity_icon("breaking", emoji=False) == "[BREAKING]"
    assert severity_icon("additive", emoji=True) == "🟢"


# --------------------------------------------------------------------------- #
# Golden files (byte-for-byte locked contract)
# --------------------------------------------------------------------------- #


def _golden(name: str) -> str:
    return (GOLDEN / name).read_text(encoding="utf-8").rstrip("\n")


def test_render_golden_empty_diff():
    out = render(_result("identical_a.ttl", "identical_b.ttl"))
    assert out == _golden("empty.md")


def test_render_golden_era_evolution():
    out = render(_result("era_evolution_v1.ttl", "era_evolution_v2.ttl"))
    assert out == _golden("era_evolution.md")


def test_render_golden_era_renames():
    out = render(_result("era_renames_v1.ttl", "era_renames_v2.ttl", base=RENAME))
    assert out == _golden("era_renames.md")


def test_render_golden_only_renames():
    out = render(_result("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl", base=RENAME))
    assert out == _golden("only_renames.md")


def test_render_golden_with_unexplained_layer0():
    out = render(_result("unexplained_layer0_before.ttl", "unexplained_layer0_after.ttl"))
    assert out == _golden("with_unexplained_layer0.md")


def test_render_golden_breaking_only():
    out = render(_result("removed_class_before.ttl", "removed_class_after.ttl"))
    assert out == _golden("breaking_only.md")


def test_render_golden_with_truncation():
    out = render(_truncation_result(55))
    assert out == _golden("with_truncation.md")


def test_render_golden_escaping_specials():
    out = render(_result("escaping_specials_before.ttl", "escaping_specials_after.ttl"))
    assert out == _golden("escaping_specials.md")
