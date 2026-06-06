"""JUnit XML renderer for ``owlcompare diff`` — CI integration format (Component 18).

Renders a ``DiffResult`` as a JUnit XML document so any CI system with a JUnit
reporter (GitHub Actions, GitLab CI, Jenkins, CircleCI, …) shows ontology changes
as a native test-results dashboard. Each Change becomes one ``<testcase>``;
breaking changes become ``<failure>`` elements; everything else passes (info
changes optionally become ``<skipped>``). The whole text-format diff is embedded
as ``<system-out>``.

The document is built from string templates (not an XML library) for tight
control over attribute order and indentation, which keeps the output
byte-deterministic — testcases sorted by ``(classname, name)``, timestamps honour
``SOURCE_DATE_EPOCH``. Every user-supplied value is escaped via stdlib
:func:`xml.sax.saxutils.escape`; the ``<system-out>`` CDATA is guarded against the
``]]>`` terminator. See ``specs/18-junit-xml.md`` for the contract and the
severity → result mapping.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.sax.saxutils import escape as _xml_escape

from owlcompare._render_diff import diff_text_plain
from owlcompare.diff._common import Change, DiffResult
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.report._markdown_helpers import prefix_iri

_DEFAULT_SUITE_NAME = "owlcompare.diff"
# JUnit names should stay short for dashboard readability (spec § Per-testcase
# rendering); longer subjects/summaries are truncated with an ellipsis.
_NAME_MAX_LEN = 60
# Entity-identifying detail keys, in the order we prefer them for the failure
# body and the testcase name (mirrors _html_components.card_subject).
_ENTITY_KEYS = ("entity_iri", "property_iri", "ontology_iri")


@dataclass(frozen=True, slots=True)
class JUnitOptions:
    """Configuration for JUnit XML rendering."""

    suite_name: str | None = None  # Default: "owlcompare.diff"
    include_skipped: bool = False  # If True, info-severity changes become <skipped>
    include_system_out: bool = True  # If True, embed the full text rendering as <system-out>
    timestamp: str | None = None  # ISO 8601; defaults to SOURCE_DATE_EPOCH or current time


def render(result: DiffResult, options: JUnitOptions | None = None) -> str:
    """Render a ``DiffResult`` as a JUnit XML document.

    Returns the full XML document as a string with an XML declaration and a
    trailing newline. Valid against the JUnit XML schema variant supported by
    GitHub Actions, GitLab CI, Jenkins, and the other major CI systems. Output is
    deterministic: the same input (with ``SOURCE_DATE_EPOCH`` pinned) yields
    byte-identical XML.
    """
    options = options or JUnitOptions()
    prefixes = {**result.a.prefixes, **result.b.prefixes}
    suite_name = options.suite_name or _DEFAULT_SUITE_NAME
    timestamp = _timestamp(options.timestamp)

    cases = _testcase_changes(result)
    tests = len(cases) or 1  # an empty <testsuite> is invalid; emit "no-changes"
    failures = sum(1 for c in cases if _is_failure(c))
    skipped = sum(1 for c in cases if _is_skipped(c, options.include_skipped))

    if cases:
        ordered = sorted(cases, key=lambda c: (_classname(c), _testcase_name(c, prefixes)))
        testcase_lines = [
            _render_testcase(c, prefixes, include_skipped=options.include_skipped) for c in ordered
        ]
    else:
        testcase_lines = [_NO_CHANGES_TESTCASE]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuites name="owlcompare" tests="{tests}" failures="{failures}" '
        f'errors="0" skipped="{skipped}" time="0">',
        f'  <testsuite name="{_attr(suite_name)}" tests="{tests}" failures="{failures}" '
        f'errors="0" skipped="{skipped}" timestamp="{_attr(timestamp)}" time="0">',
        *testcase_lines,
    ]
    if options.include_system_out:
        lines.append(_render_system_out(result))
    lines.append("  </testsuite>")
    lines.append("</testsuites>")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Change selection + severity → result mapping
# --------------------------------------------------------------------------- #


def _testcase_changes(result: DiffResult) -> list[Change]:
    """The changes that become testcases: every structural change plus the
    *unexplained* Layer 0 changes (the explained ones are folded into the
    structural change that subsumes them, exactly as the other renderers do)."""
    registry = _registry(result)
    changes = list(result.changes)
    structural = [c for c in changes if c.layer == "structural"]
    layer0 = [c for c in changes if c.layer == "syntactic"]
    unexplained = [c for c in layer0 if not registry.is_explained(c.details.get("change_id", ""))]
    return structural + unexplained


def _is_rename(change: Change) -> bool:
    return change.kind.endswith("_renamed")


def _is_failure(change: Change) -> bool:
    """Breaking non-rename changes fail; renames always pass (spec mapping table)."""
    return not _is_rename(change) and change.severity == "breaking"


def _is_skipped(change: Change, include_skipped: bool) -> bool:
    """Info non-rename changes are skipped only when the flag is set."""
    return include_skipped and not _is_rename(change) and change.severity == "info"


# --------------------------------------------------------------------------- #
# Per-testcase rendering
# --------------------------------------------------------------------------- #


def _render_testcase(change: Change, prefixes: dict[str, str], *, include_skipped: bool) -> str:
    """One ``<testcase>``: a ``<failure>`` for breaking, ``<skipped>`` for an info
    change under the flag, otherwise an empty (passing) self-closing element."""
    attrs = (
        f'classname="{_attr(_classname(change))}" '
        f'name="{_attr(_testcase_name(change, prefixes))}" time="0"'
    )
    if _is_failure(change):
        message = change.summary or f"breaking change of kind {change.kind}"
        body = _text(_failure_body(change))
        return (
            f"    <testcase {attrs}>\n"
            f'      <failure type="{_attr(change.kind)}" '
            f'message="{_attr(message)}">{body}</failure>\n'
            "    </testcase>"
        )
    if _is_skipped(change, include_skipped):
        body = _text(change.summary)
        return (
            f"    <testcase {attrs}>\n"
            f'      <skipped message="info-level change">{body}</skipped>\n'
            "    </testcase>"
        )
    return f"    <testcase {attrs}/>"


def _classname(change: Change) -> str:
    """``{layer}.{kind}`` so the CI dashboard groups testcases by kind."""
    return f"{change.layer}.{change.kind}"


def _testcase_name(change: Change, prefixes: dict[str, str]) -> str:
    """The testcase name: the shortened subject IRI, else the summary; truncated."""
    if change.subject:
        return _truncate(prefix_iri(change.subject, prefixes))
    return _truncate(change.summary or change.kind)


def _failure_body(change: Change) -> str:
    """The plain-text ``<failure>`` body shown in the CI dashboard's detail panel.

    Carries only the user-relevant fields (the *full* entity IRI, kind, label,
    severity) plus the subsumed Layer 0 change ids when present — not the full
    ``details`` dict, which would be noisy. The full IRI (not the compact form used
    in the testcase name) goes here so the dashboard's detail view is unambiguous.
    The text is XML-escaped by the caller, not embedded as XML.
    """
    summary = change.summary or f"breaking change of kind {change.kind}"
    lines = [f"Breaking change detected: {summary}"]
    entity = _entity_iri(change)
    if entity:
        lines.append(f"  Entity:    {entity}")
    lines.append(f"  Kind:      {change.kind}")
    label = change.details.get("label")
    if label:
        language = change.details.get("language")
        lines.append(
            f'  Label:     "{label}"@{language}' if language else f'  Label:     "{label}"'
        )
    lines.append(f"  Severity:  {change.severity}")
    subsumes = change.details.get("subsumes")
    if isinstance(subsumes, list) and subsumes:
        lines.append("")
        lines.append("  Subsumed Layer 0 changes:")
        lines.extend(f"    - {cid}" for cid in subsumes)
    lines.append("")
    lines.append("Refer to the full owlcompare report for context.")
    return "\n".join(lines)


def _entity_iri(change: Change) -> str | None:
    """The entity/property/ontology IRI for the failure body, else the subject."""
    for key in _ENTITY_KEYS:
        value = change.details.get(key)
        if value:
            return str(value)
    return change.subject or None


# --------------------------------------------------------------------------- #
# <system-out>
# --------------------------------------------------------------------------- #


def _render_system_out(result: DiffResult) -> str:
    """Embed the whole text-format diff as a ``<system-out>`` CDATA section.

    The text renderer (Component 05) already emits plain text with no ANSI codes,
    so it drops straight into CDATA — only the ``]]>`` terminator needs guarding.
    """
    text = diff_text_plain(
        list(result.changes),
        _registry(result),
        result.a,
        result.b,
        layer1_enabled=True,
        show_syntactic=False,
    )
    return f"    <system-out><![CDATA[{_cdata_escape(text)}]]></system-out>"


def _cdata_escape(text: str) -> str:
    """Split any ``]]>`` so it can't terminate the CDATA section early.

    CDATA forbids the literal ``]]>``; the standard fix closes the section right
    before the ``>`` and reopens a fresh one (``]]]]><![CDATA[>``), which a parser
    reassembles into the original three characters as ordinary text.
    """
    return text.replace("]]>", "]]]]><![CDATA[>")


# --------------------------------------------------------------------------- #
# Escaping, timestamp, truncation
# --------------------------------------------------------------------------- #


def _text(value: str) -> str:
    """Escape ``&``, ``<`` and ``>`` for element text content."""
    return _xml_escape(value)


def _attr(value: str) -> str:
    """Escape a value for use inside a double-quoted attribute."""
    return _xml_escape(value, {'"': "&quot;", "'": "&#39;"})


def _truncate(text: str) -> str:
    """Truncate to ``_NAME_MAX_LEN`` characters with a trailing ellipsis."""
    if len(text) <= _NAME_MAX_LEN:
        return text
    return text[: _NAME_MAX_LEN - 3] + "..."


def _timestamp(override: str | None) -> str:
    """Resolve the ISO 8601 ``timestamp`` attribute.

    Priority: an explicit ``options.timestamp``; otherwise ``SOURCE_DATE_EPOCH``
    (reproducible-builds convention, so goldens are byte-stable); otherwise the
    local wall clock.
    """
    if override is not None:
        return override
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None and epoch.strip().isdigit():
        return datetime.fromtimestamp(int(epoch), tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _registry(result: DiffResult) -> SubsumptionRegistry:
    """The diff's subsumption registry, or an empty one for hand-built results."""
    registry = result.metadata.get("subsumption_registry")
    if isinstance(registry, SubsumptionRegistry):
        return registry
    return SubsumptionRegistry()


# An empty diff still needs one passing testcase — some CI parsers reject an empty
# <testsuite> (spec § Edge cases).
_NO_CHANGES_TESTCASE = '    <testcase classname="owlcompare.diff" name="no-changes" time="0"/>'

__all__ = ["JUnitOptions", "render"]
