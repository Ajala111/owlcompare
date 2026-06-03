"""Project-wide test fixtures.

Component 14 lockdown: every in-process ``owlcompare diff --format json``
invocation is schema-validated. The ``_schema_validate_cli_json`` fixture
(autouse) wraps :func:`owlcompare.cli.diff_json` so the rendered payload is run
through :func:`owlcompare.schema.validate_diff_json` before it is returned to the
CLI. The wrapper returns the byte-identical string, so it changes no assertion —
it only fails the build if any test ever emits JSON that does not conform to the
published schema. That is the whole point of the lockdown: drift breaks CI.

A test that deliberately produces malformed JSON (to exercise the
``--validate-schema`` flag) overrides ``owlcompare.cli.diff_json`` in its own
body; that later ``monkeypatch.setattr`` replaces this wrapper for that test.
"""

from __future__ import annotations

import json

import pytest

from owlcompare import cli as _cli
from owlcompare.schema import validate_diff_json


@pytest.fixture(autouse=True)
def _schema_validate_cli_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate every CLI-rendered JSON payload against the bundled schema."""
    original = _cli.diff_json

    def wrapped(*args: object, **kwargs: object) -> str:
        rendered = original(*args, **kwargs)  # type: ignore[arg-type]
        validate_diff_json(json.loads(rendered))
        return rendered

    monkeypatch.setattr(_cli, "diff_json", wrapped)
