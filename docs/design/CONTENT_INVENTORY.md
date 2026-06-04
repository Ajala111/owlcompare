# Content Inventory

Every data point the HTML report *could* render, drawn from
`docs/schema/diff-result.schema.json` (schema v1) and the two reference
renderers. Each field is classified into one of three tiers:

- **Tier 1 — Always visible.** The headline; in the DOM before any scroll.
- **Tier 2 — One scroll or one click away.** Per-change detail, expandable.
- **Tier 3 — Behind navigation, a filter, or a "show technical" toggle.**

The rule this table enforces: *every field in the schema appears here exactly
once.* If Component 17 finds a field with no row, the inventory is wrong, not the
schema.

## Top-level

| Field | Tier | Rationale |
|-------|------|-----------|
| `schema_version` | 3 | Debugging/forensics only; belongs in the footer. |
| `summary.added` / `summary.removed` | 1 | The Layer 0 triple counts shown in the summary strip. |
| `summary.total` | 1 | "N changes" headline figure. |
| `summary.breaking` | 1 | Drives the status badge colour and the page's first sentence. |
| `changes[]` | 1 | The body of the report; the whole point. |

## Per-change (`Change`)

| Field | Tier | Rationale |
|-------|------|-----------|
| `layer` | 3 | Used internally to split structural vs. syntactic; not surfaced as a label. |
| `kind` | 2 | Becomes the human noun ("Class renamed"); shown on each card. |
| `severity` | 1 | The left stripe + badge; the primary sort/group axis. |
| `subject` | 2 | The IRI a change is about; the card's subtitle. |
| `summary` | 1 | The producer's one-line phrasing; the card headline and the JS-less fallback. |
| `details` | 2 | The per-kind payload; revealed on card expansion (rows below). |
| `before` / `after` | 2 | Top-level mirror of decoded values; rendered as an `ArrowChange`. |

## Metadata (`Metadata`)

| Field | Tier | Rationale |
|-------|------|-----------|
| `metadata.severity_refinements[]` | 2 | The audit trail; the "this is why it's breaking" drilldown for story 4. |
| `severity_refinements[].change_id` | 3 | Links a refinement to its card; internal anchor, not displayed text. |
| `severity_refinements[].original_severity` / `refined_severity` | 2 | Rendered as `info → breaking` inside the card's "why" note. |
| `severity_refinements[].rule_id` | 2 | Shown as a small monospace tag ("rule: cardinality-tightened"). |
| `severity_refinements[].rationale` | 2 | The prose sentence explaining the bump. |
| `metadata.layer_counts` | 3 | Diagnostics; "show technical" panel only. |
| `metadata.subsumption_registry` | 3 | Internal; used to decide which Layer 0 triples are *unexplained*, never shown raw. |
| `metadata.rename_candidates[]` | 3 | Reserved; not emitted today. Reserve a "considered renames" technical slot. |
| `metadata.renames_applied[]` | 3 | Reserved; renames already surface as `*_renamed` changes in Tier 1. |
| `RenameCandidate.*` (`removed_iri`, `added_iri`, `entity_kind`, `confidence`, `evidence`, `score`) | 3 | Same reserved shape; only ever in the technical panel if emitted. |

## Detail payloads (per-kind `details`)

All `details.change_id` and `details.subsumes` / `cascade_subsumes` fields are
**Tier 3** uniformly: they are anchors and roll-up bookkeeping, never displayed
as text. Listed once here rather than repeated per type.

| Detail type → fields | Tier | Rationale |
|----------------------|------|-----------|
| `SyntacticDetails`: `subject`, `predicate`, `object`, `subject_iri`, `predicate_iri` | 3 | The raw triple; only in the collapsed "Unexplained Layer 0" section. |
| `EntityDetails`: `entity_iri`, `entity_kind`, `label`, `language` | 1/2 | Adds/removes of classes & properties are Tier 1 headlines; `label`/`language` are the Tier 2 quoted suffix. |
| `EntityKindChangedDetails`: `entity_iri`, `from_kind`, `to_kind` | 2 | A rarer structural change; card detail. |
| `ParentEdgeDetails`: `entity_iri`, `entity_kind`, `parent_iri` | 2 | Hierarchy gain/loss; card detail with an `IRIChip`. |
| `ReparentDetails`: `entity_iri`, `entity_kind`, `parents_before`, `parents_after`, `direction` | 2 | The `{A} → {B} (generalization)` arrow; card detail. |
| `CycleDetails`: `entity_iri`, `path` | 2 | The introduced cycle path, rendered as a breadcrumb. |
| `RestrictionDetails`: `entity_iri`, `via_predicate`, `on_property`, `before`, `after` | 2 | The restriction card; `before`/`after` carry decoded forms. |
| `RestrictionDecoded`: `kind`, `cardinality`, `filler`, `urn` | 2 | Rendered as readable English ("max 1 → max 2"); `urn` is Tier 3 (synthetic id). |
| `DomainRangeChangedDetails`: `property_iri`, `before`, `after` | 2 | `ArrowChange` on a property card. |
| `DomainRangeValueDetails`: `property_iri`, `value` | 2 | A single added/removed domain or range value. |
| `PairwiseClassDetails`: `entity_iri`, `other_iri` | 2 | Equivalent/disjoint edge; `A ≡ B` / `A ⊥ B`. |
| `ComplementDetails`: `entity_iri`, `before`, `after` | 2 | `owl:complementOf` set/unset. |
| `ComplexClassExpressionDetails`: `entity_iri`, `depth`, `note` | 2 | The opaque fallback; `note` shown, `depth` Tier 3. |
| `AnnotationChangedDetails`: `entity_iri`, `predicate_iri`, `predicate_short`, `language`, `before`, `after` | 2 | Label/comment edits; `predicate_iri` is Tier 3 (tooltip), `predicate_short` is the visible noun. |
| `AnnotationSingleDetails`: `entity_iri`, `predicate_iri`, `predicate_short`, `language`, `value`, `is_iri_value` | 2 | Annotation add/remove; same Tier split as above. |
| `AnnotationValue`: `value`, `is_iri_value` | 2 | One annotation value; `is_iri_value` decides chip vs. quoted-string rendering. |
| `DeprecationDetails`: `entity_iri` | 2 | "Deprecated: `era:X`"; card detail. |
| `OntologyMetadataDetails`: `ontology_iri`, `predicate_iri`, `predicate_short`, `language`, `before`, `after` | 2 | Ontology-header edits; `ontology_iri`/`predicate_iri` Tier 3. |
| `RenameDetails`: `before_iri`, `after_iri`, `entity_kind`, `confidence`, `evidence`, `score` | 1/2 | Renames are Tier 1 (own section); `confidence`/`evidence`/`score` are the Tier 2 `EvidenceList`. |

## Coverage note

Enums (`Severity`, `RenameableKind`, `RenameConfidence`) are value domains of the
fields above, not standalone data points; they are covered by their host field's
row. `ChangeIdList` is the type of `subsumes`/`cascade_subsumes`, covered by the
Tier 3 bookkeeping rule. With those accounted for, no `$defs` member is
unclassified.
