"""Acceptance tests for the ``owlcompare diff`` subcommand — specs/05-syntactic-diff.md.

Exit-code behaviour that depends on owlcompare's typed exceptions (usage errors,
not-implemented layers, the breaking-change signal) is exercised through
``cli.main``, which owns the exception -> exit-code mapping. ``CliRunner`` is used
only where Click itself produces the exit code (``--help``, missing arguments).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from owlcompare.cli import app, main

runner = CliRunner()
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"


def _fx(name: str) -> str:
    return str(DIFF / name)


def test_cli_diff_help_lists_layers_format_out(help_runner, clean):
    result = help_runner.invoke(app, ["diff", "--help"])
    assert result.exit_code == 0
    out = clean(result.output).lower()
    assert "--layers" in out
    assert "--format" in out
    assert "--out" in out


def test_cli_diff_missing_arguments_exits_2():
    result = runner.invoke(app, ["diff"])
    assert result.exit_code == 2


def test_cli_diff_identical_inputs_exits_0():
    assert main(["diff", _fx("identical_a.ttl"), _fx("identical_b.ttl")]) == 0


def test_cli_diff_layers_structural_only_exits_2():
    assert (
        main(["diff", _fx("identical_a.ttl"), _fx("identical_b.ttl"), "--layers", "structural"])
        == 2
    )


def test_cli_diff_layers_invalid_name_exits_2():
    assert main(["diff", _fx("identical_a.ttl"), _fx("identical_b.ttl"), "--layers", "bogus"]) == 2


def test_cli_diff_format_json_output_is_valid_json(capsys):
    rc = main(
        ["diff", _fx("added_class_before.ttl"), _fx("added_class_after.ttl"), "--format", "json"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "changes" in payload
    assert isinstance(payload["changes"], list)


def test_cli_diff_format_json_schema_version_field_present(capsys):
    main(["diff", _fx("added_class_before.ttl"), _fx("added_class_after.ttl"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1


def test_cli_diff_format_text_default_on_tty(capsys):
    # Under pytest capture stdout is not a TTY, so the plain text path runs; it
    # still carries prefixed (era:/ex:) forms, which is what the spec asks for.
    main(["diff", _fx("added_class_before.ttl"), _fx("added_class_after.ttl")])
    out = capsys.readouterr().out
    assert "triples added" in out
    assert "ex:Dog" in out


def test_cli_diff_added_class_fixture_shows_at_least_one_added_change(capsys):
    main(["diff", _fx("added_class_before.ttl"), _fx("added_class_after.ttl"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    added = [c for c in payload["changes"] if c["kind"] == "triple_added"]
    assert added


def test_cli_diff_writes_to_out_file(tmp_path: Path):
    out_path = tmp_path / "diff.json"
    rc = main(
        [
            "diff",
            _fx("added_class_before.ttl"),
            _fx("added_class_after.ttl"),
            "--format",
            "json",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["changes"]


def test_cli_diff_breaking_change_exits_10():
    # removed_class_* removes an rdfs:subClassOf axiom -> breaking.
    assert main(["diff", _fx("removed_class_before.ttl"), _fx("removed_class_after.ttl")]) == 10


def test_cli_diff_only_info_changes_exits_0():
    assert main(["diff", _fx("renamed_label_before.ttl"), _fx("renamed_label_after.ttl")]) == 0


def test_cli_diff_table_has_no_truncation_artifacts(capsys):
    # era_evolution involves restriction URNs; the display layer must shorten
    # them so no full URN leaks and no ellipsis truncates restriction rows.
    rc = main(["diff", _fx("era_evolution_v1.ttl"), _fx("era_evolution_v2.ttl")])
    assert rc == 10
    out = capsys.readouterr().out
    assert "_restriction:" in out
    assert "urn:owlcompare:restriction:" not in out
    restriction_lines = [line for line in out.splitlines() if "_restriction:" in line]
    assert restriction_lines
    for line in restriction_lines:
        assert "…" not in line  # Unicode ellipsis from summary truncation
