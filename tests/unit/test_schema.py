"""Acceptance tests for the JSON Schema lockdown — specs/14-json-schema.md.

Covers the schema-loading helpers, the validator's accept/reject behaviour
against the curated ``tests/schema`` fixtures, and the error-message contract
(JSON pointer + human description). Forward-compatibility (unknown ``kind``
accepted, strictness on known kinds) is pinned here so a future schema edit that
breaks either rule fails the build.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from owlcompare.exceptions import SchemaValidationError
from owlcompare.schema import load_schema, schema_version, validate_diff_json

SCHEMA_FIXTURES = Path(__file__).resolve().parent.parent / "schema"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_FIXTURES / name).read_text(encoding="utf-8"))


def _minimal_change(kind: str, details: dict[str, Any], **over: Any) -> dict[str, Any]:
    """A Change object with every required field present (details supplied by caller)."""
    change = {
        "layer": "structural",
        "kind": kind,
        "severity": "info",
        "subject": "http://example.org/X",
        "summary": f"{kind} on ex:X",
        "details": details,
        "before": None,
        "after": None,
    }
    change.update(over)
    return change


def _minimal_payload(changes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "summary": {"added": 0, "removed": 0, "total": len(changes or []), "breaking": 0},
        "changes": changes or [],
        "metadata": {"severity_refinements": []},
    }


# --------------------------------------------------------------------------- #
# Schema-loading helpers
# --------------------------------------------------------------------------- #


def test_load_schema_returns_valid_schema_object():
    schema = load_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    # The document is itself a valid JSON Schema.
    jsonschema.Draft202012Validator.check_schema(schema)


def test_load_schema_has_required_top_level_fields():
    schema = load_schema()
    assert set(schema["required"]) == {"schema_version", "summary", "changes"}


def test_schema_version_constant_matches_schema_file():
    schema = load_schema()
    assert schema_version() == schema["properties"]["schema_version"]["const"]


# --------------------------------------------------------------------------- #
# Accepting real output (the curated fixtures)
# --------------------------------------------------------------------------- #


def test_validate_empty_changes_array():
    # No raise == valid.
    validate_diff_json(_load_fixture("empty.json"))


def test_validate_single_class_added_change():
    validate_diff_json(_load_fixture("simple_class_added.json"))


def test_validate_era_evolution_canonical_output():
    validate_diff_json(_load_fixture("era_evolution.json"))


def test_validate_era_renames_output():
    payload = _load_fixture("era_renames.json")
    assert any(c["kind"].endswith("_renamed") for c in payload["changes"])
    validate_diff_json(payload)


def test_validate_severity_refinements_section():
    payload = _load_fixture("with_severity_overrides.json")
    assert payload["metadata"]["severity_refinements"]
    validate_diff_json(payload)


def test_validate_cycle_introduced_kind():
    payload = _load_fixture("cycle_introduced.json")
    assert any(c["kind"] == "class_hierarchy_cycle_introduced" for c in payload["changes"])
    validate_diff_json(payload)


def test_validate_restriction_changed_with_full_before_after():
    payload = _load_fixture("restrictions_complex.json")
    changed = [c for c in payload["changes"] if c["kind"] == "restriction_changed"]
    assert changed
    # The before/after carry the decoded restriction dict, not null.
    assert changed[0]["details"]["before"]["kind"]
    assert changed[0]["details"]["after"]["kind"]
    validate_diff_json(payload)


def test_validate_complex_class_expression_kind():
    change = _minimal_change(
        "complex_class_expression_changed",
        {
            "entity_iri": "http://example.org/X",
            "depth": 3,
            "note": "Deep class expression change; structured diff deferred to v2.",
            "subsumes": [],
            "change_id": "structural:complex_class_expression_changed:abc",
        },
        severity="breaking",
    )
    validate_diff_json(_minimal_payload([change]))


# --------------------------------------------------------------------------- #
# Rejecting malformed output
# --------------------------------------------------------------------------- #


def test_validate_missing_required_field_raises():
    payload = _load_fixture("simple_class_added.json")
    del payload["summary"]
    with pytest.raises(SchemaValidationError):
        validate_diff_json(payload)


def test_validate_invalid_severity_value_raises():
    payload = _load_fixture("simple_class_added.json")
    payload["changes"][0]["severity"] = "catastrophic"
    with pytest.raises(SchemaValidationError):
        validate_diff_json(payload)


def test_validate_invalid_layer_value_raises():
    payload = _load_fixture("simple_class_added.json")
    payload["changes"][0]["layer"] = "inferential"
    with pytest.raises(SchemaValidationError):
        validate_diff_json(payload)


def test_validate_invalid_schema_version_raises():
    payload = _load_fixture("simple_class_added.json")
    payload["schema_version"] = 2
    with pytest.raises(SchemaValidationError):
        validate_diff_json(payload)


def test_validate_unknown_kind_accepted():
    # Forward-compat (Q2): an unknown kind with an arbitrary details object is
    # accepted as long as the surrounding Change structure is intact.
    change = _minimal_change("some_future_kind_v2", {"whatever": True, "nested": {"x": 1}})
    validate_diff_json(_minimal_payload([change]))


def test_validate_unknown_details_field_in_known_kind_raises():
    # Strict on known kinds: a class_added carrying an extra details key fails.
    payload = _load_fixture("simple_class_added.json")
    structural = next(c for c in payload["changes"] if c["kind"] == "class_added")
    structural["details"]["surprise"] = "unexpected"
    with pytest.raises(SchemaValidationError):
        validate_diff_json(payload)


def test_validate_extra_top_level_field_raises():
    payload = _load_fixture("simple_class_added.json")
    payload["unexpected_top_level"] = 1
    with pytest.raises(SchemaValidationError):
        validate_diff_json(payload)


# --------------------------------------------------------------------------- #
# Error-message contract
# --------------------------------------------------------------------------- #


def test_validation_error_includes_json_pointer():
    payload = _load_fixture("simple_class_added.json")
    payload["changes"][0]["severity"] = "catastrophic"
    with pytest.raises(SchemaValidationError) as exc:
        validate_diff_json(payload)
    # The pointer locates the offending field within the document.
    assert "/changes/0/severity" in str(exc.value)


def test_validation_error_includes_human_description():
    payload = _load_fixture("simple_class_added.json")
    del payload["summary"]
    with pytest.raises(SchemaValidationError) as exc:
        validate_diff_json(payload)
    # jsonschema's own wording is preserved after the pointer.
    assert "summary" in str(exc.value)
    assert "required" in str(exc.value).lower()


def test_schema_validation_error_exit_code_is_5():
    assert SchemaValidationError("x").exit_code == 5
