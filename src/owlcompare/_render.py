"""Rich-formatted ``owlcompare load`` output, with plain-text TTY fallback.

The CLI calls :func:`render_summary` rather than ``print(snapshot.summary())``
so interactive terminals get panels/tables and pipes/CI logs get the same
information as a flat readable text block.
"""

from __future__ import annotations

import sys
from typing import TextIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from owlcompare.model import (
    KIND_ORDER,
    OntologySnapshot,
    sample_entity_iris,
)


def render_summary(snapshot: OntologySnapshot, stream: TextIO | None = None) -> None:
    """Render an ontology summary to ``stream`` (default ``sys.stdout``).

    On a TTY this emits the rich-formatted panels and tables described in the
    Component 02 follow-up. When the stream is not a terminal (piped, CI logs,
    captured by tests) we fall through to :meth:`OntologySnapshot.summary` so
    the output stays clean — no boxes, no ANSI — while carrying the same
    content.
    """
    stream = stream if stream is not None else sys.stdout
    is_terminal = getattr(stream, "isatty", lambda: False)()
    if not is_terminal:
        print(snapshot.summary(), file=stream)
        return

    console = Console(file=stream)
    _render_title(snapshot, console)
    _render_metadata(snapshot, console)
    _render_entities(snapshot, console)
    _render_prefixes(snapshot, console)


def _render_title(snapshot: OntologySnapshot, console: Console) -> None:
    iri = snapshot.metadata.iri or "<no ontology IRI declared>"
    console.print(Panel(Text(iri, style="bold"), title="Ontology", border_style="cyan"))


def _render_metadata(snapshot: OntologySnapshot, console: Console) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="dim", justify="right")
    table.add_column()
    if snapshot.metadata.version_iri:
        table.add_row("Version IRI", snapshot.metadata.version_iri)
    if snapshot.metadata.version_info:
        table.add_row("Version info", snapshot.metadata.version_info)
    table.add_row("Source", snapshot.source)
    table.add_row("Format", snapshot.format)
    table.add_row("Axiom count", str(snapshot.axiom_count()))
    if snapshot.metadata.imports:
        table.add_row("Imports", "\n".join(snapshot.metadata.imports))
    console.print(Panel(table, title="Metadata", border_style="cyan"))


def _render_entities(snapshot: OntologySnapshot, console: Console) -> None:
    table = Table(title="Entities", show_header=True, header_style="bold")
    table.add_column("Kind", style="dim")
    table.add_column("Count", justify="right", style="bold")
    table.add_column("Sample IRIs")
    counts = snapshot.entities.counts()
    buckets = snapshot.entities.by_kind()
    for kind in KIND_ORDER:
        count = counts[kind]
        if count == 0:
            table.add_row(kind, "0", Text("—", style="dim"))
            continue
        samples, overflow = sample_entity_iris(buckets[kind], snapshot.prefixes)
        body = "\n".join(samples)
        if overflow:
            body += f"\n[dim]...and {overflow} more[/dim]"
        table.add_row(kind, str(count), Text.from_markup(body))
    console.print(table)


def _render_prefixes(snapshot: OntologySnapshot, console: Console) -> None:
    if not snapshot.prefixes:
        return
    table = Table(title="Prefixes", show_header=True, header_style="bold")
    table.add_column("Prefix", style="dim")
    table.add_column("Namespace")
    for prefix, namespace in sorted(snapshot.prefixes.items()):
        table.add_row(prefix or "(default)", namespace)
    console.print(table)
