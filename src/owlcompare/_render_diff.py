"""Rendering for ``owlcompare diff`` output (text + JSON).

Mirrors :mod:`owlcompare._render`: a TTY gets rich panels/tables, anything
non-interactive (pipes, CI logs, captured test output, ``--out`` files) gets the
same content as clean plain text. JSON is schema-versioned for downstream tools.

Since Component 06 the text output is grouped by layer: Layer 1 (structural)
changes are shown prominently, and the Layer 0 (syntactic) triples they explain
are hidden by default — only *unexplained* triples remain, with a count and a
``--show-syntactic`` hint.

The JSON emitter moved to :mod:`owlcompare.report.json_report` in Component 15
(the report package is Phase 4's home for every renderer); ``diff_json`` is
re-exported here so existing ``from owlcompare._render_diff import diff_json``
call sites keep working.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from owlcompare.diff._common import Change, shorten_synthetic_iri
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.severity import SeverityRefinement
from owlcompare.model import OntologySnapshot
from owlcompare.report.json_report import diff_json

__all__ = [
    "diff_json",
    "diff_text_plain",
    "render_diff_text",
    "render_severity_explanations",
    "severity_explanations_plain",
]

# Each layer section truncates after this many changes; the full set lives in
# --format json or the Markdown/HTML report. Q2 (resolved): not configurable.
_TEXT_CHANGE_LIMIT = 20

# Rich styling per severity, used in the TTY tables.
_SEVERITY_STYLE: dict[str, str] = {
    "breaking": "bold red",
    "non_breaking": "yellow",
    "additive": "green",
    "info": "dim",
}


def _counts(changes: list[Change]) -> dict[str, int]:
    added = sum(1 for c in changes if c.kind == "triple_added")
    removed = sum(1 for c in changes if c.kind == "triple_removed")
    breaking = sum(1 for c in changes if c.severity == "breaking")
    return {"added": added, "removed": removed, "total": len(changes), "breaking": breaking}


def _summary_line(counts: dict[str, int]) -> str:
    base = f"{counts['added']} triples added, {counts['removed']} triples removed"
    if counts["breaking"]:
        return f"{base} ({counts['breaking']} breaking)"
    return base


def _display_summary(change: Change) -> str:
    """The change's summary with any synthetic URN collapsed for display.

    The diff layers already shorten these when building summaries; this is a
    defensive token-wise pass so user-facing rendering stays compact regardless
    of which code path produced the summary. JSON output is untouched.
    """
    return " ".join(shorten_synthetic_iri(token) for token in change.summary.split(" "))


def _partition(
    changes: list[Change], registry: SubsumptionRegistry
) -> tuple[list[Change], list[Change], list[Change]]:
    """Split into ``(structural, layer0_all, layer0_unexplained)``."""
    structural = [c for c in changes if c.layer == "structural"]
    layer0 = [c for c in changes if c.layer == "syntactic"]
    unexplained = [c for c in layer0 if not registry.is_explained(c.details.get("change_id", ""))]
    return structural, layer0, unexplained


def _split_renames(structural: list[Change]) -> tuple[list[Change], list[Change]]:
    """Partition structural changes into ``(renames, everything_else)``.

    Consolidated ``*_renamed`` changes (Component 11) are shown in their own
    section so a safe refactor reads as a handful of renames rather than being
    buried among the structural changes. Order within each group is preserved.
    """
    renames = [c for c in structural if c.kind.endswith("_renamed")]
    others = [c for c in structural if not c.kind.endswith("_renamed")]
    return renames, others


def _layer0_heading(
    layer0: list[Change], unexplained: list[Change], *, layer1_enabled: bool, show_syntactic: bool
) -> str:
    """Heading for the Layer 0 section, reflecting subsumption when Layer 1 ran."""
    if not layer1_enabled:
        return f"Layer 0 — Syntactic ({len(layer0)} changes)"
    if show_syntactic:
        return f"Layer 0 — Syntactic ({len(layer0)} changes, {len(unexplained)} unexplained)"
    return f"Layer 0 — Syntactic ({len(unexplained)} unexplained)"


def diff_text_plain(
    changes: list[Change],
    registry: SubsumptionRegistry,
    a: OntologySnapshot,
    b: OntologySnapshot,
    *,
    layer1_enabled: bool,
    show_syntactic: bool,
) -> str:
    """Render plain (un-styled) text for pipes, ``--out`` files and CI logs."""
    lines = [
        "owlcompare diff",
        f"A: {a.source}",
        f"B: {b.source}",
        "",
    ]
    if not changes:
        lines.append("No changes: the two ontologies are identical after canonicalization.")
        return "\n".join(lines)

    structural, layer0, unexplained = _partition(changes, registry)
    lines.append(_summary_line(_counts(changes)))

    if layer1_enabled:
        renames, others = _split_renames(structural)
        if renames:
            lines.append("")
            lines.append(f"Renames ({len(renames)} consolidated)")
            _append_change_lines(lines, renames)
        lines.append("")
        lines.append(f"Layer 1 — Structural ({len(others)} changes)")
        _append_change_lines(lines, others)

    visible_layer0 = layer0 if show_syntactic else unexplained
    heading = _layer0_heading(
        layer0, unexplained, layer1_enabled=layer1_enabled, show_syntactic=show_syntactic
    )
    if layer1_enabled and not show_syntactic:
        heading += "        [use --show-syntactic for all]"
    lines.append("")
    lines.append(heading)
    _append_change_lines(lines, visible_layer0)
    return "\n".join(lines)


def _append_change_lines(lines: list[str], changes: list[Change]) -> None:
    for change in changes[:_TEXT_CHANGE_LIMIT]:
        lines.append(f"  [{change.severity}] {_display_summary(change)}")
    if len(changes) > _TEXT_CHANGE_LIMIT:
        lines.append(f"  ...and {len(changes) - _TEXT_CHANGE_LIMIT} more")


def render_diff_text(
    changes: list[Change],
    registry: SubsumptionRegistry,
    a: OntologySnapshot,
    b: OntologySnapshot,
    *,
    layer1_enabled: bool,
    show_syntactic: bool,
    stream: TextIO | None = None,
) -> None:
    """Print the text diff to ``stream`` (rich on a TTY, plain otherwise)."""
    stream = stream if stream is not None else sys.stdout
    is_terminal = getattr(stream, "isatty", lambda: False)()
    if not is_terminal:
        print(
            diff_text_plain(
                changes,
                registry,
                a,
                b,
                layer1_enabled=layer1_enabled,
                show_syntactic=show_syntactic,
            ),
            file=stream,
        )
        return
    # emoji=False: prefixed names contain colons (``ex:Car``); without this, a
    # fragment like ``:Car:`` is substituted with an emoji (🚗). markup stays on.
    console = Console(file=stream, emoji=False)
    _render_rich(
        changes,
        registry,
        a,
        b,
        console,
        layer1_enabled=layer1_enabled,
        show_syntactic=show_syntactic,
    )


def _render_rich(
    changes: list[Change],
    registry: SubsumptionRegistry,
    a: OntologySnapshot,
    b: OntologySnapshot,
    console: Console,
    *,
    layer1_enabled: bool,
    show_syntactic: bool,
) -> None:
    counts = _counts(changes)
    header = f"A: {a.source}\nB: {b.source}\n\n{_summary_line(counts)}"
    border = "red" if counts["breaking"] else "cyan"
    console.print(Panel(header, title="owlcompare diff", border_style=border))

    if not changes:
        console.print("No changes: the two ontologies are identical after canonicalization.")
        return

    structural, layer0, unexplained = _partition(changes, registry)

    if layer1_enabled:
        renames, others = _split_renames(structural)
        if renames:
            console.print(f"\n[bold]Renames ({len(renames)} consolidated)[/bold]")
            console.print(_change_table(renames))
        console.print(f"\n[bold]Layer 1 — Structural ({len(others)} changes)[/bold]")
        console.print(_change_table(others))

    visible_layer0 = layer0 if show_syntactic else unexplained
    heading = _layer0_heading(
        layer0, unexplained, layer1_enabled=layer1_enabled, show_syntactic=show_syntactic
    )
    hint = ""
    if layer1_enabled and not show_syntactic:
        hint = "        [dim][use --show-syntactic for all][/dim]"
    console.print(f"\n[bold]{heading}[/bold]{hint}")
    console.print(_change_table(visible_layer0))


def _change_table(changes: list[Change]) -> Table:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Severity")
    table.add_column("Change")
    for change in changes[:_TEXT_CHANGE_LIMIT]:
        style = _SEVERITY_STYLE.get(change.severity, "")
        table.add_row(
            f"[{style}]{change.severity}[/{style}]" if style else change.severity,
            _display_summary(change),
        )
    if len(changes) > _TEXT_CHANGE_LIMIT:
        table.add_row("", f"[dim]...and {len(changes) - _TEXT_CHANGE_LIMIT} more[/dim]")
    return table


# --------------------------------------------------------------------------- #
# --explain-severity panel (Component 10)
# --------------------------------------------------------------------------- #


def severity_explanations_plain(refinements: Sequence[SeverityRefinement]) -> str:
    """Plain-text ``--explain-severity`` panel for pipes, ``--out`` files and CI."""
    if not refinements:
        return "Severity explanations: none (no refinements applied)."
    lines = [f"Severity explanations ({len(refinements)} refinement(s)):"]
    for r in refinements:
        lines.append(
            f"  [{r.rule_id}] {r.original_severity} -> {r.refined_severity}: "
            f"{r.rationale} ({r.change_id})"
        )
    return "\n".join(lines)


def render_severity_explanations(
    refinements: Sequence[SeverityRefinement],
    stream: TextIO | None = None,
) -> None:
    """Print the ``--explain-severity`` panel (rich on a TTY, plain otherwise)."""
    stream = stream if stream is not None else sys.stdout
    is_terminal = getattr(stream, "isatty", lambda: False)()
    if not is_terminal:
        print(severity_explanations_plain(refinements), file=stream)
        return
    console = Console(file=stream, emoji=False)  # see note above: ``ex:Car`` vs 🚗
    if not refinements:
        console.print("\n[bold]Severity explanations[/bold]\n[dim](no refinements applied)[/dim]")
        return
    console.print(f"\n[bold]Severity explanations ({len(refinements)})[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Rule")
    table.add_column("Change")
    table.add_column("Rationale")
    for r in refinements:
        table.add_row(
            r.rule_id,
            f"{r.original_severity} → {r.refined_severity}",
            r.rationale,
        )
    console.print(table)
