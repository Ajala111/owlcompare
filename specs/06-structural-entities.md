# Component 06: Layer 1 Structural Diff — Entity-Level Changes

## Identity

- **Component number:** 06
- **Name:** Structural diff — entity-level (Layer 1, first slice)
- **Module paths:**
  - `src/owlcompare/diff/structural/__init__.py` — Layer 1 package root
  - `src/owlcompare/diff/structural/entities.py` — this component's implementation
  - `src/owlcompare/diff/_subsumption.py` — shared subsumption tracking (used by all Layer 1 slices)
  - `src/owlcompare/diff/orchestrator.py` — top-level diff orchestrator that runs multiple layers
- **Roadmap phase:** Phase 2 (second component)
- **Depends on components:** 02 (snapshot/model), 04 (canonicalize), 05 (Layer 0 + Change/DiffResult)
- **Depended on by (planned):** 07 (hierarchy), 08 (restrictions), 09 (annotations), 10 (severity), 14–17 (report renderers)

## Purpose

Detect entity-level changes between two canonicalized snapshots: classes/properties/individuals/datatypes added, removed, or changed in kind. Produce `Change` records at the structural layer that explain what happened at a meaningful level — "Class added" rather than "triple added" — and link them to the Layer 0 triples they subsume.

This is the first piece of semantic intelligence in the pipeline. After this component, a user diffing two ontologies sees `+ Class added: era:Platform` once, instead of seeing the three or four underlying triples scattered across the table.

What would break if we removed it: the diff output would remain at the raw-triple level forever. Components 07–09 cannot meaningfully build on each other without entity-level changes as a foundation, because hierarchy and annotation changes depend on knowing whether the entity itself still exists.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Snapshot A | `OntologySnapshot` | Loader + Canonicalize | `canonical=True` precondition |
| Snapshot B | `OntologySnapshot` | Loader + Canonicalize | `canonical=True` precondition |
| Layer 0 changes | `list[Change]` | Component 05's output | Used for subsumption tracking |
| Options | `DiffOptions` | Optional | |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `list[Change]` | list | Diff orchestrator | All carry `layer="structural"`; subsumption recorded in `details` |
| Updated subsumption registry | (internal, threaded via orchestrator) | Renderers / other Layer 1 slices | See subsumption section |

## Public API

### Subsumption (shared across Layer 1 slices)

```python
# src/owlcompare/diff/_subsumption.py

from dataclasses import dataclass, field
from .._common import Change


@dataclass
class SubsumptionRegistry:
    """Tracks which Layer 0 changes are explained by which Layer 1+ changes.

    Mutable on purpose — built incrementally across Layer 1 components.
    The orchestrator passes one registry through the layer pipeline.
    """
    # Map from a Layer 0 change's identity to the list of higher-layer change IDs that explain it.
    explained_by: dict[str, list[str]] = field(default_factory=dict)

    def register(self, higher_change_id: str, layer0_changes: list[Change]) -> None:
        """Mark each given Layer 0 change as subsumed by higher_change_id."""

    def is_explained(self, layer0_change_id: str) -> bool: ...

    def explainers(self, layer0_change_id: str) -> tuple[str, ...]: ...

    @staticmethod
    def change_id(change: Change) -> str:
        """Stable identity for a Change record, used as the registry key.
        Format: '<layer>:<kind>:<sha1 of summary + sorted details>'."""
```

Every `Change` gets a stable id via `SubsumptionRegistry.change_id(change)`. The registry records that, say, the class-added change explains both the `rdf:type owl:Class` triple-added and the `rdfs:label` triple-added Layer 0 changes that came along with it.

The `id` itself is added as `Change.details["change_id"]` so renderers can do reverse lookups.

### Entity diff

```python
# src/owlcompare/diff/structural/entities.py

from owlcompare.model import OntologySnapshot
from .._common import Change, DiffOptions
from .._subsumption import SubsumptionRegistry


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    layer0_changes: list[Change],
    registry: SubsumptionRegistry,
    options: DiffOptions | None = None,
) -> list[Change]:
    """Compute Layer 1 entity-level differences.

    Updates `registry` in-place to mark Layer 0 changes that are now explained
    by the structural changes returned here.

    Returns:
        A list of Change records with layer='structural'. Kinds include:
        'class_added', 'class_removed', 'object_property_added',
        'object_property_removed', 'data_property_added', 'data_property_removed',
        'annotation_property_added', 'annotation_property_removed',
        'individual_added', 'individual_removed', 'datatype_added',
        'datatype_removed', 'entity_kind_changed' (punning resolution / promotion).
    """
```

### Orchestrator

```python
# src/owlcompare/diff/orchestrator.py

from owlcompare.model import OntologySnapshot
from ._common import Change, DiffOptions, DiffResult


def run(
    a: OntologySnapshot,
    b: OntologySnapshot,
    options: DiffOptions | None = None,
) -> DiffResult:
    """Run the diff pipeline end-to-end across all enabled layers.

    1. Canonicalize both inputs if not already canonical.
    2. Run Layer 0 (syntactic). Always.
    3. For each requested Layer 1 slice (currently only entities), run with shared
       SubsumptionRegistry. Append results.
    4. Layer 2/3 stubs return empty for now.
    5. Build DiffResult with all changes, the registry, and metadata.
    """
```

The orchestrator handles canonicalization automatically — callers can pass non-canonical snapshots and the orchestrator does the right thing. The CLI moves to using the orchestrator instead of calling `syntactic.diff` directly.

## CLI integration

The `diff` subcommand gains a `--layers` default of `"syntactic,structural"` (previously only `"syntactic"`). The structural slices added so far register themselves; others remain stubbed.

Add a flag `--show-syntactic` (boolean, default False) controlling text-format output: by default, Layer 0 changes that are *explained by* a Layer 1 change are hidden. With `--show-syntactic`, all Layer 0 changes appear regardless of subsumption.

JSON output **always** includes both layers (it's machine-readable; consumers filter as they wish).

Refine the rich-rendered table to group changes by layer with a small subheading:

```
Layer 1 — Structural (4 changes)
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Severity   ┃ Change                                              ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ additive   │ Class added: era:Platform "Platform"@en             │
│ breaking   │ Object property removed: era:locatedOn "located on" │
│ ...                                                               │

Layer 0 — Syntactic (4 unexplained)        [use --show-syntactic for all]
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ...      ┃ ...                                               ┃
```

The "unexplained" count means Layer 0 changes that no Layer 1 change subsumed. After Component 06 alone, the restriction-related triples remain unexplained (Component 08's job); after Component 09 the count should drop close to zero for typical ontologies.

## Internal design

### Algorithm

1. Get the entity indexes: `entities_a = a.entities`, `entities_b = b.entities`.
2. For each `EntityKind` (`class`, `object_property`, `data_property`, `annotation_property`, `individual`, `datatype`):
   - `iris_a = set(entities_a.<kind_collection>.keys())`
   - `iris_b = set(entities_b.<kind_collection>.keys())`
   - `removed_iris = iris_a - iris_b`
   - `added_iris = iris_b - iris_a`
   - For each removed IRI: emit a `Change(kind=f"{kind}_removed", ...)`.
   - For each added IRI: emit a `Change(kind=f"{kind}_added", ...)`.
3. **Kind-change detection** (after addition/removal): for any IRI that appears in `removed_iris` for one kind AND `added_iris` for another kind, emit a single `entity_kind_changed` change instead of two separate add+remove changes. Skip both the add and remove for that IRI in their respective kinds. (Note: this excludes punning, which is the same IRI under multiple kinds in both A and B — we already handle that in the model.)
4. Compute subsumption: for each emitted Layer 1 change, find the Layer 0 changes whose `details.subject_iri` matches the entity IRI AND whose predicate is one of:
   - `rdf:type` (the type declaration)
   - `rdfs:label`, `rdfs:comment` (initial annotations on the entity)
   - `owl:deprecated` (if the entity was added with deprecation)
   - `rdfs:isDefinedBy`, `dcterms:*` annotations directly on the entity
   Register these Layer 0 changes as explained.

### Severity

| Kind | Severity |
|------|----------|
| `class_added`, `object_property_added`, `data_property_added`, `annotation_property_added`, `individual_added`, `datatype_added` | `additive` |
| `class_removed`, `object_property_removed`, `data_property_removed` | `breaking` |
| `annotation_property_removed` | `non_breaking` (annotations are not core semantics) |
| `individual_removed` | `non_breaking` (data, not schema) |
| `datatype_removed` | `breaking` |
| `entity_kind_changed` | `breaking` (changing a class to an individual is a major semantic break) |

### Subject and summary

`Change.subject` is always the entity IRI (full URI string).

`Change.summary` patterns:
- `"Class added: era:Platform"` (with prefixed form when known)
- `"Class added: era:Platform \"Platform\"@en"` if a label exists in the new ontology
- `"Object property removed: era:locatedOn \"located on\"@en"` (label from old ontology, if present)
- `"Entity kind changed: era:Foo (class → individual)"`

Pick the most prominent English label first; fall back to the first label in any language; omit label if none.

### Details dictionary

```python
details = {
    "change_id": "structural:class_added:abc123...",
    "entity_iri": iri,
    "entity_kind": "class",
    "label": "Platform" or None,
    "language": "en" or None,
    "subsumes": ["syntactic:triple_added:xyz...", ...],  # the Layer 0 change ids
}
```

For `entity_kind_changed`:

```python
details = {
    "change_id": "...",
    "entity_iri": iri,
    "from_kind": "class",
    "to_kind": "individual",
    "subsumes": [...],
}
```

### Ordering

Final structural changes are sorted by:

1. `kind` (groups all "class_added" together, then "object_property_added", etc.)
2. `subject` (entity IRI)

Layer 0 ordering is unchanged from Component 05.

## Edge cases & failure modes

- **Empty ontology on one side:** all entities of the populated side are added (or removed). No errors.
- **Punning** (same IRI as both class AND individual in both A and B): each kind is tracked independently. If both kinds drop the IRI, that's two separate `_removed` changes, not one.
- **Punning resolution** (same IRI as class in A only, as individual in B only): treat as `entity_kind_changed` (`from_kind="class"`, `to_kind="individual"`).
- **Multiple punning kinds changing simultaneously** (IRI in A as class+individual, in B only as class): emits one `individual_removed`, no `class_removed`. Not an `entity_kind_changed` because the IRI didn't "move" — it lost one of its kinds. Behavior is correct as long as we don't try to over-interpret.
- **Synthetic IRIs** (`urn:owlcompare:restriction:*` etc.): treated as regular IRIs. They appear in the entity index only if the canonicalization reified them and they have type declarations in the canonical graph. In practice, restrictions are not in the entity index because they're not declared as `owl:Class` etc. — they're declared as `owl:Restriction`, which we don't index. **No Layer 1 changes get emitted for synthetic IRIs.** Add a unit test.
- **Datatype entities:** indexed (`rdfs:Datatype` declarations) and diffed like any other kind.
- **Inputs identical post-canonicalization:** empty result list.
- **Entity declared twice with same kind in one snapshot:** the model's `EntityIndex` dedupes by IRI, so this is a non-issue at the diff layer.
- **Subsumption with no matching Layer 0 change** (rare, defensive): emit the Layer 1 change anyway. `subsumes` list is empty. Log at DEBUG.

## Dependencies to add

None. Pure-Python set operations on existing model types.

## Acceptance tests

Located in `tests/unit/test_diff_structural_entities.py`, `tests/unit/test_subsumption.py`, `tests/unit/test_diff_orchestrator.py`, `tests/unit/test_cli_diff.py` (extensions), and `tests/integration/test_diff_integration.py` (extensions).

### Fixtures to add (`tests/fixtures/diff/`)

- `class_added_before.ttl` / `class_added_after.ttl` — exactly one class added, with one label.
- `class_removed_before.ttl` / `class_removed_after.ttl` — exactly one class removed.
- `property_added_before.ttl` / `property_added_after.ttl` — one object property and one data property added.
- `kind_changed_before.ttl` / `kind_changed_after.ttl` — an IRI changes from `owl:Class` to `owl:NamedIndividual` between versions.
- `punning_resolution_before.ttl` / `punning_resolution_after.ttl` — IRI is punned in A (both class and individual); only class in B. Tests the "lost one kind" edge case.
- `multiple_kinds_added_before.ttl` / `multiple_kinds_added_after.ttl` — classes AND object properties AND individuals all added simultaneously.

### Test list

**`tests/unit/test_subsumption.py`:**
- [ ] `test_change_id_is_deterministic` — same change content produces the same id across runs.
- [ ] `test_change_id_includes_layer_and_kind`
- [ ] `test_register_marks_layer0_changes_explained`
- [ ] `test_is_explained_false_for_unregistered`
- [ ] `test_explainers_returns_all_higher_layer_ids`

**`tests/unit/test_diff_structural_entities.py`:**
- [ ] `test_diff_requires_canonical_inputs` — `DiffError` if not canonical.
- [ ] `test_diff_identical_inputs_returns_empty`
- [ ] `test_diff_class_added_emits_class_added_change`
- [ ] `test_diff_class_added_change_severity_is_additive`
- [ ] `test_diff_class_removed_change_severity_is_breaking`
- [ ] `test_diff_class_added_subsumes_rdf_type_triple_added` — verify subsumption registry updated.
- [ ] `test_diff_class_added_subsumes_rdfs_label_triple_added`
- [ ] `test_diff_object_property_added_emits_correct_kind`
- [ ] `test_diff_data_property_added_emits_correct_kind`
- [ ] `test_diff_individual_added_severity_is_additive`
- [ ] `test_diff_individual_removed_severity_is_non_breaking`
- [ ] `test_diff_datatype_added_emits_correct_kind`
- [ ] `test_diff_summary_includes_english_label_when_available`
- [ ] `test_diff_summary_falls_back_to_any_label_when_no_english`
- [ ] `test_diff_summary_omits_label_when_none`
- [ ] `test_diff_uses_prefixed_iri_when_namespace_known`
- [ ] `test_diff_kind_changed_emits_single_entity_kind_changed`
- [ ] `test_diff_kind_changed_severity_is_breaking`
- [ ] `test_diff_kind_changed_does_not_emit_add_and_remove` — the IRI must not appear in both added and removed lists.
- [ ] `test_diff_punning_resolution_emits_individual_removed_only` — IRI was class+individual in A, only class in B → exactly one `individual_removed`, no `entity_kind_changed`.
- [ ] `test_diff_skips_synthetic_restriction_iris` — `urn:owlcompare:restriction:*` IRIs are never in the entity index, so they produce no Layer 1 changes.
- [ ] `test_diff_changes_ordered_by_kind_then_subject`
- [ ] `test_diff_change_id_present_in_details`
- [ ] `test_diff_subsumes_field_populated_when_layer0_matched`
- [ ] `test_diff_subsumes_empty_when_no_matching_layer0` — defensive case.

**`tests/unit/test_diff_orchestrator.py`:**
- [ ] `test_orchestrator_canonicalizes_non_canonical_inputs`
- [ ] `test_orchestrator_passes_canonical_inputs_through`
- [ ] `test_orchestrator_runs_layer0_always`
- [ ] `test_orchestrator_runs_layer1_entities_by_default`
- [ ] `test_orchestrator_returns_diffresult_with_combined_changes`
- [ ] `test_orchestrator_diffresult_metadata_includes_layer_counts`
- [ ] `test_orchestrator_subsumption_registry_attached_to_metadata`
- [ ] `test_orchestrator_with_only_syntactic_layer_skips_structural`
- [ ] `test_orchestrator_with_only_structural_layer_still_runs_syntactic` — Layer 1 depends on Layer 0; explicit skip-syntactic is an error.

**`tests/unit/test_cli_diff.py` (extensions):**
- [ ] `test_cli_diff_default_layers_now_include_structural`
- [ ] `test_cli_diff_text_output_groups_by_layer`
- [ ] `test_cli_diff_text_output_hides_subsumed_layer0_by_default`
- [ ] `test_cli_diff_show_syntactic_flag_reveals_all_layer0`
- [ ] `test_cli_diff_text_output_shows_unexplained_count` — "(N unexplained)" appears in the Layer 0 heading when Layer 1 is enabled.
- [ ] `test_cli_diff_json_includes_subsumes_in_details`
- [ ] `test_cli_diff_json_includes_change_id_in_details`

**`tests/integration/test_diff_integration.py` (extensions):**
- [ ] `test_era_evolution_layer1_emits_class_added_for_platform`
- [ ] `test_era_evolution_layer1_emits_object_property_removed_for_locatedon`
- [ ] `test_era_evolution_layer1_subsumes_associated_layer0_changes`
- [ ] `test_era_evolution_total_change_count_reduces_with_subsumption` — assert that visible-by-default change count < total change count.

## Out of scope (deliberately, for this slice)

- Hierarchy changes (`rdfs:subClassOf`, `rdfs:subPropertyOf`) — Component 07.
- Restriction changes (cardinality, value restrictions, domain/range) — Component 08.
- Annotation changes (labels, comments, metadata) as standalone changes when the entity itself didn't change — Component 09.
- Rename detection — Components 11+.
- Suggesting fixes ("did you mean to rename instead of remove?") — Phase 5.
- Severity refinement / overrides — Component 10 (severity classifier).

## Open questions

- [x] **Q1 (resolved — adopted proposed):** Should `entity_kind_changed` be emitted only for "kind A → kind B" where the original kind is no longer present in B (a true "move"), or also for "added a new kind alongside the existing one" (becomes punned)?
  **Decision:** Only for true moves (the original kind is gone). Adding a new kind alongside an existing one is *punning becoming established* — surfaced as an `_added` of the new kind, with no removal. Implemented in `_resolve_kind_changes`: an IRI is a kind change only when it left *exactly one* kind and joined *exactly one* other kind.

- [x] **Q2 (resolved — adopted proposed):** For the label preference in summaries, what's the language priority order?
  **Decision:** `en` first, then no-language-tag (the default), then alphabetical by language tag. Implemented in `_label_rank`.

- [x] **Q3 (resolved — adopted proposed):** When the orchestrator is given non-canonical snapshots, should it canonicalize them silently or warn?
  **Decision:** Canonicalize silently, logging at INFO that it was auto-applied (`orchestrator._ensure_canonical`). Canonical inputs pass through untouched (same object).

All three open questions were resolved by adopting the proposed answers during Component 06 implementation.

## References

- `docs/ARCHITECTURE.md` § Diff Engine (Layer 1)
- `docs/DESIGN_DECISIONS.md` § DD-008 (severity)
- `docs/GLOSSARY.md` § Change, § Layer, § Severity
- Component 05 spec for the `Change` contract this consumes.
