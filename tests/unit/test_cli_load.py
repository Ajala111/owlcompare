"""Acceptance tests for the ``owlcompare load`` subcommand."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from owlcompare.cli import app, main

runner = CliRunner()
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

_NO_ONTOLOGY_TURTLE = (
    "@prefix : <http://example.org/no-onto#> .\n"
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    ":A a owl:Class .\n"
)


def test_cli_load_help_lists_options():
    result = runner.invoke(app, ["load", "--help"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "--format" in out
    assert "--strict" in out
    assert "--timeout" in out
    assert "--base-iri" in out
    assert "source" in out


def test_cli_load_missing_source_exits_2():
    result = runner.invoke(app, ["load"])
    assert result.exit_code == 2


def test_cli_load_minimal_fixture_exits_0_prints_summary(capsys, monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    rc = main(["load", str(FIXTURES / "minimal_class.ttl")])
    assert rc == 0
    captured = capsys.readouterr()
    assert "http://example.org/minimal" in captured.out
    assert "Entity counts:" in captured.out


def test_cli_load_broken_fixture_exits_3(monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    rc = main(["load", str(FIXTURES / "broken.ttl")])
    assert rc == 3


def test_cli_load_missing_file_exits_3(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    rc = main(["load", str(tmp_path / "nope.ttl")])
    assert rc == 3


def test_cli_load_strict_flag_propagates(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    path = tmp_path / "no_ontology.ttl"
    path.write_text(_NO_ONTOLOGY_TURTLE)

    # Without --strict, this loads cleanly.
    assert main(["load", str(path)]) == 0
    # With --strict, the missing owl:Ontology declaration fails the load.
    assert main(["load", "--strict", str(path)]) == 3
