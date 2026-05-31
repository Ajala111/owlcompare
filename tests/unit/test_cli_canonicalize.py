"""Acceptance tests for the ``owlcompare canonicalize`` subcommand."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from owlcompare.cli import app, main

# Wide terminal so Typer's rich formatter doesn't truncate long option names
# (e.g. ``--no-reify-restrictions``) in the help panel.
runner = CliRunner(env={"COLUMNS": "200"})
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CANON_FIXTURES = FIXTURES / "canonicalize"

_RESTRICTION_PREFIX = "urn:owlcompare:restriction:"


def test_cli_canonicalize_help_lists_options():
    result = runner.invoke(app, ["canonicalize", "--help"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "--format" in out
    assert "--out" in out
    assert "--output-format" in out
    assert "--no-blank-nodes" in out
    assert "--no-reify-restrictions" in out
    assert "--no-collapse-lists" in out
    assert "--no-sort" in out
    assert "source" in out


def test_cli_canonicalize_missing_source_exits_2():
    result = runner.invoke(app, ["canonicalize"])
    assert result.exit_code == 2


def test_cli_canonicalize_minimal_fixture_exits_0_prints_turtle(capsys, monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    rc = main(["canonicalize", str(CANON_FIXTURES / "restriction_simple.ttl")])
    assert rc == 0
    captured = capsys.readouterr()
    # Turtle output should contain at least one prefix declaration.
    assert "@prefix" in captured.out
    assert _RESTRICTION_PREFIX in captured.out


def test_cli_canonicalize_output_format_nt_exits_0_prints_ntriples(capsys, monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    rc = main(
        [
            "canonicalize",
            "--output-format",
            "nt",
            str(CANON_FIXTURES / "restriction_simple.ttl"),
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    # N-Triples lines end with " .\n" and never use @prefix.
    assert "@prefix" not in captured.out
    assert " .\n" in captured.out


def test_cli_canonicalize_writes_to_out_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    out_path = tmp_path / "canonical.ttl"
    rc = main(
        [
            "canonicalize",
            "--out",
            str(out_path),
            str(CANON_FIXTURES / "restriction_simple.ttl"),
        ]
    )
    assert rc == 0
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert _RESTRICTION_PREFIX in content


def test_cli_canonicalize_no_blank_nodes_flag_propagates(capsys, monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    rc = main(
        [
            "canonicalize",
            "--no-blank-nodes",
            "--no-reify-restrictions",
            "--no-collapse-lists",
            str(CANON_FIXTURES / "restriction_simple.ttl"),
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    # With both reification and list collapsing disabled, no URN should appear.
    assert _RESTRICTION_PREFIX not in captured.out
    assert "urn:owlcompare:list:" not in captured.out


def test_cli_canonicalize_named_graph_input_exits_4(monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    rc = main(
        [
            "canonicalize",
            "--format",
            "trig",
            str(CANON_FIXTURES / "with_named_graph.trig"),
        ]
    )
    assert rc == 4
