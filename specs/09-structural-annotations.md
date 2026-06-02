# Component 09: Layer 1 Structural Diff — Annotations

## Identity

- **Component number:** 09
- **Name:** Structural diff — annotations (Layer 1, fourth and final slice)
- **Module paths:**
  - `src/owlcompare/diff/structural/annotations.py` — this component's implementation
  - `src/owlcompare/diff/structural/_annotation_index.py` — internal helper: indexed view of annotation triples per entity/property/language
- **Roadmap phase:** Phase 2
- **Depends on components:** 02 (model), 04 (canonicalize), 05 (Layer 0 + Change), 06 (entity diff + orchestrator + SubsumptionRegistry), 07 (hierarchy — for coordination), 08 (restrictions — for coordination)
- **Depended on by (planned):** 10 (severity classifier polish), 14–17 (renderers)

## Purpose

Detect annotation-property changes (labels, comments, deprecations, metadata) between two canonicalized snapshots and consolidate add+remove pairs into single `annotation_changed` Change records when they share the same subject, predicate, and language tag.

After this component, the most common remaining Layer 0 noise — pairs of `rdfs:label` triples representing a label being changed — folds into single human-readable changes like *"Label changed on era:Track (fr): 'Voie' → 'Voie ferrée'"*.

What would break if we removed it: every multilingual label edit, every comment refinement, every deprecation marking would appear as 2+ unexplained Layer 0 triples forever. Ontologies under active editorial maintenance (which is most of them) would produce mostly-Layer-0 diffs that misrepresent the change as "everything was deleted and re-added."

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Snapshot A | `OntologySnapshot` | Loader + Canonicalize | `canonical=True` precondition |
| Snapshot B | `OntologySnapshot` | Loader + Canonicalize | Same |
| Layer 0 changes | `list[Change]` | Component 05 | For subsumption matching |
| Registry | `SubsumptionRegistry` | Components 06 + 07 + 08 (already updated) | Mutated in-place |
| Options | `DiffOptions` | Optional | |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `list[Change]` | list | Orchestrator | All `layer="structural"`; new `kind` values described below |
| Updated registry | (in-place) | Renderers | Remaining annotation triples subsumed |

## Public API

```python
# src/owlcompare/diff/structural/annotations.py

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
    """Compute Layer 1 annotation-level differences.

    Emits Change records of the following kinds:
      - 'annotation_changed'  — value changed for same (subject, predicate, language)
      - 'annotation_added'    — annotation appeared for an existing entity
      - 'annotation_removed'  — annotation removed from an existing entity
      - 'entity_deprecated'   — owl:deprecated true newly asserted on an existing entity
      - 'entity_undeprecated' — owl:deprecated true removed (rare but real)
      - 'ontology_metadata_changed' — annotation change on the owl:Ontology subject itself

    Updates `registry` in-place. Returns the list of new Change records.
    """
```

The orchestrator wires this in: after `restrictions.diff()` it now calls `annotations.diff()` with the shared registry. This is the final Layer 1 slice — after it returns, Phase 2's diff pipeline (modulo the severity classifier) is complete.

## Internal design

### Step 1 — Build per-side annotation indexes

`_annotation_index.py` produces a structured view of every annotation triple in each snapshot, keyed for efficient pairing:

```python
@dataclass(frozen=True, slots=True)
class AnnotationValue:
    """A single annotation triple, normalized for diffing."""
    subject: str               # IRI (entity or ontology)
    predicate: str             # annotation property IRI
    language: str | None       # language tag for literals, None for non-literal values or no-tag literals
    value: str                 # literal lexical form, or IRI string for resource values
    is_iri_value: bool         # True if the object is an IRI, False if a literal


@dataclass(frozen=True, slots=True)
class AnnotationIndex:
    # subject IRI -> predicate IRI -> language -> tuple of AnnotationValues
    # (tuple to keep multi-valued annotations like multiple skos:altLabel@en distinguishable)
    by_subject: dict[str, dict[str, dict[str | None, tuple[AnnotationValue, ...]]]]

    # Convenience: flat list of all annotations on the ontology declaration itself
    ontology_annotations: tuple[AnnotationValue, ...]

    # Convenience: flat list of all annotations across the index (used for subsumption matching)
    all_annotations: tuple[AnnotationValue, ...]


def build(snapshot: OntologySnapshot) -> AnnotationIndex: ...
```

Building it:

1. Define the set of annotation properties to recognize: well-known ones (`rdfs:label`, `rdfs:comment`, `rdfs:seeAlso`, `rdfs:isDefinedBy`, `owl:versionInfo`, `owl:priorVersion`, `owl:deprecated`, `owl:incompatibleWith`, `owl:backwardCompatibleWith`, `dcterms:*`, `dc:*`, `skos:prefLabel`, `skos:altLabel`, `skos:hiddenLabel`, `skos:definition`, `skos:note`, `skos:scopeNote`, `skos:example`, `skos:editorialNote`, `skos:changeNote`, `skos:historyNote`, `prov:wasGeneratedBy`, `foaf:*`) PLUS any property explicitly declared as `rdf:type owl:AnnotationProperty` in the snapshot.
2. Scan the canonical graph for triples whose predicate matches the set.
3. For each, capture subject, predicate, language tag (if literal with `@lang`), value, and value type. Build a tuple of `AnnotationValue`s per `(subject, predicate, language)`.
4. Separately collect annotations where the subject is the ontology IRI (from `snapshot.metadata.iri`) into `ontology_annotations`.

Skip annotation triples whose subject is a `urn:owlcompare:restriction:*` URN (those are part of restriction expressions, not user-facing entity annotations) and whose subject is a blank node.

### Step 2 — Pair annotations across A and B

For each subject IRI present in either index:

1. Skip if Component 06 already emitted `class_added`/`class_removed`/etc. for this entity — its annotations are subsumed under that change. **Read the registry.** This is the key coordination point.
2. Skip if the subject is a `urn:owlcompare:restriction:*` URN (handled by Component 08).
3. For each annotation property the subject has in either A or B:
4.   For each language tag (or `None`):
5.     `values_a = a_index.by_subject[s][p][lang]` (default empty tuple)
6.     `values_b = b_index.by_subject[s][p][lang]` (default empty tuple)
7.     Match values:
        - **Both non-empty, distinct sets** (e.g., `("Voie",)` vs. `("Voie ferrée",)`): if both have exactly one value → emit `annotation_changed` with that pair. If both have multiple, emit `annotation_changed` if the *sets* differ, with `before` and `after` lists. The multi-value case is rare but well-handled.
        - **Only A**: `annotation_removed` for each value in A.
        - **Only B**: `annotation_added` for each value in B.
        - **Equal sets**: no change.

### Step 3 — Special cases

**`owl:deprecated true`**:

- If the entity didn't have `owl:deprecated true` in A but does in B → emit `entity_deprecated` (single change, special kind).
- If the entity had `owl:deprecated true` in A but not in B → emit `entity_undeprecated`.
- Don't emit a generic `annotation_added/removed` for these — they have their own semantics.

**Ontology-level annotations** (subject is `snapshot.metadata.iri`):

- Diff separately, emit `ontology_metadata_changed` (one per changed annotation property, with full before/after in details).
- Severity is generally `info` (version bumps, contributor changes), but `owl:versionIRI` changes (when the version IRI itself changes) are `info` too — the version difference is metadata, not a semantic break.

### Step 4 — Subsumption

For each emitted Layer 1 annotation change, find the matching Layer 0 changes and register them:

- `annotation_changed (subject=s, predicate=p, language=lang)`: subsumes the corresponding `triple_removed` (for the old value) and `triple_added` (for the new value) in Layer 0.
- `annotation_added`: subsumes the matching `triple_added`.
- `annotation_removed`: subsumes the matching `triple_removed`.
- `entity_deprecated`: subsumes the `owl:deprecated true triple_added`.
- `entity_undeprecated`: subsumes the `owl:deprecated true triple_removed`.
- `ontology_metadata_changed`: subsumes both the removed and added triples for that ontology-level annotation.

### Severity rules

| Kind | Severity |
|------|----------|
| `annotation_changed` (label, comment, prefLabel, altLabel, definition, note) | `info` |
| `annotation_added` / `annotation_removed` (label-like) | `info` |
| `entity_deprecated` | `non_breaking` — flags consumers that something is going away, but doesn't break anything yet |
| `entity_undeprecated` | `info` |
| `ontology_metadata_changed` | `info` |
| `annotation_changed` for an unknown annotation property | `info` |

Annotations are intrinsically `info` by definition — they're metadata, not semantics. The `entity_deprecated` case is the only one with a stronger severity, and even that's `non_breaking` (deprecation is a signal, not an invalidation).

### Subject and summary

`Change.subject` is the entity IRI (or ontology IRI for `ontology_metadata_changed`).

`Change.summary` patterns (with prefixed IRIs when known):

- `"Label changed on era:Track (fr): 'Voie' → 'Voie ferrée'"` (annotation_changed, with language)
- `"Label changed on era:Track: 'Track' → 'Railway Track'"` (annotation_changed, no language)
- `"Comment changed on era:Track"` (annotation_changed for `rdfs:comment` — value omitted from summary for length; full text in details)
- `"Label added on era:Track (de): 'Gleis'"`
- `"Comment removed from era:Track"`
- `"era:Track marked deprecated"`
- `"era:Track unmarked deprecated"`
- `"Ontology metadata: owl:versionInfo '1.0.0' → '2.0.0'"`
- `"Ontology metadata: dcterms:modified '2024-01-15' → '2026-05-30'"`

The annotation property name uses the short prefixed form (`label`, `comment`, `prefLabel`, etc.) when the predicate is `rdfs:label`, `rdfs:comment`, or in a recognized namespace. Otherwise the full predicate IRI.

Comment-style annotations (`rdfs:comment`, `skos:definition`, etc.) omit the value text from the summary because it's typically too long. Full before/after available in `details`.

### Details dictionary

For `annotation_changed`:

```python
details = {
    "change_id": "structural:annotation_changed:...",
    "entity_iri": "...",
    "predicate_iri": "...",          # the annotation property
    "predicate_short": "label",       # short form for display
    "language": "fr",                 # or None
    "before": {"value": "Voie", "is_iri_value": False},
    "after": {"value": "Voie ferrée", "is_iri_value": False},
    "subsumes": [<layer0 change_ids>],
}
```

For `annotation_added` / `annotation_removed`:

```python
details = {
    "change_id": "...",
    "entity_iri": "...",
    "predicate_iri": "...",
    "predicate_short": "...",
    "language": "..." or None,
    "value": "...",
    "is_iri_value": bool,
    "subsumes": [<layer0 change_ids>],
}
```

For `entity_deprecated` / `entity_undeprecated`:

```python
details = {
    "change_id": "...",
    "entity_iri": "...",
    "subsumes": [<layer0 change_id>],
}
```

For `ontology_metadata_changed`:

```python
details = {
    "change_id": "...",
    "ontology_iri": "...",
    "predicate_iri": "...",
    "predicate_short": "...",
    "before": {"value": "...", ...} or None,
    "after": {"value": "...", ...} or None,
    "subsumes": [<layer0 change_ids>],
}
```

### Ordering

Within the structural section, sort by:

1. `kind` (groups `annotation_changed`, then `annotation_added`/`removed`, then `entity_deprecated`/`undeprecated`, then `ontology_metadata_changed`)
2. `subject` (entity or ontology IRI)
3. `predicate_iri`
4. `language` (None first, then alphabetical)

## Edge cases & failure modes

- **Entity exists only in one side:** Component 06 emits `class_added`/`removed`; this component **skips** annotation processing for that entity (registry-driven).
- **Restriction URN as subject:** skip — Component 08's territory.
- **Blank node as subject:** skip — anonymous, not meaningful for annotation tracking.
- **Same value, different language tag** (e.g., `rdfs:label "Track"` added with `@en`, removed without language): treat as separate annotations (different language buckets). The diff sees one `annotation_added (lang=en)` and one `annotation_removed (lang=None)`.
- **Multi-value annotations** (e.g., 3 `skos:altLabel`s in A, 2 in B, same language): match by set difference. If A has `{X, Y, Z}` and B has `{X, Y}`, emit one `annotation_removed` for `Z`. No `annotation_changed` for sets — only for single-value-each case.
- **Datatype literals** (`rdfs:label "Track"^^xsd:string`): treat as values without language tag. Don't try to be smart about datatype-vs-plain-literal distinctions.
- **IRI-valued annotations** (`rdfs:seeAlso <http://example.org/something>`): record `is_iri_value=True`, treat value as the IRI string. Pair normally.
- **Annotation property declared in the ontology but not used:** no triples, no entries in index, no changes emitted.
- **Punning** (entity is both class and individual): annotations attach to the IRI, not the kind. Component 09 sees one IRI with annotations. If only the class kind was removed (Component 06), the annotations stay attached and aren't subsumed — they're still on the still-existing individual. Tested.
- **Ontology IRI changed** (very rare): treat as a special case — if the ontology IRI itself differs between A and B, fall back to ontology-level annotation diff on whichever ontology IRI each side has, but flag that the IRI changed via a separate `ontology_iri_changed` change. **Out of scope for v1**; document in backlog.

## Dependencies to add

None. All in stdlib + rdflib + existing model.

## Acceptance tests

Located in `tests/unit/test_annotation_index.py`, `tests/unit/test_diff_structural_annotations.py`, extensions to `tests/unit/test_diff_orchestrator.py`, and extensions to `tests/integration/test_diff_integration.py`.

### Fixtures to add (`tests/fixtures/diff/annotations/`)

Each fixture pair: `_before.ttl` / `_after.ttl`.

- `label_changed_same_lang` — `rdfs:label "Track"@en → "Railway Track"@en`. Same language, value change.
- `label_changed_different_lang` — `rdfs:label "Voie"@fr → "Voie ferrée"@fr`. Same scenario, different language.
- `label_added` — `rdfs:label "Gleis"@de` added; no German label existed before.
- `label_removed` — `rdfs:label "Track"@en` removed; English label gone in v2.
- `comment_changed` — `rdfs:comment` value changed; summary should omit value.
- `multivalue_altLabel_one_removed` — `skos:altLabel` had 3 values in A, has 2 in B; one removed.
- `deprecated_added` — `owl:deprecated true` newly asserted in v2 on existing entity.
- `deprecated_removed` — `owl:deprecated true` removed in v2 (entity un-deprecated).
- `ontology_versioninfo_changed` — `owl:versionInfo "1.0.0" → "2.0.0"` on the `owl:Ontology` subject.
- `ontology_modified_changed` — `dcterms:modified` date changed.
- `annotation_on_class_added_does_not_emit_separate_change` — fixture where a new class is added with a label; Component 06 should subsume, Component 09 should NOT emit.
- `annotation_on_restriction_urn_skipped` — fixture where a restriction URN somehow has an annotation; Component 09 must skip.
- `iri_valued_annotation` — `rdfs:seeAlso <http://example.org/related>` value changed.
- `era_annotations_v1.ttl` / `era_annotations_v2.ttl` — flagship: 3 entities with mixed annotation changes (label in French changed, comment changed, one entity deprecated, ontology metadata bumped).

### Test list

**`tests/unit/test_annotation_index.py`:**
- [ ] `test_build_captures_rdfs_label`
- [ ] `test_build_captures_rdfs_comment`
- [ ] `test_build_captures_multiple_languages_separately`
- [ ] `test_build_groups_multivalue_annotations`
- [ ] `test_build_captures_owl_deprecated`
- [ ] `test_build_captures_ontology_annotations_separately`
- [ ] `test_build_skips_restriction_urn_subjects`
- [ ] `test_build_skips_blank_node_subjects`
- [ ] `test_build_recognizes_user_declared_annotation_property`
- [ ] `test_build_captures_iri_valued_annotation`
- [ ] `test_build_captures_no_language_literal`

**`tests/unit/test_diff_structural_annotations.py`:**
- [ ] `test_diff_requires_canonical_inputs`
- [ ] `test_diff_identical_inputs_returns_empty`
- [ ] `test_label_changed_same_lang_emits_annotation_changed`
- [ ] `test_label_changed_different_lang_emits_annotation_changed`
- [ ] `test_label_added_emits_annotation_added`
- [ ] `test_label_removed_emits_annotation_removed`
- [ ] `test_comment_changed_emits_annotation_changed_with_no_values_in_summary` — summary text omits value, but `details.before` and `details.after` carry it.
- [ ] `test_multivalue_one_removed_emits_annotation_removed`
- [ ] `test_deprecated_added_emits_entity_deprecated`
- [ ] `test_deprecated_added_does_not_emit_annotation_added`
- [ ] `test_deprecated_removed_emits_entity_undeprecated`
- [ ] `test_ontology_versioninfo_change_emits_ontology_metadata_changed`
- [ ] `test_ontology_modified_change_emits_ontology_metadata_changed`
- [ ] `test_iri_valued_annotation_change_records_is_iri_value_true`
- [ ] `test_annotation_changed_severity_info`
- [ ] `test_entity_deprecated_severity_non_breaking`
- [ ] `test_entity_undeprecated_severity_info`
- [ ] `test_ontology_metadata_changed_severity_info`
- [ ] `test_diff_skips_entities_with_class_added_in_registry` — Component 06 coordination.
- [ ] `test_diff_skips_entities_with_class_removed_in_registry`
- [ ] `test_diff_skips_restriction_urn_subjects`
- [ ] `test_diff_subsumes_corresponding_layer0_triples`
- [ ] `test_change_id_present_in_details`
- [ ] `test_summary_uses_prefixed_iris_when_known`
- [ ] `test_summary_label_includes_language_in_parens`
- [ ] `test_summary_label_no_language_omits_paren`
- [ ] `test_summary_comment_omits_value_text`
- [ ] `test_summary_arrow_notation_for_changed`
- [ ] `test_ordering_groups_kind_then_subject_then_predicate_then_language`

**`tests/unit/test_diff_orchestrator.py` (extensions):**
- [ ] `test_orchestrator_runs_annotations_after_restrictions`
- [ ] `test_orchestrator_layer1_changes_include_annotations`
- [ ] `test_orchestrator_layer1_pipeline_order_entities_hierarchy_restrictions_annotations`

**`tests/integration/test_diff_integration.py` (extensions):**
- [ ] `test_era_evolution_fixture_after_component_09` — assert exact behavior: the two French label triples now fold into one `annotation_changed`. The two `owl:versionInfo` triples fold into one `ontology_metadata_changed`. Layer 0 unexplained should drop to 0 or near it.
- [ ] `test_era_evolution_emits_label_changed_for_voie_voie_ferree`
- [ ] `test_era_evolution_emits_ontology_metadata_changed_for_versioninfo`
- [ ] `test_era_annotations_fixture_emits_expected_changes` — exact count match.

## Out of scope (deliberately)

- Annotations-on-annotations (OWL 2 annotated axioms).
- `ontology_iri_changed` detection (backlog).
- Detecting whether a label translation is more or less idiomatic — out of scope by design.
- Severity refinement based on annotation property semantics (handled in Component 10).
- Renames disguised as label changes — Components 11+.

## Open questions

- [x] **Q1 (resolved — adopted proposed):** Comment-style annotations (`rdfs:comment`, `skos:definition`, `skos:note`) — should the summary include the value or omit it? Long comments break table layout; short comments would be fine.
  **Decision:** Always omit the value from the summary for these. The details dict carries the full text. Implemented as the `_COMMENT_LIKE` set in `annotations.py`; `_changed_annotation` / `_single_annotation` skip the value phrase when the predicate is in it, so *"Comment changed on era:Track"* carries no inline text and `details.before`/`after` hold the full strings.

- [x] **Q2 (resolved — adopted proposed):** When pairing multi-value annotations across A and B for the *same* language, can we ever emit `annotation_changed` for a clear "renamed" altLabel, or do we always emit `_added` + `_removed`?
  **Decision:** Always `_added` + `_removed` for multi-value sets. `annotation_changed` is emitted only when each side has *exactly one* value (`_diff_bucket` checks `len(set_a) == 1 and len(set_b) == 1`); otherwise the set difference drives per-value `annotation_added` / `annotation_removed`. Rename-style pairing is deferred to Phase 3.

- [x] **Q3 (resolved — adopted proposed):** For ontology-level annotations, should the change be `ontology_metadata_changed` (one kind) regardless of which annotation property changed, or per-property kinds (e.g., `version_info_changed`, `dcterms_modified_changed`)?
  **Decision:** One kind, `ontology_metadata_changed`, with the property in `details.predicate_iri` / `details.predicate_short`. Implemented in `_diff_ontology` / `_ontology_change`.

All three open questions were resolved by adopting the proposed answers during implementation.

## Resolved design notes (added during implementation)

- **Entity coordination is membership-driven, not registry-keyed by kind.** `_defer_entity` skips an entity only when its IRI is wholly absent from one side's entity index (`_wholly_changed` over `entities.all_iris()`), then registers that entity's annotation triples under Component 06's `rdf:type` explainer (found via the shared registry, mirroring Component 08's `_defer_*`). This deliberately keeps the punning case correct: an IRI that loses only one of its kinds (e.g. the class is removed but the individual remains) is present on both sides, so it is *not* deferred and its annotations are still diffed — matching the spec's punning edge case.
- **`owl:deprecated` is detected from the index, not `Entity.is_deprecated`.** `_is_deprecated` reads the `owl:deprecated` bucket for a `"true"` value, so the special-case lives entirely in the annotation layer and the generic predicate loop explicitly skips `owl:deprecated`.
- **Subsumption matching reconstructs the literal `n3` form.** `_match_value` rebuilds the object term (`URIRef`, language-tagged `Literal`, or plain `Literal`) and renders it with the side's namespace manager to match Component 05's `details.object`; `owl:deprecated` matches object-agnostically by `(subject, predicate, kind)` since there is only one such triple per subject.
- **Module-name vs. `from __future__ import annotations` footgun.** The submodule is named `annotations.py`, which collides with the module-global `annotations` bound by `from __future__ import annotations`. The package `__init__` therefore omits that future import (it has no annotations of its own), and `orchestrator.py` imports the slice aliased as `annotations_slice` so both the import machinery and mypy resolve the submodule rather than the `__future__._Feature`.

## References

- `docs/ARCHITECTURE.md` § Diff Engine (Layer 1)
- `docs/DESIGN_DECISIONS.md` § DD-006 (frozen), § DD-008 (severity)
- `docs/GLOSSARY.md` § Change, § Layer
- Components 06, 07, 08 specs for the orchestrator and registry patterns
