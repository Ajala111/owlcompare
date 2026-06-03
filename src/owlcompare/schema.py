"""Loading and validation of the published DiffResult JSON Schema (Component 14).

The schema lives at ``docs/schema/diff-result.schema.json`` — the single
canonical artifact, referenced by external tools and bundled into the wheel as
package data (see ``pyproject.toml`` ``force-include`` and DD-019/DD-020).

``validate_diff_json`` is the contract enforcement point: every CLI JSON test
runs its output through it (so drift breaks the build), and ``owlcompare diff
--validate-schema`` opts production callers into the same check. ``jsonschema``
is a *dev-only* dependency (DD-020); importing this module at runtime is only
needed when validation is requested, so the import is deferred into the
validating function rather than taken at module load.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from owlcompare.exceptions import SchemaValidationError

# The schema's top-level ``schema_version`` const. Kept in lockstep with the
# ``schema_version`` field that ``_render_diff.diff_json`` emits; the test
# ``test_schema_version_constant_matches_schema_file`` pins the two together.
SCHEMA_VERSION = 1

_SCHEMA_RESOURCE = ("schema", "diff-result.schema.json")
_SCHEMA_FILENAME = "diff-result.schema.json"


def _schema_text() -> str:
    """Read the bundled schema file, falling back to the source tree in dev.

    Installed wheels carry the schema as package data under
    ``owlcompare/schema/`` (``pyproject.toml`` ``force-include``), reachable via
    :mod:`importlib.resources`. Editable / source checkouts (how the test suite
    runs) keep only the canonical copy under ``docs/schema/``; there the bundled
    resource is absent, so we resolve the repo-relative path instead.
    """
    bundled = resources.files("owlcompare").joinpath(*_SCHEMA_RESOURCE)
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[2]
    source_copy = repo_root / "docs" / "schema" / _SCHEMA_FILENAME
    return source_copy.read_text(encoding="utf-8")


def load_schema() -> dict[str, Any]:
    """Load and parse the bundled DiffResult JSON Schema.

    Returns:
        The parsed JSON Schema (2020-12) document as a dict.
    """
    return json.loads(_schema_text())  # type: ignore[no-any-return]


def schema_version() -> int:
    """Return the current schema version (currently 1)."""
    return SCHEMA_VERSION


def validate_diff_json(data: dict[str, Any]) -> None:
    """Validate a DiffResult JSON payload against the bundled schema.

    Args:
        data: A parsed DiffResult JSON object (``json.loads`` of the output).

    Raises:
        SchemaValidationError: on the first conformance failure. The message
            carries the JSON pointer to the offending field plus jsonschema's
            human-readable description. Returns ``None`` on success.
    """
    # Deferred import: jsonschema is a dev-only dependency (DD-020) and is only
    # needed when validation is actually requested.
    import jsonschema

    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    error = jsonschema.exceptions.best_match(validator.iter_errors(data))
    if error is None:
        return
    pointer = _json_pointer(error)
    raise SchemaValidationError(f"schema validation failed at {pointer}: {error.message}")


def _json_pointer(error: Any) -> str:
    """RFC-6901-style pointer to the offending field (``<root>`` for the top)."""
    if not error.absolute_path:
        return "<root>"
    return "/" + "/".join(str(part) for part in error.absolute_path)
