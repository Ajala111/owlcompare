"""Integration tests for the JSON Schema lockdown — specs/14-json-schema.md.

End-to-end: drive ``owlcompare diff --format json`` through ``cli.main`` and
confirm the emitted payload validates, plus a sweep that validates every curated
fixture in ``tests/schema``. These complement the autouse wrapper in
``tests/conftest.py`` by asserting validity explicitly rather than implicitly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from owlcompare.cli import main
from owlcompare.schema import validate_diff_json

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"
RENAME = FIXTURES / "rename"
SEV = FIXTURES / "severity"
SCHEMA_FIXTURES = Path(__file__).resolve().parent.parent / "schema"


def _diff_json(capsys: pytest.CaptureFixture[str], *args: str) -> dict:
    main(["diff", *args, "--format", "json"])
    return json.loads(capsys.readouterr().out)


def test_schema_validates_every_existing_fixture_in_tests_schema_dir():
    fixtures = sorted(SCHEMA_FIXTURES.glob("*.json"))
    assert fixtures  # guard against an empty directory silently passing
    for path in fixtures:
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_diff_json(payload)  # no raise == valid


def test_owlcompare_diff_era_evolution_output_validates(capsys):
    payload = _diff_json(
        capsys, str(DIFF / "era_evolution_v1.ttl"), str(DIFF / "era_evolution_v2.ttl")
    )
    validate_diff_json(payload)


def test_owlcompare_diff_era_renames_output_validates(capsys):
    payload = _diff_json(
        capsys, str(RENAME / "era_renames_v1.ttl"), str(RENAME / "era_renames_v2.ttl")
    )
    assert any(c["kind"].endswith("_renamed") for c in payload["changes"])
    validate_diff_json(payload)


def test_owlcompare_diff_with_severity_overrides_output_validates(capsys):
    payload = _diff_json(
        capsys,
        str(DIFF / "era_evolution_v1.ttl"),
        str(DIFF / "era_evolution_v2.ttl"),
        "--severity-config",
        str(SEV / "demote_all.toml"),
    )
    assert payload["metadata"]["severity_refinements"]
    validate_diff_json(payload)
