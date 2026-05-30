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
from owlcompare.exceptions import NotImplementedYetError, OwlCompareError
from owlcompare.loader import load as _load_ontology
from owlcompare.logging_config import configure_logging
from owlcompare.model import LoadOptions

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
