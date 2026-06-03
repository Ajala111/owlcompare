"""Acceptance tests for the ``owlcompare diff`` subcommand — specs/05-syntactic-diff.md.

Exit-code behaviour that depends on owlcompare's typed exceptions (usage errors,
not-implemented layers, the breaking-change signal) is exercised through
``cli.main``, which owns the exception -> exit-code mapping. ``CliRunner`` is used
only where Click itself produces the exit code (``--help``, missing arguments).
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from typer.testing import CliRunner

from owlcompare.cli import app, main

runner = CliRunner()
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"
SEV = FIXTURES / "severity"
RENAME = FIXTURES / "rename"


def _fx(name: str) -> str:
    return str(DIFF / name)


def _sev(name: str) -> str:
    return str(SEV / name)


def _ren(name: str) -> str:
    return str(RENAME / name)


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


# --------------------------------------------------------------------------- #
# Component 11 — rename detection flags
# --------------------------------------------------------------------------- #


def _rename_json(capsys, *args: str) -> dict:
    main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
            "--format",
            "json",
            *args,
        ]
    )
    return json.loads(capsys.readouterr().out)


def test_cli_diff_help_lists_rename_flags(help_runner, clean):
    result = help_runner.invoke(app, ["diff", "--help"])
    out = clean(result.output).lower()
    assert "--rename-mapping" in out
    assert "--rename-confidence" in out


def test_cli_diff_rename_mapping_flag_loads_mapping(capsys):
    main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
            "--format",
            "json",
            "--rename-mapping",
            _ren("valid_mapping.toml"),
            "--rename-confidence",
            "certain",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    renamed = [c for c in payload["changes"] if c["kind"] == "class_renamed"]
    assert len(renamed) == 1
    assert renamed[0]["details"]["confidence"] == "certain"


def test_cli_diff_rename_mapping_missing_file_exits_2():
    rc = main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
            "--rename-mapping",
            _ren("nope.toml"),
        ]
    )
    assert rc == 2


def test_cli_diff_rename_mapping_malformed_exits_6():
    rc = main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
            "--rename-mapping",
            _ren("mapping_malformed.toml"),
        ]
    )
    assert rc == 6


def test_cli_diff_rename_confidence_none_disables_detection(capsys):
    payload = _rename_json(capsys, "--rename-confidence", "none")
    kinds = {c["kind"] for c in payload["changes"]}
    assert "class_renamed" not in kinds
    assert "class_removed" in kinds
    assert "class_added" in kinds


def test_cli_diff_rename_confidence_certain_requires_mapping(capsys):
    # certain with no mapping -> nothing is asserted, so the label-match rename
    # is not detected (it stays a class_added + class_removed).
    payload = _rename_json(capsys, "--rename-confidence", "certain")
    kinds = {c["kind"] for c in payload["changes"]}
    assert "class_renamed" not in kinds
    assert "class_removed" in kinds


def test_cli_diff_rename_confidence_medium_enables_fingerprint(capsys):
    main(
        [
            "diff",
            _ren("fingerprint_rename_v1.ttl"),
            _ren("fingerprint_rename_v2.ttl"),
            "--format",
            "json",
            "--rename-confidence",
            "medium",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    renamed = [c for c in payload["changes"] if c["kind"] == "class_renamed"]
    assert len(renamed) == 1
    assert renamed[0]["details"]["confidence"] == "medium"


def test_cli_diff_text_output_shows_renames_specially(capsys):
    main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
        ]
    )
    out = capsys.readouterr().out
    assert "Renames" in out
    assert "renamed" in out.lower()


def test_cli_diff_json_includes_rename_evidence_and_confidence(capsys):
    payload = _rename_json(capsys)
    renamed = [c for c in payload["changes"] if c["kind"] == "class_renamed"]
    assert len(renamed) == 1
    details = renamed[0]["details"]
    assert "confidence" in details
    assert "evidence" in details
    assert "cascade_subsumes" in details


# --------------------------------------------------------------------------- #
# Component 12 Part B — --export-rename-mapping
# --------------------------------------------------------------------------- #


def test_cli_diff_export_rename_mapping_writes_file(tmp_path: Path):
    out_toml = tmp_path / "renames.toml"
    main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
            "--export-rename-mapping",
            str(out_toml),
        ]
    )
    data = tomllib.loads(out_toml.read_text(encoding="utf-8"))
    assert data["classes"] == [
        {
            "old": "http://data.europa.eu/949/Track",
            "new": "http://data.europa.eu/949/RailwayTrack",
        }
    ]


def test_cli_diff_export_rename_mapping_with_no_renames_writes_empty_file(tmp_path: Path):
    out_toml = tmp_path / "empty.toml"
    main(
        [
            "diff",
            _ren("no_rename_just_replacement_v1.ttl"),
            _ren("no_rename_just_replacement_v2.ttl"),
            "--export-rename-mapping",
            str(out_toml),
        ]
    )
    assert tomllib.loads(out_toml.read_text(encoding="utf-8")) == {"schema_version": 1}


def test_cli_diff_export_rename_mapping_with_rename_confidence_none_writes_empty(tmp_path: Path):
    out_toml = tmp_path / "none.toml"
    main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
            "--rename-confidence",
            "none",
            "--export-rename-mapping",
            str(out_toml),
        ]
    )
    assert tomllib.loads(out_toml.read_text(encoding="utf-8")) == {"schema_version": 1}


def test_cli_diff_export_rename_mapping_round_trip(capsys, tmp_path: Path):
    out_toml = tmp_path / "era.toml"
    main(
        [
            "diff",
            _ren("era_renames_v1.ttl"),
            _ren("era_renames_v2.ttl"),
            "--export-rename-mapping",
            str(out_toml),
        ]
    )
    capsys.readouterr()  # drain the first invocation's output
    main(
        [
            "diff",
            _ren("era_renames_v1.ttl"),
            _ren("era_renames_v2.ttl"),
            "--format",
            "json",
            "--rename-mapping",
            str(out_toml),
            "--rename-confidence",
            "certain",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    renamed = [c for c in payload["changes"] if c["kind"].endswith("_renamed")]
    assert len(renamed) == 3
    assert all(c["details"]["confidence"] == "certain" for c in renamed)


def test_cli_diff_export_rename_mapping_unwritable_path_exits_5(tmp_path: Path):
    # A directory path is not writable as a file -> RenameMappingError exit 5.
    rc = main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
            "--export-rename-mapping",
            str(tmp_path),
        ]
    )
    assert rc == 5


def test_cli_diff_export_does_not_suppress_normal_output(capsys, tmp_path: Path):
    out_toml = tmp_path / "renames.toml"
    main(
        [
            "diff",
            _ren("simple_class_rename_v1.ttl"),
            _ren("simple_class_rename_v2.ttl"),
            "--format",
            "json",
            "--export-rename-mapping",
            str(out_toml),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert any(c["kind"] == "class_renamed" for c in payload["changes"])
    assert out_toml.exists()
