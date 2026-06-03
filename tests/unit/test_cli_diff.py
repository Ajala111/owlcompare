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
SEV = FIXTURES / "severity"


def _fx(name: str) -> str:
    return str(DIFF / name)


def _sev(name: str) -> str:
    return str(SEV / name)


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


def test_cli_diff_layers_structural_without_syntactic_exits_4():
    # Structural is implemented now, but Layer 1 depends on Layer 0: requesting
    # it alone is a DiffError (exit 4), not a usage error.
    assert (
        main(["diff", _fx("identical_a.ttl"), _fx("identical_b.ttl"), "--layers", "structural"])
        == 4
    )


def test_cli_diff_layers_inferential_exits_2():
    # Layers 2/3 remain stubbed → NotImplementedYetError (exit 2).
    assert (
        main(["diff", _fx("identical_a.ttl"), _fx("identical_b.ttl"), "--layers", "inferential"])
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


def test_cli_diff_default_layers_now_include_structural(capsys):
    main(["diff", _fx("class_added_before.ttl"), _fx("class_added_after.ttl"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert any(c["layer"] == "structural" for c in payload["changes"])


def test_cli_diff_text_output_groups_by_layer(capsys):
    main(["diff", _fx("era_evolution_v1.ttl"), _fx("era_evolution_v2.ttl")])
    out = capsys.readouterr().out
    assert "Layer 1 — Structural" in out
    assert "Layer 0 — Syntactic" in out


def test_cli_diff_text_output_hides_subsumed_layer0_by_default(capsys):
    # ex:Dog's rdf:type/label triple additions are subsumed by "Class added";
    # by default the Layer 0 section shows zero unexplained and the subsumed
    # triple rows (the type declaration "owl:Class") never appear.
    main(["diff", _fx("class_added_before.ttl"), _fx("class_added_after.ttl")])
    out = capsys.readouterr().out
    assert "Class added: ex:Dog" in out
    assert "0 unexplained" in out
    assert "owl:Class" not in out


def test_cli_diff_show_syntactic_flag_reveals_all_layer0(capsys):
    main(
        [
            "diff",
            _fx("class_added_before.ttl"),
            _fx("class_added_after.ttl"),
            "--show-syntactic",
        ]
    )
    out = capsys.readouterr().out
    # The previously-hidden type-declaration triple is now visible.
    assert "owl:Class" in out


def test_cli_diff_text_output_shows_unexplained_count(capsys):
    main(["diff", _fx("era_evolution_v1.ttl"), _fx("era_evolution_v2.ttl")])
    out = capsys.readouterr().out
    assert "unexplained)" in out


def test_cli_diff_json_includes_subsumes_in_details(capsys):
    main(["diff", _fx("class_added_before.ttl"), _fx("class_added_after.ttl"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    structural = [c for c in payload["changes"] if c["layer"] == "structural"]
    assert structural
    assert structural[0]["details"]["subsumes"]


def test_cli_diff_json_includes_change_id_in_details(capsys):
    main(["diff", _fx("class_added_before.ttl"), _fx("class_added_after.ttl"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert all("change_id" in c["details"] for c in payload["changes"])


def test_cli_diff_table_has_no_truncation_artifacts(capsys):
    # era_evolution involves restriction URNs; the display layer must shorten
    # them so no full URN leaks and no ellipsis truncates restriction rows.
    # Since Component 08 those triples are subsumed and hidden by default, so we
    # ask for --show-syntactic to bring the (shortened) URN rows back into view.
    rc = main(
        ["diff", _fx("era_evolution_v1.ttl"), _fx("era_evolution_v2.ttl"), "--show-syntactic"]
    )
    assert rc == 10
    out = capsys.readouterr().out
    assert "_restriction:" in out
    assert "urn:owlcompare:restriction:" not in out
    restriction_lines = [line for line in out.splitlines() if "_restriction:" in line]
    assert restriction_lines
    for line in restriction_lines:
        assert "…" not in line  # Unicode ellipsis from summary truncation


# --------------------------------------------------------------------------- #
# Component 10 — severity config / refinement flags
# --------------------------------------------------------------------------- #


def test_cli_diff_severity_config_flag_loads_config():
    # A valid config loads and the diff completes; era:locatedOn is still removed
    # (kept breaking by the "*_removed structural -> breaking" override) -> exit 10.
    rc = main(
        [
            "diff",
            _fx("era_evolution_v1.ttl"),
            _fx("era_evolution_v2.ttl"),
            "--severity-config",
            _sev("valid_config.toml"),
        ]
    )
    assert rc == 10


def test_cli_diff_severity_config_missing_file_exits_2():
    rc = main(
        [
            "diff",
            _fx("identical_a.ttl"),
            _fx("identical_b.ttl"),
            "--severity-config",
            _sev("nope.toml"),
        ]
    )
    assert rc == 2


def test_cli_diff_severity_config_malformed_exits_6():
    rc = main(
        [
            "diff",
            _fx("identical_a.ttl"),
            _fx("identical_b.ttl"),
            "--severity-config",
            _sev("malformed.toml"),
        ]
    )
    assert rc == 6


def test_cli_diff_no_severity_refinement_flag_skips_classifier(capsys):
    main(
        [
            "diff",
            _fx("era_evolution_v1.ttl"),
            _fx("era_evolution_v2.ttl"),
            "--no-severity-refinement",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    # The audit trail is present but empty, and Rule 6 did NOT run: a subsumed
    # Layer 0 removal keeps its original breaking severity.
    assert payload["metadata"]["severity_refinements"] == []
    syntactic_breaking = [
        c for c in payload["changes"] if c["layer"] == "syntactic" and c["severity"] == "breaking"
    ]
    assert syntactic_breaking


def test_cli_diff_explain_severity_flag_prints_refinement_panel(capsys):
    main(
        [
            "diff",
            _fx("era_evolution_v1.ttl"),
            _fx("era_evolution_v2.ttl"),
            "--explain-severity",
        ]
    )
    out = capsys.readouterr().out
    assert "Severity explanations" in out
    assert "subsumed-layer0-info" in out


def test_cli_diff_json_includes_severity_refinements_in_metadata(capsys):
    main(["diff", _fx("era_evolution_v1.ttl"), _fx("era_evolution_v2.ttl"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    refinements = payload["metadata"]["severity_refinements"]
    assert isinstance(refinements, list)
    # era_evolution subsumes plenty of Layer 0 changes -> Rule 6 fires.
    assert any(r["rule_id"] == "subsumed-layer0-info" for r in refinements)


def test_cli_diff_exit_code_respects_user_override():
    # demote_all forces every change (including the breaking property removal) to
    # info, so the diff exits 0 even though structurally it is a breaking change.
    rc = main(
        [
            "diff",
            _fx("era_evolution_v1.ttl"),
            _fx("era_evolution_v2.ttl"),
            "--severity-config",
            _sev("demote_all.toml"),
        ]
    )
    assert rc == 0
