"""HTML renderer for ``owlcompare diff`` — the self-contained report (Component 17).

Produces one valid HTML5 document with the CSS and JS inlined: no external
assets, no network, openable from ``file://`` (DD-005). The document is fully
readable with JavaScript disabled — sections are expanded, content is in the DOM,
and ``<details>`` works natively; JS only *enhances* (collapse, theme toggle, JSON
download, copy link). Implements the design brief in ``docs/design/``; design
changes belong there, not here. See ``specs/17-html-report.md``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from typing import Literal

from owlcompare._version import __version__
from owlcompare.diff._common import Change, DiffResult, Severity
from owlcompare.report._markdown_helpers import normalize_source
from owlcompare.report.json_report import SCHEMA_VERSION, diff_json

from . import _html_components as hc

_REPO_URL = "https://github.com/Ajala111/owlcompare"
_SCHEMA_URL = (
    "https://raw.githubusercontent.com/Ajala111/owlcompare/main/docs/schema/diff-result.schema.json"
)

# Severities that share the "Other changes" section, sorted in this order.
_OTHER_SEVERITIES: tuple[Severity, ...] = ("non_breaking", "additive", "info")
# Summary-strip severity buckets (renames are counted separately).
_STRIP_SEVERITIES: tuple[Severity, ...] = ("breaking", "non_breaking", "additive", "info")
_SEVERITY_LABEL: dict[str, str] = {
    "breaking": "Breaking",
    "non-breaking": "Non-breaking",
    "additive": "Additive",
    "info": "Info",
}


@dataclass(frozen=True, slots=True)
class HtmlOptions:
    """Configuration for HTML rendering."""

    default_theme: Literal["light", "dark", "auto"] = "auto"  # 'auto' respects prefers-color-scheme
    embed_json: bool = True  # If True, embeds the raw JSON in a hidden block for download
    include_footer: bool = True
    title_override: str | None = None  # If set, replaces the default page title
    inline_svg_logo: bool = True  # Inline owlcompare wordmark


def render(result: DiffResult, options: HtmlOptions | None = None) -> str:
    """Render a ``DiffResult`` as a self-contained HTML document.

    Returns the full HTML5 document as a string. No external dependencies; valid
    for offline viewing, email attachment, and archival. Output is deterministic:
    the same input (with ``SOURCE_DATE_EPOCH`` pinned) yields byte-identical HTML.
    """
    options = options or HtmlOptions()
    model = _Model.build(result)

    head = _render_head(model, options)
    body = _render_body(model, result, options)
    html_attrs = _html_attrs(options.default_theme)
    return f"<!DOCTYPE html>\n<html {html_attrs}>\n{head}\n{body}\n</html>\n"


# --------------------------------------------------------------------------- #
# Derived view model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Model:
    """The change buckets and counts derived once from a ``DiffResult``."""

    prefixes: dict[str, str]
    source_a: str
    source_b: str
    renames: list[Change]
    breaking: list[Change]
    other: list[Change]
    unexplained: list[Change]
    counts: dict[str, int]
    refinements: dict[str, object]

    @staticmethod
    def build(result: DiffResult) -> _Model:
        registry = result.metadata.get("subsumption_registry")
        changes = list(result.changes)
        structural = [c for c in changes if c.layer == "structural"]
        layer0 = [c for c in changes if c.layer == "syntactic"]
        unexplained = [c for c in layer0 if not _is_explained(registry, c)]

        renames = [c for c in structural if c.kind.endswith("_renamed")]
        non_rename = [c for c in structural if not c.kind.endswith("_renamed")]
        breaking = [c for c in non_rename if c.severity == "breaking"]
        other = [c for c in non_rename if c.severity in _OTHER_SEVERITIES]

        # Counts exclude renames (own bucket) and explained Layer 0 (already
        # represented by the structural change that subsumes them).
        counted = non_rename + unexplained
        counts: dict[str, int] = {
            sev: sum(1 for c in counted if c.severity == sev) for sev in _STRIP_SEVERITIES
        }
        counts["rename"] = len(renames)
        counts["total"] = len(counted) + len(renames)

        return _Model(
            prefixes={**result.a.prefixes, **result.b.prefixes},
            source_a=_source_display(result.a.source),
            source_b=_source_display(result.b.source),
            renames=renames,
            breaking=breaking,
            other=other,
            unexplained=unexplained,
            counts=counts,
            refinements=_refinement_map(result),
        )


def _refinement_map(result: DiffResult) -> dict[str, object]:
    """Map ``change_id`` → its ``SeverityRefinement`` for the in-card 'why' note."""
    refinements = result.metadata.get("severity_refinements", ())
    return {r.change_id: r for r in refinements}


def _is_explained(registry: object, change: Change) -> bool:
    """Whether a Layer 0 change is subsumed by a Layer 1 change (per the registry)."""
    if registry is None:
        return False
    change_id = change.details.get("change_id", "")
    return bool(registry.is_explained(change_id))  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# <head>
# --------------------------------------------------------------------------- #


def _render_head(model: _Model, options: HtmlOptions) -> str:
    title = options.title_override or f"owlcompare diff: {_status_phrase(model)}"
    css = _asset("styles.css")
    return (
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{hc.escape_html(title)}</title>\n"
        f"<style>\n{css}</style>\n"
        "</head>"
    )


# --------------------------------------------------------------------------- #
# <body>
# --------------------------------------------------------------------------- #


def _render_body(model: _Model, result: DiffResult, options: HtmlOptions) -> str:
    parts = [
        _render_header(model, options),
        _render_summary_strip(model),
        _render_main(model),
    ]
    if options.include_footer:
        parts.append(_render_footer())
    if options.embed_json:
        parts.append(_render_json_payload(result))
    parts.append(f"<script>\n{_asset('interactive.js')}</script>")
    body = "\n".join(parts)
    return f"<body>\n{body}\n</body>"


def _render_header(model: _Model, options: HtmlOptions) -> str:
    logo = _LOGO_SVG if options.inline_svg_logo else ""
    badge_class, icon, text = _status_badge(model)
    source_a = _source_chip(model.source_a)
    source_b = _source_chip(model.source_b)
    return (
        '<header class="report-header">\n'
        f'<div class="header-left">{logo}<span class="wordmark">owlcompare</span></div>\n'
        '<div class="header-center">\n'
        f'<h1 class="report-title">Diff: {source_a} vs {source_b}</h1>\n'
        f'<div class="status-badge severity-{badge_class}" role="status" '
        f'aria-label="{hc.escape_html(text)}">'
        f'<span class="status-icon" aria-hidden="true">{icon}</span> {hc.escape_html(text)}</div>\n'
        "</div>\n"
        f'<div class="header-right toolbar">\n{_TOOLBAR}\n</div>\n'
        "</header>"
    )


def _render_summary_strip(model: _Model) -> str:
    counts = model.counts
    spans = [
        f'<span class="count count-{sev.replace("_", "-")}">'
        f"{_SEVERITY_LABEL[sev.replace('_', '-')]}: <strong>{counts[sev]}</strong></span>"
        for sev in _STRIP_SEVERITIES
    ]
    spans.append(
        f'<span class="count count-renames">Renames: <strong>{counts["rename"]}</strong></span>'
    )
    body = "\n".join(spans)
    return (
        '<div class="summary-strip" role="region" aria-label="Change counts by severity">\n'
        f"{body}\n</div>"
    )


def _render_main(model: _Model) -> str:
    sections: list[str] = []
    if model.renames:
        sections.append(_render_section("Renames", "renames", model.renames, model))
    if model.breaking:
        sections.append(_render_section("Breaking changes", "breaking", model.breaking, model))
    if model.other:
        ordered = _sort_other(model.other)
        sections.append(_render_section("Other changes", "other", ordered, model))
    if model.unexplained:
        sections.append(
            _render_section(
                "Unexplained Layer 0", "layer0", model.unexplained, model, collapsed=True
            )
        )
    if not sections:
        body = '<p class="empty-note">No changes &mdash; the two ontologies are identical.</p>'
    else:
        body = "\n".join(sections)
    return f'<main class="report-main">\n{body}\n</main>'


def _render_section(
    title: str, anchor: str, changes: list[Change], model: _Model, *, collapsed: bool = False
) -> str:
    cards = "\n".join(_render_card(c, model) for c in _sort_cards(changes))
    expanded = "false" if collapsed else "true"
    collapse_attr = ' data-collapsed="true"' if collapsed else ""
    return (
        f'<section class="change-section section-{anchor}" id="section-{anchor}"{collapse_attr}>\n'
        '<header class="section-header">\n'
        f'<h2 class="section-title">{hc.escape_html(title)}</h2>\n'
        f'<span class="section-count">{len(changes)}</span>\n'
        f'<button class="section-toggle" aria-expanded="{expanded}" '
        f'aria-controls="section-{anchor}-body"><span class="chevron"></span></button>\n'
        "</header>\n"
        f'<div class="section-body" id="section-{anchor}-body">\n{cards}\n</div>\n'
        "</section>"
    )


def _render_card(change: Change, model: _Model) -> str:
    sev_class = _sev_class(change)
    change_id = hc.escape_html(str(change.details.get("change_id", "")))
    header = _render_card_header(change, sev_class, model)
    summary = hc.render_change_summary(change, model.prefixes)
    why = _render_why_note(change, model)
    details = hc.details_list(change, model.prefixes)
    return (
        f'<article class="change-card severity-{sev_class}" data-change-id="{change_id}" '
        f'data-kind="{hc.escape_html(change.kind)}" data-severity="{sev_class}">\n'
        '<div class="card-stripe" aria-hidden="true"></div>\n'
        '<div class="card-body">\n'
        f"{header}\n"
        f'<div class="card-summary">{summary}</div>\n'
        f"{why}"
        '<details class="card-details">\n'
        '<summary class="card-details-toggle">Show details</summary>\n'
        f'<div class="card-details-body">{details}</div>\n'
        "</details>\n"
        "</div>\n"
        "</article>"
    )


def _render_card_header(change: Change, sev_class: str, model: _Model) -> str:
    label = "RENAME" if sev_class == "rename" else sev_class.replace("-", " ").upper()
    title = hc.escape_html(hc.kind_title(change))
    subject = hc.card_subject(change, model.prefixes)
    subject_html = ""
    if subject:
        short = hc.escape_html(hc._short(subject, model.prefixes))
        subject_html = (
            f'<code class="card-subject" title="{hc.escape_html(subject)}">{short}</code>'
        )
    return (
        '<header class="card-header">\n'
        f'<span class="card-badge severity-{sev_class}">{hc.escape_html(label)}</span>\n'
        f'<h3 class="card-title">{title}</h3>\n'
        f"{subject_html}\n"
        "</header>"
    )


def _render_why_note(change: Change, model: _Model) -> str:
    """The in-place severity-refinement note (USER_STORIES.md story 4)."""
    change_id = change.details.get("change_id")
    refinement = model.refinements.get(str(change_id)) if change_id else None
    if refinement is None:
        return ""
    refined = hc.escape_html(str(refinement.refined_severity))  # type: ignore[attr-defined]
    original = hc.escape_html(str(refinement.original_severity))  # type: ignore[attr-defined]
    rationale = hc.escape_html(str(refinement.rationale))  # type: ignore[attr-defined]
    rule_id = hc.escape_html(str(refinement.rule_id))  # type: ignore[attr-defined]
    return (
        '<div class="why-note">\n'
        f'<span class="why-label">Why {refined}:</span> {rationale}\n'
        f'<div><span class="severity-shift">{original} &rarr; {refined}</span> '
        f'&middot; <span class="rule-id">rule: {rule_id}</span></div>\n'
        "</div>\n"
    )


def _render_footer() -> str:
    stamp = hc.escape_html(_timestamp())
    return (
        '<footer class="report-footer">\n'
        f'<p>Generated by <a href="{_REPO_URL}">owlcompare</a> {hc.escape_html(__version__)} '
        f"on {stamp} &middot; "
        f'<a href="{_SCHEMA_URL}">Schema v{SCHEMA_VERSION}</a> &middot; '
        '<a href="#" data-action="view-json">View JSON</a> '
        "(downloads the JSON payload)</p>\n"
        '<noscript><p class="noscript-note">JavaScript is disabled. The report is fully '
        "readable; only the toolbar (theme, JSON download, copy link) is inactive.</p></noscript>\n"
        "</footer>"
    )


def _render_json_payload(result: DiffResult) -> str:
    """The hidden JSON block the download button reads (Q1: embedded unconditionally).

    The ``subsumes`` / ``cascade_subsumes`` bookkeeping arrays are sorted at the
    producer (DD-021), so the embedded copy is byte-deterministic across processes
    with no post-processing here.
    """
    refinements = result.metadata.get("severity_refinements", ())
    rendered = diff_json(list(result.changes), refinements)
    # Neutralise any "</script>" sequence a user-supplied label could smuggle in;
    # "<" is valid JSON and keeps the script element from closing early.
    safe = rendered.replace("<", "\\u003c")
    return f'<script id="diff-json" type="application/json">{safe}</script>'


# --------------------------------------------------------------------------- #
# Status badge + page title
# --------------------------------------------------------------------------- #


def _status_phrase(model: _Model) -> str:
    breaking = model.counts["breaking"]
    if breaking > 0:
        return _pluralize(breaking, "breaking change")
    if model.counts["total"] > 0:
        return "no breaking changes"
    return "no changes"


def _status_badge(model: _Model) -> tuple[str, str, str]:
    """Return ``(severity_class, icon, text)`` for the header verdict badge."""
    breaking = model.counts["breaking"]
    if breaking > 0:
        return "breaking", "\U0001f534", _pluralize(breaking, "breaking change")
    if model.counts["total"] > 0:
        return "additive", "\U0001f7e2", "No breaking changes"
    return "info", "⚪", "No changes"


def _pluralize(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


# --------------------------------------------------------------------------- #
# Sorting
# --------------------------------------------------------------------------- #


def _sort_cards(changes: list[Change]) -> list[Change]:
    """Sort by subject IRI then kind (visual grouping; stable tiebreaker)."""
    return sorted(changes, key=lambda c: (c.subject or "", c.kind))


def _sort_other(changes: list[Change]) -> list[Change]:
    """Other-changes section: severity (non_breaking → additive → info), then card sort."""
    rank = {sev: i for i, sev in enumerate(_OTHER_SEVERITIES)}
    return sorted(changes, key=lambda c: (rank.get(c.severity, 99), c.subject or "", c.kind))


def _sev_class(change: Change) -> str:
    """CSS severity token: ``rename`` for renames, else the hyphenated severity."""
    if change.kind.endswith("_renamed"):
        return "rename"
    return change.severity.replace("_", "-")


# --------------------------------------------------------------------------- #
# Sources, assets, timestamp, head attrs
# --------------------------------------------------------------------------- #


def _source_display(source: str | None) -> str:
    """The full (normalized) source string, or empty when no source is known."""
    if not source:
        return ""
    return normalize_source(source)


def _source_chip(source: str) -> str:
    """``<code class="source-name" title="full">basename</code>`` (placeholder if empty)."""
    if not source:
        return '<code class="source-name">(source)</code>'
    basename = source.rstrip("/").rsplit("/", 1)[-1] or source
    return (
        f'<code class="source-name" title="{hc.escape_html(source)}">'
        f"{hc.escape_html(basename)}</code>"
    )


def _asset(name: str) -> str:
    """Read a bundled CSS/JS asset string via ``importlib.resources``."""
    return (resources.files("owlcompare.report._html_assets") / name).read_text(encoding="utf-8")


def _timestamp() -> str:
    """A stable, readable timestamp.

    Honours ``SOURCE_DATE_EPOCH`` (reproducible-builds convention) so tests and
    golden fixtures get byte-identical output; falls back to the local wall clock.
    """
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None and epoch.strip().isdigit():
        moment = datetime.fromtimestamp(int(epoch), tz=UTC)
        return moment.strftime("%Y-%m-%d %H:%M:%S UTC")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _html_attrs(default_theme: str) -> str:
    """``<html>`` attributes: lang, the default-theme hint, and a first-paint override.

    For an explicit light/dark default we also set ``data-theme`` so the choice
    applies on first paint with no JavaScript; ``auto`` leaves it to
    ``prefers-color-scheme``.
    """
    attrs = f'lang="en" data-theme-default="{default_theme}"'
    if default_theme in ("light", "dark"):
        attrs += f' data-theme="{default_theme}"'
    return attrs


# A small inline owl wordmark glyph. Inline (not <img src>) to keep the report
# self-contained (DD-005); decorative, so aria-hidden.
_LOGO_SVG = (
    '<svg class="logo" width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" '
    'focusable="false"><circle cx="10" cy="10" r="9" fill="none" stroke="currentColor" '
    'stroke-width="1.5"/><circle cx="6.5" cy="8.5" r="2.2" fill="none" stroke="currentColor" '
    'stroke-width="1.2"/><circle cx="13.5" cy="8.5" r="2.2" fill="none" stroke="currentColor" '
    'stroke-width="1.2"/><circle cx="6.5" cy="8.5" r="0.8" fill="currentColor"/>'
    '<circle cx="13.5" cy="8.5" r="0.8" fill="currentColor"/></svg>'
)

# The toolbar markup is static — the buttons operate on the document, not the
# diff — so it lives here as a constant. JS attaches the handlers by data-action.
_TOOLBAR = (
    '<button class="toolbar-btn" data-action="download-json" aria-label="Download JSON">'
    "⬇ JSON</button>\n"
    '<button class="toolbar-btn" data-action="copy-link" aria-label="Copy link">'
    "\U0001f517 Copy link</button>\n"
    '<button class="toolbar-btn" data-action="theme-toggle" aria-label="Toggle theme">'
    "\U0001f313</button>"
)
