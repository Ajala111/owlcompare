# Component 05: Layer 0 Syntactic Diff

## Identity

- **Component number:** 05
- **Name:** Layer 0 syntactic diff
- **Module paths:**
  - `src/owlcompare/diff/__init__.py` — package init, exports `Change`, `DiffResult`, `diff()`
  - `src/owlcompare/diff/_common.py` — `Change`, `DiffResult`, `DiffOptions`, severity helpers (shared by all layers)
  - `src/owlcompare/diff/syntactic.py` — Layer 0 implementation
- **Roadmap phase:** Phase 2 (first component)
- **Depends on components:** 02 (snapshot/model), 04 (canonicalize)
- **Depended on by (planned):** 06–09 (Layer 1 structural), 10 (severity classifier), 14–17 (report renderers)

## Purpose

Implement the simplest, most complete diff layer: a canonicalized triple-set difference. After canonicalization, two ontologies are two sets of triples; Layer 0 is the asymmetric difference — triples in A but not in B, triples in B but not in A.

This is the safety net beneath every other layer. Layers 1–3 *interpret* triples (this is a class deletion, this is a cardinality change, etc.) and can therefore have blind spots. Layer 0 reports every triple-level change without interpretation, guaranteeing nothing is silently missed. Users can always drill down past summarization to see the raw triple deltas.

What would break if we removed it: every diff layer would need its own fallback for "triples we didn't recognize," and we'd lose the audit trail that confirms higher layers are complete.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Snapshot A | `OntologySnapshot` | Loader + Canonicalize | Must have `canonical=True`; assertion at function entry |
| Snapshot B | `OntologySnapshot` | Loader + Canonicalize | Same |
| Options | `DiffOptions` | Optional | Layer filters, severity overrides, future tuning |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `list[Change]` | list | Diff orchestrator / renderers | Stable ordering; deterministic for identical inputs |

Note: `DiffResult` (the top-level type that aggregates changes from all layers) is *defined* here but constructed by the diff orchestrator in a later component. Layer 0 itself returns just `list[Change]`.

## Public API

```python
# src/owlcompare/diff/_common.py

from dataclasses import dataclass, field
from typing import Any, Literal

DiffLayer = Literal["syntactic", "structural", "inferential", "impact"]
Severity = Literal["breaking", "non_breaking", "additive", "info"]


@dataclass(frozen=True, slots=True)
class Change:
    """A single record describing one difference between two snapshots."""
    layer: DiffLayer
    kind: str                                  # e.g., "triple_added", "triple_removed"
    severity: Severity
    subject: str | None                        # IRI of the affected entity, when applicable
    summary: str                               # one-line human description
    details: dict[str, Any] = field(default_factory=dict)
    before: Any | None = None
    after: Any | None = None


@dataclass(frozen=True, slots=True)
class DiffOptions:
    """Diff invocation knobs."""
    include_layers: tuple[DiffLayer, ...] = ("syntactic", "structural", "inferential", "impact")
    # Layer-specific knobs added later; deliberately empty for v1 syntactic.


@dataclass(frozen=True)
class DiffResult:
    """Aggregated diff output (populated by the orchestrator; defined here for shared use)."""
    a: "OntologySnapshot"                      # forward ref to avoid circular import
    b: "OntologySnapshot"
    changes: tuple[Change, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
```

```python
# src/owlcompare/diff/syntactic.py

from owlcompare.model import OntologySnapshot
from ._common import Change, DiffOptions


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    options: DiffOptions | None = None,
) -> list[Change]:
    """Compute Layer 0 (syntactic / triple-set) differences between two canonicalized snapshots.

    Preconditions:
        a.canonical and b.canonical must both be True.

    Returns:
        A list of Change records with layer='syntactic'. Empty list if snapshots are
        triple-set-equal. Ordering is deterministic across runs for identical inputs.
    """
```

Also export from the package root:

```python
# src/owlcompare/diff/__init__.py
from ._common import Change, DiffOptions, DiffResult, Severity, DiffLayer
from . import syntactic

__all__ = ["Change", "DiffOptions", "DiffResult", "Severity", "DiffLayer", "syntactic"]
```

## CLI integration

The `diff` subcommand is currently a stub (raises `NotImplementedYetError` with exit code 2). This component **partially implements** it: when only `--layers syntactic` is requested, the stub becomes real. Other layers remain stubbed.

Replace the stub body with:

```
owlcompare diff [OPTIONS] ONTOLOGY_A ONTOLOGY_B

Arguments:
  ONTOLOGY_A    Path or URL to the baseline ontology  [required]
  ONTOLOGY_B    Path or URL to the comparison ontology  [required]

Options:
  --layers TEXT     Comma-separated layer list (e.g., "syntactic" or "syntactic,structural").
                    Default: "syntactic" (only one fully implemented in v1).
  --format [json|text]
                    Output format. Default: "text" (compact summary on TTY, plain on non-TTY).
                    Other formats (markdown, html, junit) added in Phase 4.
  --out PATH        Output file (default: stdout for text/json).
  --help            Show this message and exit.
```

Behavior when `--layers syntactic` is requested:
1. Load A and B via the loader.
2. Canonicalize both.
3. Call `syntactic.diff(a, b)`.
4. Render the result:
   - **`--format text`** (default): a `rich`-styled summary (panel with counts: triples added / triples removed) plus the first 20 triple-level changes, then "...and N more" footer if truncated. The non-TTY plain version uses the same content with no styling.
   - **`--format json`**: machine-readable JSON with each Change as an object. Schema version 1.
5. Exit code:
   - 0 if no changes
   - 0 if changes exist but none are `breaking` (Layer 0 changes have severity per the rules below)
   - 10 if any change is `breaking` (this is the "found breaking changes" signal)

When `--layers` includes anything other than `syntactic`, raise `NotImplementedYetError` listing which layers aren't done yet. Layers 1–3 are still planned.

## Internal design

### The algorithm — deliberately simple

1. Precondition check: assert both snapshots have `canonical=True`. If not, raise `DiffError("inputs must be canonicalized first")`.
2. Compute `triples_a = set(a.graph)` and `triples_b = set(b.graph)`.
3. `removed = triples_a - triples_b` (in A, not in B).
4. `added = triples_b - triples_a` (in B, not in A).
5. For each triple in `removed`, build a `Change` with `kind="triple_removed"`.
6. For each triple in `added`, build a `Change` with `kind="triple_added"`.
7. Sort the changes by a deterministic key (see Ordering below).
8. Return the list.

Performance: O(N + M) on triple counts. The two diffs are pure Python set operations on rdflib `Triple` tuples, which are hashable by their term n3 representations. Fast.

### Severity rules for Layer 0

Layer 0 doesn't *understand* triples, so it can't classify them semantically. But we can apply simple rules that hold in any RDF:

| Predicate pattern | Removed triple severity | Added triple severity |
|---|---|---|
| `rdf:type` | `breaking` | `additive` |
| `rdfs:subClassOf`, `rdfs:subPropertyOf` | `breaking` | `additive` |
| `rdfs:domain`, `rdfs:range` | `breaking` | `non_breaking` |
| `owl:deprecated` (added → True) | n/a | `info` |
| `rdfs:label`, `rdfs:comment`, `dcterms:*`, `skos:prefLabel`, `skos:altLabel` | `info` | `info` |
| `owl:imports` | `non_breaking` | `non_breaking` |
| `owl:versionIRI`, `owl:versionInfo` | `info` | `info` |
| Anything else | `non_breaking` | `non_breaking` |

These rules are **defaults** — Layer 1 will override with more accurate per-entity classifications. Layer 0's severity is a coarse fallback.

Implement as a module-level dict mapping predicate IRIs to `(removed_severity, added_severity)` tuples. Predicates not in the table fall through to `("non_breaking", "non_breaking")`.

### Subject extraction

`Change.subject` for a triple change is the triple's subject term:
- If it's a URI ref, use the IRI as a string.
- If it's a blank node, use `None` (post-canonicalization, blank nodes have stable labels but they aren't entity IRIs we want to expose).
- If it's a literal, use `None` (literals shouldn't appear as subjects, but defensive).

### Summary string

A short, human-readable description:
- `triple_removed`: `"Removed: <subject_n3> <predicate_n3> <object_n3>"` truncated to 120 chars
- `triple_added`: `"Added: <subject_n3> <predicate_n3> <object_n3>"` truncated to 120 chars

Use rdflib's `.n3()` term serialization with the snapshot's namespace manager to get prefixed forms (`era:Track` not `<http://data.europa.eu/949/Track>`) for readability.

### Details dictionary

Each Change's `details` dict carries the structured triple data so renderers can reformat:

```python
details = {
    "subject": triple[0].n3(),
    "predicate": triple[1].n3(),
    "object": triple[2].n3(),
    "subject_iri": str(triple[0]) if is_uri(triple[0]) else None,
    "predicate_iri": str(triple[1]) if is_uri(triple[1]) else None,
}
```

### Ordering

Deterministic sort key, applied after change list assembly:

1. By `kind` (`triple_removed` before `triple_added` — removals first makes diffs read like "what's gone, what's new")
2. Then by `subject_iri` (None last)
3. Then by `predicate_iri`
4. Then by full triple n3 representation (final tiebreak)

This means the same input always produces the same output; tests can rely on exact ordering; users skimming output see related changes grouped.

## Edge cases & failure modes

- **Inputs not canonicalized:** raise `DiffError("inputs must be canonicalized first")`. Exit code 4.
- **Inputs are the same snapshot object (a is b):** return empty list, fast path.
- **Empty ontologies (both):** return empty list.
- **One empty, one not:** return all triples of the non-empty side as added (if A empty) or removed (if B empty).
- **Identical canonical forms but different metadata:** still produces zero Layer 0 changes; metadata differences surface in Layer 1.
- **Huge ontologies (>1M triples):** set operations stay fast; the rendering layer truncates output. Don't optimize early.
- **Blank node noise:** post-canonicalization, blank nodes have stable labels, so identical logical content produces identical triples. If we see noisy blank-node "changes," that's a bug in Component 04, not here.
- **Triples whose subject is a `urn:owlcompare:restriction:...` URN:** these are reified anonymous restrictions from Component 04. Treat them like any other URI subject — surface the URN. Layer 1 will translate them back to "restriction on entity X."

## Dependencies to add

None. Pure-Python set operations + rdflib types already in dependencies.

## Acceptance tests

Located in `tests/unit/test_diff_syntactic.py`, with shared diff types tested in `tests/unit/test_diff_common.py`. CLI integration in `tests/unit/test_cli_diff.py`. Integration test in `tests/integration/test_diff_integration.py`.

### Fixtures to add (`tests/fixtures/diff/`)

- `identical_a.ttl` and `identical_b.ttl` — same content, different blank node labels and triple order. Layer 0 result must be empty after canonicalization.
- `added_class_before.ttl` and `added_class_after.ttl` — `after` adds one class with one label and one subClassOf axiom.
- `removed_class_before.ttl` and `removed_class_after.ttl` — `after` removes one class.
- `renamed_label_before.ttl` and `renamed_label_after.ttl` — label changed, entity otherwise unchanged. Should produce one removed-label triple, one added-label triple.
- `widened_range_before.ttl` and `widened_range_after.ttl` — `rdfs:range` of a property broadened.
- `era_evolution_v1.ttl` and `era_evolution_v2.ttl` — small hand-crafted "two versions of an ERA fragment" with: one added class, one removed property, one cardinality change, one label change in French. The flagship realistic test.

### Test list

**`tests/unit/test_diff_common.py`:**
- [ ] `test_change_is_frozen`
- [ ] `test_change_is_hashable`
- [ ] `test_change_default_details_is_empty_dict`
- [ ] `test_diff_options_defaults_include_all_four_layers`
- [ ] `test_diff_result_changes_is_tuple_not_list` — enforces immutability.

**`tests/unit/test_diff_syntactic.py`:**
- [ ] `test_diff_raises_if_inputs_not_canonical` — raise `DiffError`, exit_code 4.
- [ ] `test_diff_identical_canonical_inputs_returns_empty` — same fixture loaded twice → 0 changes.
- [ ] `test_diff_equivalent_inputs_different_serialization_returns_empty` — uses `identical_a.ttl` and `identical_b.ttl`.
- [ ] `test_diff_added_class_produces_added_changes`
- [ ] `test_diff_removed_class_produces_removed_changes`
- [ ] `test_diff_change_count_matches_triple_count_added`
- [ ] `test_diff_change_count_matches_triple_count_removed`
- [ ] `test_diff_all_changes_have_layer_syntactic`
- [ ] `test_diff_removed_change_has_correct_kind_and_severity` — for an `rdfs:label` removed: kind="triple_removed", severity="info".
- [ ] `test_diff_added_change_has_correct_kind_and_severity`
- [ ] `test_diff_rdf_type_removed_is_breaking`
- [ ] `test_diff_rdf_type_added_is_additive`
- [ ] `test_diff_subclass_removed_is_breaking`
- [ ] `test_diff_label_changed_produces_one_removed_one_added_both_info`
- [ ] `test_diff_subject_iri_extracted_for_uri_subject`
- [ ] `test_diff_subject_none_for_blank_node_subject`
- [ ] `test_diff_ordering_is_deterministic` — call diff twice, assert change list is identical.
- [ ] `test_diff_ordering_removed_before_added`
- [ ] `test_diff_summary_uses_prefixed_form_when_namespace_known` — `era:Track`, not the full IRI.
- [ ] `test_diff_details_contains_n3_terms`
- [ ] `test_diff_details_contains_iri_when_uri` — `subject_iri` populated for URI subjects.
- [ ] `test_diff_handles_one_empty_one_populated`
- [ ] `test_diff_handles_both_empty`
- [ ] `test_diff_same_object_fast_path` — `syntactic.diff(s, s)` returns `[]` instantly.

**`tests/unit/test_cli_diff.py`:**
- [ ] `test_cli_diff_help_lists_layers_format_out` — help text mentions all three flags (using the width-robust assertion pattern from Phase 1's CI fix).
- [ ] `test_cli_diff_missing_arguments_exits_2`
- [ ] `test_cli_diff_identical_inputs_exits_0`
- [ ] `test_cli_diff_layers_structural_only_exits_2` — Layer 1 stubbed; `--layers structural` raises NotImplementedYetError.
- [ ] `test_cli_diff_layers_invalid_name_exits_2`
- [ ] `test_cli_diff_format_json_output_is_valid_json` — parse `result.stdout` as JSON; verify a `"changes"` key.
- [ ] `test_cli_diff_format_json_schema_version_field_present` — top-level `"schema_version": 1`.
- [ ] `test_cli_diff_format_text_default_on_tty` — output contains rich panel characters or prefixed forms.
- [ ] `test_cli_diff_added_class_fixture_shows_at_least_one_added_change`
- [ ] `test_cli_diff_writes_to_out_file`
- [ ] `test_cli_diff_breaking_change_exits_10` — fixture with an `rdfs:subClassOf` removed → exit 10.
- [ ] `test_cli_diff_only_info_changes_exits_0` — fixture with only a label changed → exit 0.

**`tests/integration/test_diff_integration.py`:**
- [ ] `test_era_evolution_fixture_produces_expected_change_counts` — the flagship test. Load v1 and v2, canonicalize, diff. Assert exact counts: N classes added, M labels changed, etc. Drives the realism of the whole component.
- [ ] `test_diff_via_python_dash_m_subprocess` — `python -m owlcompare diff era_evolution_v1.ttl era_evolution_v2.ttl` exits with the expected code (10 if breaking, else 0) and produces JSON when `--format json`.

## Out of scope (deliberately)

- Structural diff (Component 06+) — Layer 1, the next component.
- Inferential diff (Layer 2) and impact diff (Layer 3) — v2 features per DD-009.
- Rename detection (Component 11+).
- Markdown/HTML/JUnit output formats — Phase 4.
- Diff orchestrator that aggregates multi-layer results — added in the next component.
- Severity *overrides* via CLI flag — Phase 5 polish.
- Filtering changes by predicate, subject, or namespace — deferred.

## Open questions

- [x] **Q1 (resolved — adopted proposed):** What exit code should we use when only `info`-severity changes exist (e.g., labels updated)?
  **Decision:** Exit 0. Severity `info` is by definition non-breaking and not even semantically meaningful for downstream consumers. The CI-friendly contract is "exit 0 = nothing breaking, exit 10 = breaking found, exit 1+ = error." `info` changes don't break builds. Implemented: only a `breaking`-severity change triggers exit 10.

- [x] **Q2 (resolved — adopted proposed):** Should the text output's 20-change truncation limit be configurable via a CLI flag?
  **Decision:** No, hard-coded for v1 (`_TEXT_CHANGE_LIMIT = 20` in `_render_diff.py`). Truncation pushes users to the full report once that exists (Phase 4). One fewer knob to document. Revisit when we add `--format html`.

- [x] **Q3 (resolved — adopted proposed):** Should `triple_added` and `triple_removed` use `subject_iri` when the subject is a `urn:owlcompare:restriction:...` URN from canonicalization?
  **Decision:** Yes — these are valid IRIs, just synthetic. Surfaced as `subject_iri`. Layer 1 (Component 06+) will translate them back to "restriction on entity X" with a different `kind` and a more informative summary. For Layer 0, the URN is what it is.

All three open questions were resolved by adopting the proposed answers during Component 05 implementation.

## References

- `docs/ARCHITECTURE.md` § Diff Engine, § Public API surfaces
- `docs/DESIGN_DECISIONS.md` § DD-006 (frozen dataclasses), § DD-007 (canonicalization), § DD-008 (severity)
- `docs/GLOSSARY.md` § Change, § Layer, § Severity
