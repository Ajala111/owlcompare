"""Typer-based CLI surface and the ``main`` entry point.

This module defines the command shape every later component plugs into. It owns
the mapping from typed exceptions to exit codes (see ``specs/01-cli.md``).
"""

from __future__ import annotations

import enum
import logging
import sys
from pathlib import Path
from typing import Annotated

import rdflib
import typer
from typer import Abort, Exit

# Typer vendors Click as ``typer._click`` and does not publicly re-export the
# ``ClickException`` base (only ``Exit``/``Abort`` above and the narrow
# ``BadParameter``). We need the base to map all usage errors to exit code 2, so
# we reach into the vendored module. Pinned ``typer<0.27`` to guard this — see
# DD-014.
from typer._click.exceptions import ClickException

from owlcompare._render import render_summary
from owlcompare._version import __version__
from owlcompare.canonicalize import CanonicalizeOptions
from owlcompare.canonicalize import canonicalize as _canonicalize
from owlcompare.exceptions import (
    CanonicalizationError,
    NotImplementedYetError,
    OwlCompareError,
)
from owlcompare.loader import load as _load_ontology
from owlcompare.logging_config import configure_logging
from owlcompare.model import LoadOptions
from owlcompare.sources import resolve as _resolve_source

logger = logging.getLogger("owlcompare")

app = typer.Typer(
    name="owlcompare",
    help="Modern semantic ontology diff tool.",
    add_completion=False,
    pretty_exceptions_show_locals=False,
)


class OutputFormat(enum.StrEnum):
    """Supported report output formats for the ``diff`` command."""

    json = "json"
    markdown = "markdown"
    html = "html"
    junit = "junit"


class LoadFormatHint(enum.StrEnum):
    """Accepted ``--format`` values for ``owlcompare load``."""

    turtle = "turtle"
    xml = "xml"
    n3 = "n3"
    nt = "nt"
    json_ld = "json-ld"
    trig = "trig"


class CanonicalOutputFormat(enum.StrEnum):
    """Accepted ``--output-format`` values for ``owlcompare canonicalize``."""

    turtle = "turtle"
    nt = "nt"


# rdflib serializer name keyed by our public output-format alias.
_CANONICAL_RDFLIB_FORMAT: dict[CanonicalOutputFormat, str] = {
    CanonicalOutputFormat.turtle: "turtle",
    CanonicalOutputFormat.nt: "nt",
}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"owlcompare {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the version and exit.",
        ),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("-v", "--verbose", count=True, help="Increase log verbosity (-v, -vv)."),
    ] = 0,
    quiet: Annotated[
        bool,
        typer.Option("-q", "--quiet", help="Only log errors."),
    ] = False,
) -> None:
    """Compare two OWL/RDF ontologies and report meaningful changes."""
    configure_logging(-1 if quiet else verbose)
    # With no subcommand, show help and exit cleanly (spec: exit 0). We do this
    # manually rather than via no_args_is_help, which exits 2 in this Typer/Click.
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@app.command()
def version() -> None:
    """Print the version and exit."""
    typer.echo(f"owlcompare {__version__}")


@app.command()
def diff(
    ontology_a: Annotated[str, typer.Argument(help="Path or URL to the baseline ontology.")],
    ontology_b: Annotated[str, typer.Argument(help="Path or URL to the comparison ontology.")],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format."),
    ] = OutputFormat.json,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output file (default: stdout for json/markdown)."),
    ] = None,
) -> None:
    """Compare two ontologies (stub in v1; not yet implemented)."""
    raise NotImplementedYetError("diff is not yet implemented (planned for Phase 2)")


@app.command(name="load")
def load_cmd(
    source: Annotated[str, typer.Argument(help="File path or URL to the ontology.")],
    format_hint: Annotated[
        LoadFormatHint | None,
        typer.Option("--format", help="Format hint (auto-detected if absent)."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Treat warnings as errors."),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Network timeout in seconds (URL sources)."),
    ] = 30.0,
    base_iri: Annotated[
        str | None,
        typer.Option("--base-iri", help="Base IRI for relative references."),
    ] = None,
) -> None:
    """Load an ontology and print a summary (entity counts, IRI, prefixes)."""
    opts = LoadOptions(
        strict=strict,
        base_iri=base_iri,
        timeout_seconds=timeout,
        format_hint=format_hint.value if format_hint is not None else None,
    )
    snapshot = _load_ontology(source, opts)
    render_summary(snapshot)


@app.command(name="canonicalize")
def canonicalize_cmd(
    source: Annotated[str, typer.Argument(help="File path or URL to the ontology.")],
    format_hint: Annotated[
        LoadFormatHint | None,
        typer.Option("--format", help="Format hint (passed to loader)."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output file (default: stdout)."),
    ] = None,
    output_format: Annotated[
        CanonicalOutputFormat,
        typer.Option("--output-format", help="Serialization for output."),
    ] = CanonicalOutputFormat.turtle,
    no_blank_nodes: Annotated[
        bool,
        typer.Option("--no-blank-nodes", help="Skip blank node canonicalization."),
    ] = False,
    no_reify_restrictions: Annotated[
        bool,
        typer.Option("--no-reify-restrictions", help="Skip restriction reification."),
    ] = False,
    no_collapse_lists: Annotated[
        bool,
        typer.Option("--no-collapse-lists", help="Skip list collapsing."),
    ] = False,
    no_sort: Annotated[
        bool,
        typer.Option("--no-sort", help="Skip triple sorting."),
    ] = False,
) -> None:
    """Canonicalize an ontology and emit the normalized form."""
    load_opts = LoadOptions(
        format_hint=format_hint.value if format_hint is not None else None,
    )
    snapshot = _load_ontology(source, load_opts)
    # Quad formats (TriG, N-Quads) may carry named graphs; the loader parses
    # into a plain Graph and silently merges them, so we re-parse into a
    # ConjunctiveGraph here purely to surface a CanonicalizationError on
    # named-graph input (spec § Edge cases — exit code 4).
    if snapshot.format in ("trig", "nquads"):
        _check_quad_source_has_no_named_graphs(source, snapshot.format, load_opts)
    canon_opts = CanonicalizeOptions(
        canonicalize_blank_nodes=not no_blank_nodes,
        reify_restrictions=not no_reify_restrictions,
        collapse_lists=not no_collapse_lists,
        sort_triples=not no_sort,
    )
    canonical = _canonicalize(snapshot, canon_opts)
    serialized = canonical.graph.serialize(format=_CANONICAL_RDFLIB_FORMAT[output_format])
    if isinstance(serialized, bytes):
        serialized = serialized.decode("utf-8")
    if out is not None:
        out.write_text(serialized, encoding="utf-8")
    else:
        typer.echo(serialized, nl=False)


def _check_quad_source_has_no_named_graphs(
    source: str, normalized_format: str, load_opts: LoadOptions
) -> None:
    resolved = _resolve_source(source, timeout_seconds=load_opts.timeout_seconds)
    rdflib_format = "trig" if normalized_format == "trig" else "nquads"
    dataset = rdflib.Dataset()
    dataset.parse(data=resolved.content, format=rdflib_format)
    default_id = dataset.default_graph.identifier
    for ctx in dataset.graphs():
        if ctx.identifier != default_id and len(ctx) > 0:
            raise CanonicalizationError("named graphs not supported in v1")


def _configure_console_encoding() -> None:
    """Force stdout/stderr to UTF-8 (Windows consoles otherwise default to a
    legacy code page that mangles em-dash, arrows, and other glyphs the rich
    renderer emits). ``errors="replace"`` keeps the CLI alive if some exotic
    glyph still can't be encoded on the target codepage.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns an exit code. Used by tests and the console script."""
    _configure_console_encoding()
    try:
        result = app(args=argv, standalone_mode=False)
    except Exit as exc:
        return int(exc.exit_code)
    except Abort:
        print("Aborted.", file=sys.stderr)
        return 130
    except ClickException as exc:
        exc.show()
        return int(exc.exit_code)
    except OwlCompareError as exc:
        logger.error("%s", exc)
        return exc.exit_code
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception:
        logger.debug("Unhandled exception", exc_info=True)
        logger.error("An unexpected error occurred. Re-run with -v for details.")
        return 1
    return result if isinstance(result, int) else 0
