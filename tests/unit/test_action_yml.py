"""Static validation of the repo-root ``action.yml`` (Component 19).

These tests assert the GitHub Action metadata file is well-formed and that its
declared inputs/outputs stay in sync with the user-facing documentation. They do
not — and cannot — exercise the Action end-to-end; that requires a real GitHub
Actions runner and lives in ``.github/workflows/action-smoke-test.yml`` (manual).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTION_YML = _REPO_ROOT / "action.yml"
_ACTION_DOCS = _REPO_ROOT / "docs" / "github-action.md"

# The full set of inputs the spec (specs/19-github-action.md § Inputs) requires.
_EXPECTED_INPUTS = {
    "ontology-path",
    "baseline-ref",
    "formats",
    "python-version",
    "owlcompare-version",
    "fail-on-breaking",
    "post-pr-comment",
    "upload-artifacts",
    "severity-config",
    "rename-mapping",
    "rename-confidence",
    "comment-marker",
}

# The full set of outputs the spec (§ Outputs) requires.
_EXPECTED_OUTPUTS = {
    "breaking-count",
    "total-changes",
    "report-html-path",
    "report-junit-path",
    "report-markdown",
    "exit-code",
}


@pytest.fixture(scope="module")
def action() -> dict[str, Any]:
    """Parse ``action.yml`` once for the module."""
    return yaml.safe_load(_ACTION_YML.read_text(encoding="utf-8"))


def test_action_yml_is_valid_yaml() -> None:
    parsed = yaml.safe_load(_ACTION_YML.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)


def test_action_yml_lives_at_repo_root() -> None:
    # GitHub resolves `uses: owner/repo@ref` to `action.yml` at the repo root.
    assert _ACTION_YML.exists()


def test_action_yml_has_required_top_level_fields(action: dict[str, Any]) -> None:
    for field in ("name", "description", "runs"):
        assert field in action, f"missing required top-level field: {field}"


def test_action_yml_runs_using_is_composite(action: dict[str, Any]) -> None:
    assert action["runs"]["using"] == "composite"


def test_action_yml_has_steps(action: dict[str, Any]) -> None:
    steps = action["runs"]["steps"]
    assert isinstance(steps, list)
    assert len(steps) >= 1


def test_action_yml_declares_expected_inputs(action: dict[str, Any]) -> None:
    assert set(action["inputs"]) == _EXPECTED_INPUTS


def test_action_yml_inputs_all_have_descriptions(action: dict[str, Any]) -> None:
    for name, spec in action["inputs"].items():
        assert spec.get("description"), f"input '{name}' has no description"


def test_action_yml_ontology_path_is_required(action: dict[str, Any]) -> None:
    assert action["inputs"]["ontology-path"]["required"] is True


def test_action_yml_optional_inputs_have_defaults(action: dict[str, Any]) -> None:
    for name, spec in action["inputs"].items():
        if name == "ontology-path":
            continue
        # Every non-required input must carry a sensible default (the empty
        # string is a valid default for the optional-path inputs).
        assert "default" in spec, f"optional input '{name}' has no default"


def test_action_yml_declares_expected_outputs(action: dict[str, Any]) -> None:
    assert set(action["outputs"]) == _EXPECTED_OUTPUTS


def test_action_yml_outputs_all_have_descriptions(action: dict[str, Any]) -> None:
    for name, spec in action["outputs"].items():
        assert spec.get("description"), f"output '{name}' has no description"


def test_action_yml_outputs_all_have_values(action: dict[str, Any]) -> None:
    # Every output must be wired to a step output via the `value:` expression.
    for name, spec in action["outputs"].items():
        assert spec.get("value"), f"output '{name}' has no value expression"
        assert "steps.diff.outputs" in spec["value"], (
            f"output '{name}' is not wired to the diff step"
        )


def test_action_yml_uses_only_first_party_actions(action: dict[str, Any]) -> None:
    # The spec mandates no third-party Action dependencies.
    allowed_prefixes = ("actions/setup-python", "actions/upload-artifact", "actions/github-script")
    for step in action["runs"]["steps"]:
        uses = step.get("uses")
        if uses is None:
            continue
        assert uses.startswith(allowed_prefixes), f"unexpected third-party action: {uses}"


def test_action_yml_inputs_match_documented_set() -> None:
    # Cross-check: every declared input must be documented in the reference doc.
    docs_text = _ACTION_DOCS.read_text(encoding="utf-8")
    for name in _EXPECTED_INPUTS:
        assert name in docs_text, f"input '{name}' is not documented in docs/github-action.md"


def test_action_yml_outputs_documented() -> None:
    docs_text = _ACTION_DOCS.read_text(encoding="utf-8")
    for name in _EXPECTED_OUTPUTS:
        assert name in docs_text, f"output '{name}' is not documented in docs/github-action.md"


def test_action_yml_default_comment_marker_is_html_comment(action: dict[str, Any]) -> None:
    marker = action["inputs"]["comment-marker"]["default"]
    assert marker.startswith("<!--") and marker.endswith("-->")
