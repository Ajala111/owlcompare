# Component 14: JSON Schema Lockdown

## Identity

- **Component number:** 14
- **Name:** JSON schema lockdown
- **Module paths:**
  - `docs/schema/diff-result.schema.json` — the formal schema (JSON Schema 2020-12)
  - `docs/schema/diff-result.md` — human-readable companion
  - `src/owlcompare/schema.py` — schema loading + validation helpers
  - `src/owlcompare/report/json_report.py` — extended with validation hook
  - `tests/schema/` — example payloads used as schema test fixtures
- **Roadmap phase:** Phase 4 (first component)
- **Depends on components:** 05–12 (all the layers and refinements that contribute to the JSON output today)
- **Depended on by (planned):** 15 (Markdown), 16/17 (HTML), 18 (JUnit XML), 19 (GitHub Action), all future external consumers

## Purpose

Promote the implicit JSON output format to an explicit, versioned, validated contract. After this component, `owlcompare diff --format json` produces output that conforms to a published JSON Schema; every CI run validates the JSON against the schema; and the schema becomes the canonical reference for any downstream tool consuming the output.

What would break if we removed it: the JSON output would remain implicit, and every renderer/downstream tool would handle its quirks slightly differently. Schema evolution would be undisciplined — future changes might silently break consumers. There would be no machine-readable contract to point integrators at.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Existing `DiffResult` JSON outputs | dict (in-memory) | `json_report.py` | What we're formalizing |
| All JSON test fixtures from earlier components | files | `tests/fixtures/**` | Used to derive shape coverage |
| Component specs (05–12) | docs | `specs/` | Source of truth for what kinds exist |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `diff-result.schema.json` | JSON Schema file | Renderers, external tools, validators | The contract |
| `diff-result.md` | Markdown doc | Humans | Companion explainer |
| Validation helper API | Python function | Tests + future renderers | `validate_diff_json()` |
| Updated `DD-019` | doc entry | Project record | Compatibility policy |

## Public API

```python
# src/owlcompare/schema.py

from pathlib import Path
from typing import Any


def load_schema() -> dict[str, Any]:
    """Load the bundled JSON Schema for DiffResult outputs.

    The schema lives at docs/schema/diff-result.schema.json and is bundled
    with the package via importlib.resources.

    Returns the parsed schema dict.
    """


def validate_diff_json(data: dict[str, Any]) -> None:
    """Validate a DiffResult JSON payload against the bundled schema.

    Raises SchemaValidationError on any conformance failure. The error
    message includes the JSON pointer to the offending field and a
    human-readable description of what failed.

    Does not return anything on success.
    """


def schema_version() -> int:
    """Return the current schema version (an integer, currently 1)."""
```

Add to `src/owlcompare/exceptions.py`:

```python
class SchemaValidationError(OwlCompareError):
    """A JSON payload failed schema validation."""
    exit_code: int = 5  # report generation error
```

## Schema structure (v1)

The schema validates the top-level `DiffResult` JSON object as currently emitted by `json_report.py`. Required top-level fields:

```jsonc
{
  "schema_version": 1,                  // integer, required, currently always 1
  "summary": {                          // required object
    "added": <int>,
    "removed": <int>,
    "total": <int>,
    "breaking": <int>
  },
  "changes": [<Change>, ...],           // required array (may be empty)
  "metadata": {                         // optional object (always present in practice)
    "layer_counts": {                   // optional, per-layer change counts
      "syntactic": <int>,
      "structural": <int>
    },
    "subsumption_registry": { ... },    // optional, opaque registry contents
    "severity_refinements": [           // optional array of SeverityRefinement
      <SeverityRefinement>, ...
    ],
    "rename_candidates": [<Candidate>], // optional, all candidates considered
    "renames_applied": [<Candidate>]    // optional, accepted renames only
  }
}
```

### The `Change` object

Required fields on every Change:

```jsonc
{
  "layer": "syntactic" | "structural",
  "kind": <string>,                     // e.g. "triple_added", "class_renamed", etc.
  "severity": "breaking" | "non_breaking" | "additive" | "info",
  "subject": <string|null>,
  "summary": <string>,                  // human-readable one-liner
  "details": { ... },                   // see per-kind details below
  "before": <any|null>,
  "after": <any|null>
}
```

The `kind` field is *not* an enum in the schema — we allow new kinds to be added in v1 without bumping the version, as long as the surrounding structure stays the same. (Adding a new kind is forward-compatible: existing consumers either handle it or ignore it.) But for *documentation* purposes, the companion `.md` lists every kind that exists today.

### The `details` object — partial schemas by kind

The schema uses `oneOf` to specify per-kind detail shapes for the well-known kinds. For unknown kinds (forward-compat), it falls back to a permissive "any object" matcher.

Per-kind detail schemas to formalize:

**Layer 0 (syntactic):**
- `triple_added`, `triple_removed` — details = `{subject, predicate, object, subject_iri, predicate_iri, change_id}`

**Layer 1 — entities (Component 06):**
- `class_added`, `class_removed`, `object_property_added`, `object_property_removed`, `data_property_added`, `data_property_removed`, `annotation_property_added`, `annotation_property_removed`, `individual_added`, `individual_removed`, `datatype_added`, `datatype_removed`
- `entity_kind_changed`
- common shape: `{entity_iri, entity_kind, label?, language?, subsumes, change_id}`
- entity_kind_changed: `{entity_iri, from_kind, to_kind, subsumes, change_id}`

**Layer 1 — hierarchy (Component 07):**
- `class_parent_added`, `class_parent_removed` — `{entity_iri, entity_kind, parent_iri, subsumes, change_id}`
- `class_reparented` — `{entity_iri, entity_kind, parents_before, parents_after, direction, subsumes, change_id}`
- `property_parent_added`, `property_parent_removed`, `property_reparented` — analogous
- `class_hierarchy_cycle_introduced` — `{entity_iri, path, subsumes, change_id}`

**Layer 1 — restrictions (Component 08):**
- `restriction_added`, `restriction_removed`, `restriction_changed` — `{entity_iri, via_predicate, on_property, before?, after?, subsumes, change_id}`
- `domain_added`, `domain_removed`, `domain_changed`, `range_added`, `range_removed`, `range_changed` — `{property_iri, before?, after?, subsumes, change_id}`
- `equivalent_class_added`, `equivalent_class_removed`, `disjoint_added`, `disjoint_removed` — `{entity_iri, other_iri, subsumes, change_id}`
- `complement_set`, `complement_unset` — `{entity_iri, before?, after?, subsumes, change_id}`
- `complex_class_expression_changed` — `{entity_iri, depth, subsumes, note, change_id}`

**Layer 1 — annotations (Component 09):**
- `annotation_changed`, `annotation_added`, `annotation_removed` — `{entity_iri, predicate_iri, predicate_short, language?, before?, after?, value?, is_iri_value?, subsumes, change_id}`
- `entity_deprecated`, `entity_undeprecated` — `{entity_iri, subsumes, change_id}`
- `ontology_metadata_changed` — `{ontology_iri, predicate_iri, predicate_short, before?, after?, subsumes, change_id}`

**Rename (Components 11/12):**
- `class_renamed`, `object_property_renamed`, `data_property_renamed`, `annotation_property_renamed` — `{before_iri, after_iri, entity_kind, confidence, score, evidence, cascade_subsumes, subsumes, change_id}`

### The `SeverityRefinement` object

```jsonc
{
  "change_id": <string>,
  "original_severity": <severity enum>,
  "refined_severity": <severity enum>,
  "rule_id": <string>,                  // e.g., "user-override", "annotation-on-deprecated"
  "rationale": <string>
}
```

### The `RenameCandidate` object (in metadata)

```jsonc
{
  "removed_iri": <string>,
  "added_iri": <string>,
  "entity_kind": "class" | "object_property" | "data_property" | "annotation_property",
  "confidence": "certain" | "high" | "medium" | "low",
  "evidence": [<string>, ...],
  "score": <number, 0.0-1.0>
}
```

## Compatibility policy (DD-019)

Add to `docs/DESIGN_DECISIONS.md`:

**DD-019: JSON schema compatibility policy**

**Status:** accepted
**Date:** today

**Decision:** The JSON output schema is versioned via a top-level `schema_version` integer. v1 is the current shape after Component 14. Future changes follow these rules:

- **Forward-compatible (no version bump):** adding a new optional field; adding a new value to a non-enum string field (e.g., new `kind`); adding a new optional object to `details`.
- **Breaking (bump to v2):** removing a field; changing a field's type; making a previously-optional field required; renaming a field; changing the semantic meaning of an existing field; tightening a previously-permissive value range.
- **Schema evolution requires:** updating `diff-result.schema.json`, updating the companion `.md`, adding migration notes to a new "Schema versions" section in `DESIGN_DECISIONS.md`, and providing test fixtures for both the old and new schema in `tests/schema/`.

**Reasoning:**
- A formal contract is the difference between "an output format" and "a stable integration surface."
- Most downstream consumers will be machine-readable (CI scripts, language servers, dashboards). Silent breaks are expensive for them.
- Versioning forces deliberate evolution: a contributor who wants to remove a field has to think about it.

**Implication:** the schema becomes a first-class artifact of the project. Every PR that touches JSON output has to consider whether it's forward-compatible or version-bumping.

## CLI integration

Add one new flag to the `diff` subcommand:

```
owlcompare diff [OPTIONS] ONTOLOGY_A ONTOLOGY_B

  --validate-schema             Validate the JSON output against the bundled schema
                                before emitting. On failure, raise SchemaValidationError
                                (exit code 5) rather than emitting non-conforming JSON.
                                Default: off (validation in tests, not in production).
```

The default is *off* because validation overhead is non-trivial on large diffs (jsonschema validation of a 100k-change result could take seconds). Production users get the implicit guarantee that validation is run *in CI*; turning it on locally is for debugging or for ultra-cautious pipelines.

When `--format` is anything other than `json`, the flag has no effect (logged at DEBUG).

## Internal design

### Validation library choice

Use `jsonschema` from PyPI. The de-facto standard, MIT-licensed, well-maintained, supports 2020-12 draft. Add as a dev dependency only (not a runtime dependency) — validation runs in tests, not at runtime.

Add DD-020: "jsonschema as test-only dependency for schema validation."

### Schema file layout

`docs/schema/diff-result.schema.json`:

- Standard `$schema`, `$id`, `title`, `description` fields at top
- `$defs` for reusable shapes (Change, SeverityRefinement, RenameCandidate, the per-kind detail objects)
- Top-level `type: object` with `properties`, `required`, `additionalProperties: false`
- Uses `oneOf` over a discriminator-like pattern for per-kind `details` schemas: each variant requires specific keys.

Discriminator-style approach (illustrative):

```json
"Change": {
  "type": "object",
  "required": ["layer", "kind", "severity", "subject", "summary", "details", "before", "after"],
  "properties": {
    "layer": { "enum": ["syntactic", "structural"] },
    "kind": { "type": "string" },
    ...
  },
  "allOf": [
    { "if": { "properties": { "kind": { "const": "class_added" } } },
      "then": { "properties": { "details": { "$ref": "#/$defs/EntityDetails" } } } },
    ...
  ]
}
```

This is verbose but precise. The companion `.md` will explain the same structure in human prose.

### Test integration

For every CLI test that exercises `--format json`, automatically run the result through `validate_diff_json()`. Implementation: a pytest fixture (or autouse function) that intercepts JSON output and validates it before tests assert against specifics.

```python
@pytest.fixture
def assert_json_valid(monkeypatch):
    """Wrap CliRunner so every --format json invocation is schema-validated.

    Yields a function that wraps json.loads() and validates before returning.
    """
```

Apply to all 30+ existing CLI JSON tests. This catches drift: any future commit that emits non-conforming JSON breaks the build.

### Schema fixtures

`tests/schema/` contains 5–10 hand-curated JSON outputs representing the breadth of what owlcompare emits:

- `empty.json` — diff with no changes (schema requires `changes: []`, but should accept it).
- `simple_class_added.json` — single Layer 1 change.
- `era_evolution.json` — the canonical 5-change result.
- `era_renames.json` — with rename changes.
- `era_renames_with_additions.json` — Component 12's flagship.
- `with_severity_overrides.json` — severity_refinements populated.
- `restrictions_complex.json` — restriction_changed with full before/after detail shapes.
- `cycle_introduced.json` — class_hierarchy_cycle_introduced.

Each fixture is the captured output of a real `owlcompare diff --format json` invocation against existing TTL fixtures, hand-reviewed once. The schema validation test asserts each parses + validates cleanly.

### What "lockdown" means in practice

After this component, the contract is:

1. The schema file is in the repo, versioned with the code.
2. Every PR's CI run validates every JSON output against the schema.
3. Any PR that emits non-conforming JSON fails CI before review.
4. Schema changes are visible in PR diffs and discussed deliberately.
5. External consumers can point at `https://raw.githubusercontent.com/<owner>/owlcompare/main/docs/schema/diff-result.schema.json` for tooling.

## Dependencies to add

- `jsonschema` (dev only) — add to `[dependency-groups].dev` in `pyproject.toml`, not to the runtime deps. Document as DD-020.

## Acceptance tests

Located in `tests/unit/test_schema.py` (new file), plus modifications to every existing CLI JSON test.

### Test list

**`tests/unit/test_schema.py`:**

- [ ] `test_load_schema_returns_valid_schema_object`
- [ ] `test_load_schema_has_required_top_level_fields` — schema_version, summary, changes
- [ ] `test_schema_version_constant_matches_schema_file`
- [ ] `test_validate_empty_changes_array`
- [ ] `test_validate_single_class_added_change`
- [ ] `test_validate_era_evolution_canonical_output`
- [ ] `test_validate_era_renames_output`
- [ ] `test_validate_severity_refinements_section`
- [ ] `test_validate_cycle_introduced_kind`
- [ ] `test_validate_restriction_changed_with_full_before_after`
- [ ] `test_validate_complex_class_expression_kind`
- [ ] `test_validate_missing_required_field_raises`
- [ ] `test_validate_invalid_severity_value_raises`
- [ ] `test_validate_invalid_layer_value_raises`
- [ ] `test_validate_invalid_schema_version_raises`
- [ ] `test_validate_unknown_kind_accepted` — forward-compat
- [ ] `test_validate_unknown_details_field_in_known_kind_raises` — strict on known kinds
- [ ] `test_validate_extra_top_level_field_raises` — additionalProperties: false
- [ ] `test_validation_error_includes_json_pointer`
- [ ] `test_validation_error_includes_human_description`

**`tests/integration/test_schema_integration.py`:**

- [ ] `test_schema_validates_every_existing_fixture_in_tests_schema_dir`
- [ ] `test_owlcompare_diff_era_evolution_output_validates`
- [ ] `test_owlcompare_diff_era_renames_output_validates`
- [ ] `test_owlcompare_diff_with_severity_overrides_output_validates`

**Modifications to existing tests:**

- [ ] Every existing test in `test_cli_diff.py` that asserts on JSON output must also validate against the schema. Add via a pytest fixture, not inline duplication.

**CLI flag:**

- [ ] `test_cli_diff_validate_schema_flag_passes_for_valid_output`
- [ ] `test_cli_diff_validate_schema_flag_raises_for_synthetic_malformed`
- [ ] `test_cli_diff_validate_schema_flag_no_effect_on_text_output`

## Out of scope (deliberately)

- Schema validation at runtime by default (only in tests + opt-in CLI flag).
- Schema version 2 design. We're locking v1.
- Auto-generating the Python dataclasses from the schema. The dataclasses are source of truth; the schema mirrors them.
- A separate schema for the rename mapping TOML or severity config TOML. Those have small, well-defined surfaces; informal docs are fine.

## Open questions

- [ ] **Q1:** Should the schema use `additionalProperties: false` strictly everywhere, or allow unknown fields in `metadata` for forward-compatibility?
  **Proposed:** Strict on `Change`, `SeverityRefinement`, `RenameCandidate`, and `summary`. Permissive on `metadata` (allow unknown fields). Rationale: metadata is project-internal and tooling-extensible; the change objects are the public contract and should be tightly defined.

- [ ] **Q2:** Should the per-kind `details` schemas use `oneOf` (one variant must match) or `allOf` with `if`/`then` (apply variant constraints conditionally)?
  **Proposed:** `allOf` with `if`/`then`. `oneOf` would require exactly one variant to match, which makes unknown kinds fail. `allOf`/`if`/`then` applies the right detail schema for known kinds and falls through for unknown ones, satisfying forward-compatibility.

- [ ] **Q3:** Should `cascade_subsumes` and `subsumes` arrays have item-level uniqueness constraints?
  **Proposed:** No. The arrays carry change_ids that should be unique by construction; if they're not, that's a bug in the producer that the schema shouldn't have to enforce. Document expected uniqueness in the companion `.md`.

If you have a preference, override before implementing; otherwise proceed with the proposed answers.

## References

- `docs/ARCHITECTURE.md` § Public API surfaces
- `docs/DESIGN_DECISIONS.md` (this component adds DD-019, DD-020)
- JSON Schema specification: https://json-schema.org/draft/2020-12/json-schema-core
- jsonschema library: https://python-jsonschema.readthedocs.io/
- Component specs 05–12 for the source of truth on what kinds and detail shapes exist
