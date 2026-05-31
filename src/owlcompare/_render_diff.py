"""Rendering for ``owlcompare diff`` Layer 0 output (text + JSON).

Mirrors :mod:`owlcompare._render`: a TTY gets a rich panel/table, anything
non-interactive (pipes, CI logs, captured test output, ``--out`` files) gets the
same content as clean plain text. JSON is schema-versioned for downstream tools.
The richer Markdown/HTML/JUnit renderers arrive in Phase 4.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from owlcompare.diff._common import Change, shorten_synthetic_iri
from owlcompare.model import OntologySnapshot

# JSON output contract version (specs/05-syntactic-diff.md § CLI integration).
SCHEMA_VERSION = 1

# Text output truncates after this many changes; the full set lives in --format
# json or (Phase 4) the HTML report. Q2 (resolved): not configurable in v1.
_TEXT_CHANGE_LIMIT = 20


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


def change_to_dict(change: Change) -> dict[str, Any]:
    """Serialize one ``Change`` to a JSON-ready dict."""
    return {
        "layer": change.layer,
        "kind": change.kind,
        "severity": change.severity,
        "subject": change.subject,
        "summary": change.summary,
        "details": change.details,
        "before": change.before,
        "after": change.after,
    }


def diff_json(changes: list[Change]) -> str:
    """Render the change list as schema-versioned JSON."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "summary": _counts(changes),
        "changes": [change_to_dict(c) for c in changes],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _display_summary(change: Change) -> str:
    """The change's summary with any synthetic URN collapsed for display.

    ``syntactic.diff`` already shortens these when it builds the summary; this is
    a defensive token-wise pass so the user-facing rendering stays compact even
    for summaries produced by other code paths. JSON output is untouched.
    """
    return " ".join(shorten_synthetic_iri(token) for token in change.summary.split(" "))


def diff_text_plain(changes: list[Change], a: OntologySnapshot, b: OntologySnapshot) -> str:
    """Render plain (un-styled) text for pipes, ``--out`` files and CI logs."""
    lines = [
        "owlcompare diff — Layer 0 (syntactic)",
        f"A: {a.source}",
        f"B: {b.source}",
        "",
    ]
    if not changes:
        lines.append("No changes: the two ontologies are identical after canonicalization.")
        return "\n".join(lines)

    lines.append(_summary_line(_counts(changes)))
    lines.append("")
    for change in changes[:_TEXT_CHANGE_LIMIT]:
        lines.append(f"  [{change.severity}] {_display_summary(change)}")
    if len(changes) > _TEXT_CHANGE_LIMIT:
        lines.append(f"  ...and {len(changes) - _TEXT_CHANGE_LIMIT} more")
    return "\n".join(lines)


def render_diff_text(
    changes: list[Change],
    a: OntologySnapshot,
    b: OntologySnapshot,
    stream: TextIO | None = None,
) -> None:
    """Print the text diff to ``stream`` (rich on a TTY, plain otherwise)."""
    stream = stream if stream is not None else sys.stdout
    is_terminal = getattr(stream, "isatty", lambda: False)()
    if not is_terminal:
        print(diff_text_plain(changes, a, b), file=stream)
        return
    console = Console(file=stream)
    _render_rich(changes, a, b, console)


# Rich styling per severity, used in the TTY table.
_SEVERITY_STYLE: dict[str, str] = {
    "breaking": "bold red",
    "non_breaking": "yellow",
    "additive": "green",
    "info": "dim",
}


def _render_rich(
    changes: list[Change], a: OntologySnapshot, b: OntologySnapshot, console: Console
) -> None:
    counts = _counts(changes)
    header = f"A: {a.source}\nB: {b.source}\n\n{_summary_line(counts)}"
    border = "red" if counts["breaking"] else "cyan"
    console.print(Panel(header, title="owlcompare diff — Layer 0 (syntactic)", border_style=border))

    if not changes:
        console.print("No changes: the two ontologies are identical after canonicalization.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Severity")
    table.add_column("Change")
    for change in changes[:_TEXT_CHANGE_LIMIT]:
        style = _SEVERITY_STYLE.get(change.severity, "")
        table.add_row(
            f"[{style}]{change.severity}[/{style}]" if style else change.severity,
            _display_summary(change),
        )
    console.print(table)
    if len(changes) > _TEXT_CHANGE_LIMIT:
        console.print(f"[dim]...and {len(changes) - _TEXT_CHANGE_LIMIT} more[/dim]")
