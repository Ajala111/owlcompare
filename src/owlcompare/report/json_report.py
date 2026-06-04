"""JSON renderer for ``owlcompare diff`` — the versioned, schema-locked contract.

This is the canonical home of the JSON emitter (moved here in Component 15;
previously it lived in ``owlcompare._render_diff``). The output conforms to
``docs/schema/diff-result.schema.json`` (JSON Schema 2020-12) and is validated in
CI by the autouse wrapper in ``tests/conftest.py`` — see DD-019 (compatibility
policy) and DD-020 (``jsonschema`` as a test-only dependency).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from owlcompare.diff._common import Change
from owlcompare.diff.severity import SeverityRefinement

# JSON output contract version (specs/14-json-schema.md; DD-019). Kept in lockstep
# with ``owlcompare.schema.SCHEMA_VERSION`` by the schema test suite.
SCHEMA_VERSION = 1


def _counts(changes: list[Change]) -> dict[str, int]:
    added = sum(1 for c in changes if c.kind == "triple_added")
    removed = sum(1 for c in changes if c.kind == "triple_removed")
    breaking = sum(1 for c in changes if c.severity == "breaking")
    return {"added": added, "removed": removed, "total": len(changes), "breaking": breaking}


def change_to_dict(change: Change) -> dict[str, Any]:
    """Serialize one ``Change`` to a JSON-ready dict."""
    return {
        "layer": change.layer,
        "kind": change.kind,
        "severity": change.severity,
        "subject": change.subject,
        "summary": change.summary,
        "details": change.details,
        "before": change.before,
        "after": change.after,
    }


def refinement_to_dict(refinement: SeverityRefinement) -> dict[str, Any]:
    """Serialize one ``SeverityRefinement`` to a JSON-ready dict."""
    return {
        "change_id": refinement.change_id,
        "original_severity": refinement.original_severity,
        "refined_severity": refinement.refined_severity,
        "rule_id": refinement.rule_id,
        "rationale": refinement.rationale,
    }


def diff_json(
    changes: list[Change],
    refinements: Sequence[SeverityRefinement] = (),
) -> str:
    """Render the change list as schema-versioned JSON (all layers included).

    The top-level ``metadata.severity_refinements`` array is part of the v1 JSON
    schema (Component 10): always present, possibly empty.
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "summary": _counts(changes),
        "changes": [change_to_dict(c) for c in changes],
        "metadata": {
            "severity_refinements": [refinement_to_dict(r) for r in refinements],
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
