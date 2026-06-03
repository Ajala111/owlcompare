# Component 08: Layer 1 Structural Diff — Restrictions

## Identity

- **Component number:** 08
- **Name:** Structural diff — restrictions (Layer 1, third slice)
- **Module paths:**
  - `src/owlcompare/diff/structural/restrictions.py` — this component's implementation
  - `src/owlcompare/diff/structural/_restriction_index.py` — internal helper: indexes the restriction triples by their reified URN and by the entity they're attached to
  - `src/owlcompare/diff/structural/_class_expression.py` — small helpers for decoding shallow class expressions into readable summaries
- **Roadmap phase:** Phase 2 (fourth Layer 1 slice; last new code in Phase 2 before severity classifier polish)
- **Depends on components:** 02 (snapshot/model), 04 (canonicalize; restriction URNs), 05 (Layer 0 + Change), 06 (entity diff + orchestrator + SubsumptionRegistry), 07 (hierarchy diff — for non-restriction subClassOf coordination)
- **Depended on by (planned):** 09 (annotations), 10 (severity classifier), 14–17 (renderers)

## Purpose

Detect OWL restriction and class-axiom changes between two canonicalized snapshots and consolidate them into single Layer 1 `Change` records. After this component, the most visible improvement is: the three or four "unexplained" Layer 0 triples representing a reified anonymous restriction collapse into one meaningful change — *"Cardinality restriction on era:Track changed: era:hasMaxSpeed max 1 → max 2"*.

What would break if we removed it: every restriction change would appear as 3–4 unexplained Layer 0 triples in every diff output forever. Most ontology *evolution* in practice is restriction tuning (tightening cardinalities, narrowing filler types). Without this component, the project's headline use case looks like noise.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Snapshot A | `OntologySnapshot` | Loader + Canonicalize | `canonical=True` precondition |
| Snapshot B | `OntologySnapshot` | Loader + Canonicalize | Same |
| Layer 0 changes | `list[Change]` | Component 05 | For subsumption matching |
| Registry | `SubsumptionRegistry` | Components 06 + 07 (already updated) | Mutated in-place |
| Options | `DiffOptions` | Optional | |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `list[Change]` | list | Orchestrator | All `layer="structural"`; new `kind` values described below |
| Updated registry | (in-place) | Renderers | More Layer 0 changes now subsumed |

## Public API

```python
# src/owlcompare/diff/structural/restrictions.py

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
    """Compute Layer 1 restriction-level differences.

    Emits Change records of the following kinds:
      - 'restriction_added' / 'restriction_removed' / 'restriction_changed'
          for cardinality, someValuesFrom, allValuesFrom, hasValue restrictions
          attached to a named class via subClassOf or equivalentClass
      - 'domain_changed' / 'range_changed'   (property domain/range, single value)
      - 'domain_added' / 'domain_removed'    (multi-domain ontologies)
      - 'range_added' / 'range_removed'
      - 'equivalent_class_added' / 'equivalent_class_removed'
      - 'disjoint_added' / 'disjoint_removed'
      - 'complement_set' / 'complement_unset'
      - 'complex_class_expression_changed'   — fallback for nested expressions

    Updates `registry` in-place. Returns the list of new Change records.
    """
```

The orchestrator wires this in: after `hierarchy.diff()` it now calls `restrictions.diff()` with the shared registry.

## Internal design

### Step 1 — Build per-side restriction indexes

`_restriction_index.py` produces, per snapshot, a structured view of every restriction reified by Component 04 — plus domain/range/equivalent/disjoint axioms (which are not anonymous but live in the same conceptual layer):

```python
@dataclass(frozen=True, slots=True)
class DecodedRestriction:
    """A restriction reified by Component 04, decoded into structured form."""
    urn: str                    # the canonical urn:owlcompare:restriction:<sha>
    attached_to: str            # IRI of the class the restriction is attached to
    via_predicate: str          # 'rdfs:subClassOf' | 'owl:equivalentClass'
    on_property: str | None     # owl:onProperty IRI (None if not present)
    kind: Literal[              # the restriction shape
        "min_cardinality", "max_cardinality", "exact_cardinality",
        "min_qualified_cardinality", "max_qualified_cardinality", "exact_qualified_cardinality",
        "some_values_from", "all_values_from", "has_value",
        "complex",              # nested expression we don't fully decode
    ]
    cardinality: int | None     # for cardinality kinds
    filler: str | None          # IRI of value range / individual / datatype filler
    filler_label: str | None    # human label for the filler if known


@dataclass(frozen=True, slots=True)
class RestrictionIndex:
    by_urn: dict[str, DecodedRestriction]              # restriction URN -> decoded
    by_attached_entity: dict[str, list[DecodedRestriction]]  # entity IRI -> restrictions on it
    domains: dict[str, frozenset[str]]                 # property IRI -> set of declared domain class IRIs
    ranges: dict[str, frozenset[str]]                  # property IRI -> set of declared range class IRIs / datatypes
    equivalent_class_sets: dict[str, frozenset[str]]   # class IRI -> set of equivalent class IRIs (named only)
    disjoint_sets: dict[str, frozenset[str]]           # class IRI -> set of disjoint class IRIs
    complement_targets: dict[str, str]                 # class IRI -> the class it's the complement of


def build(snapshot: OntologySnapshot) -> RestrictionIndex: ...
```

Building it:

1. Scan the canonical graph for every triple with subject starting `urn:owlcompare:restriction:`. Group triples by URN.
2. For each restriction URN, gather the type (`owl:Restriction`), `owl:onProperty`, and one of the value/cardinality predicates. Build a `DecodedRestriction`. If multiple value predicates are present (malformed) or the structure can't be parsed cleanly, set `kind="complex"`.
3. Scan for `?c rdfs:subClassOf ?urn` and `?c owl:equivalentClass ?urn` to populate `attached_to` and `via_predicate`.
4. Scan for `?p rdfs:domain ?d` and `?p rdfs:range ?r` for the simple non-anonymous cases.
5. Scan for `?a owl:equivalentClass ?b` where both are named classes.
6. Scan for `?a owl:disjointWith ?b` and the symmetric `owl:AllDisjointClasses` construct.
7. Scan for `?a owl:complementOf ?b`.

A restriction whose filler is itself a restriction URN (nested) is decoded with the outer kind set normally and `filler` pointing to the inner URN; the inner restriction lives separately in the index.

### Step 2 — Match restrictions across A and B

Two-pass matching. The goal: for each pair of (entity, on_property) where restrictions exist, classify the change.

**Pass 1 — exact URN match (cheap path):**

If the same restriction URN appears in both A and B, attached to the same entity via the same predicate, **no change is emitted** — the restriction is identical post-canonicalization. The 3+ Layer 0 triples involving that URN are still subsumed (registered to a `_no_change` placeholder) so they're hidden from the unexplained section.

Wait — that's a footgun. We don't want to hide *unchanged* triples either; they aren't in the Layer 0 diff at all. Skip subsumption for unchanged restrictions; the triples don't exist in `layer0_changes`.

**Pass 2 — semantic match (the interesting path):**

For each entity that has any restriction in A or B:
1. Group restrictions in A by `(via_predicate, on_property)` and same for B.
2. For each `(via_predicate, on_property)` group:
   - **Both A and B have restrictions on this group:** check if the kind matches.
     - Same kind, different cardinality value → `restriction_changed` (cardinality tuning).
     - Same kind, different filler → `restriction_changed` (filler swap).
     - Different kind (e.g., min_cardinality in A, exact_cardinality in B) → `restriction_changed` (kind change, more semantically loaded).
     - In a multi-restriction group, match greedily by kind first, then by URN order; surplus restrictions on the A side become `restriction_removed`, surplus on the B side become `restriction_added`.
   - **Only A:** `restriction_removed`.
   - **Only B:** `restriction_added`.

3. For each `(via_predicate, on_property)` where one side's filler is a nested expression (`urn:owlcompare:restriction:` filler): if the *outer* shape changed (cardinality value, kind), emit normally; if only the *inner* changed, emit `complex_class_expression_changed` (the outer shape is the same; the deep change is too complex to summarize crisply in v1).

### Step 3 — Domain / range / equivalent / disjoint / complement

Simpler logic since none of these involve anonymous structures:

- For each property, compute `domains_a - domains_b` (removed) and `domains_b - domains_a` (added). Emit `domain_added` / `domain_removed`. If the property has exactly one domain in both A and B and they differ → emit a single `domain_changed` instead. Same for range.
- For each class, compute equivalent-class set symmetric difference. Emit `equivalent_class_added` / `equivalent_class_removed` per IRI in the symmetric difference.
- For each class, compute disjoint set symmetric difference. Emit `disjoint_added` / `disjoint_removed`.
- For complement: changes are limited — either set (added/changed), unset (removed), or unchanged. Emit `complement_set` (carry old + new in details) or `complement_unset`.

### Step 4 — Coordinate with Components 06 and 07

For each Layer 1 restriction change candidate:
1. Look up the entity in the registry. If it was emitted as `class_removed` / `object_property_removed` / etc. by Component 06, the restriction changes are already implied — read the registry and add the restriction's underlying Layer 0 triples to the entity-level change's subsumption rather than emitting a separate restriction change. (i.e., when a whole class is removed, don't emit "restriction on it was also removed" separately.)
2. Same for entities removed/added at Component 06 — the restriction triples on a brand-new class are part of "class added," not standalone.
3. Hierarchy (Component 07) doesn't conflict — the `subClassOf <urn:owlcompare:restriction:...>` triples are *excluded* from Component 07's hierarchy index (per its spec), so there's no double-attribution there.

### Step 5 — Subsumption

For each emitted Layer 1 restriction change, find the matching Layer 0 changes and register them. Matches:

- `restriction_added` (URN X): every Layer 0 `triple_added` where subject is X (typically: `rdf:type owl:Restriction`, `owl:onProperty ?p`, `owl:maxCardinality "n"`...) PLUS the `subClassOf X` (or `equivalentClass X`) triple_added.
- `restriction_removed` (URN X): symmetric — all triples involving X on the removed side.
- `restriction_changed`: subsumes both A's URN triples (removed) AND B's URN triples (added) — the change is the unification.
- `domain_added` for `(property, domain_iri)`: the matching `rdfs:domain` `triple_added`.
- `range_added` likewise.
- `equivalent_class_added`, etc.: the matching triple_added/removed.

### Severity rules

| Kind | Severity |
|------|----------|
| `restriction_removed` | `non_breaking` (relaxing constraints doesn't break valid existing data) |
| `restriction_added` | `breaking` (new constraint may invalidate existing data) |
| `restriction_changed` (cardinality tightened, e.g., max 5 → max 3) | `breaking` |
| `restriction_changed` (cardinality relaxed, e.g., max 3 → max 5) | `non_breaking` |
| `restriction_changed` (kind change, e.g., `someValuesFrom` → `allValuesFrom`) | `breaking` (universal is strictly stronger than existential) |
| `restriction_changed` (filler narrowed — new filler is a subclass of old) | `breaking` |
| `restriction_changed` (filler widened — new filler is a superclass of old) | `non_breaking` |
| `restriction_changed` (filler swap, no subtype relation) | `breaking` |
| `domain_changed` (single → single, different) | `breaking` |
| `domain_added` (broadening) | `non_breaking` |
| `domain_removed` (narrowing, less constraint) | `non_breaking` |
| `range_changed` (single → single, different) | `breaking` |
| `range_added` | `non_breaking` |
| `range_removed` | `non_breaking` |
| `equivalent_class_added` | `non_breaking` (new equivalence is information; doesn't invalidate existing) |
| `equivalent_class_removed` | `breaking` (lost semantic identity) |
| `disjoint_added` | `breaking` (existing data may now violate disjointness) |
| `disjoint_removed` | `non_breaking` |
| `complement_set` | `breaking` |
| `complement_unset` | `non_breaking` |
| `complex_class_expression_changed` | `breaking` (defensive: opaque change, assume breaking) |

### Note on domain/range narrowing detection

This spec originally called for Component 08 to use Component 07's hierarchy index to classify a `domain_changed` / `range_changed` as narrowing (`breaking`) vs. widening (`non_breaking`), defaulting to `breaking` when the asserted hierarchy can't decide. **As implemented, Component 08 does *not* attempt that analysis for domain/range: `_dr_changed` defaults every single-value `domain_changed` / `range_changed` to `breaking` unconditionally.** The hierarchy-aware widening check for domain/range lives instead in **Rule 4 of Component 10's severity classifier** (`dr-widening-detected-late`), which demotes such a change to `non_breaking` when the combined asserted hierarchy shows the new value is an ancestor of the old.

This placement is intentional, not an oversight:

- By the time Component 10 runs, the orchestrator has executed *all* of Layer 1 — including Component 07, which may have added a `subClassOf` edge present only in v2. That late edge can be exactly what makes an otherwise-undecidable domain/range comparison decidable, so the check is strictly more capable when run after the full Layer 1 pass than inside Component 08.
- Keeping Component 08's per-slice severity simple and cautious (default `breaking`) and concentrating all *cross-cutting* severity judgments in Component 10 matches the project's layering (DD-008): each slice sets a conservative default; the classifier refines with full context.

Note this applies only to **domain/range**. Restriction **filler** narrowing/widening (the `restriction_changed` rows above) *is* decided inside Component 08, using Component 07's asserted hierarchy via `_combined_parents` / `_filler_severity`; that comparison does not depend on a late v2 edge in the same way and stays local to the slice.

### Subject and summary

`Change.subject` = the entity IRI the restriction is attached to (the class, or the property for domain/range, or the class for equivalent/disjoint/complement).

`Change.summary` patterns (with prefixed IRIs when known):

- `"Restriction added on era:Track: max 1 era:hasMaxSpeed"` (cardinality)
- `"Restriction added on era:Track: era:hasGauge some era:Gauge"` (existential)
- `"Restriction changed on era:Track: era:hasMaxSpeed max 1 → max 2"` (cardinality tuning)
- `"Restriction changed on era:Track: era:hasGauge some era:Gauge → all era:Gauge"` (kind change)
- `"Restriction removed from era:Track: era:hasGauge some era:Gauge"`
- `"Domain changed on era:locatedOn: era:Signal → era:Asset"` (domain swap)
- `"Domain added on era:locatedOn: era:Platform"` (multi-domain extension)
- `"Range removed from era:locatedOn: era:Track"`
- `"era:Track equivalent class added: era:RailwaySegment"`
- `"era:Track disjoint with added: era:Person"`
- `"era:NotATrack complement of: era:Vehicle → era:Track"` (complement target swap)
- `"Complex class expression on era:Track changed (deep)"` (fallback)

### Details dictionary

For `restriction_changed`:

```python
details = {
    "change_id": "structural:restriction_changed:...",
    "entity_iri": "...",            # the class the restriction is on
    "via_predicate": "rdfs:subClassOf" | "owl:equivalentClass",
    "on_property": "...",           # the property IRI
    "before": {                     # decoded restriction in A
        "kind": "max_cardinality",
        "cardinality": 1,
        "filler": null,
        "urn": "urn:owlcompare:restriction:abc..."
    },
    "after": {                      # decoded restriction in B
        "kind": "max_cardinality",
        "cardinality": 2,
        "filler": null,
        "urn": "urn:owlcompare:restriction:def..."
    },
    "subsumes": [<layer0 change_ids>],
}
```

For `restriction_added` / `restriction_removed`: only `before` or only `after` is populated; the other is None.

For `domain_changed`:

```python
details = {
    "change_id": "...",
    "property_iri": "...",
    "before": "http://...DomainA",
    "after": "http://...DomainB",
    "subsumes": [...],
}
```

For `equivalent_class_added`, `disjoint_added`, etc.:

```python
details = {
    "change_id": "...",
    "entity_iri": "...",
    "other_iri": "...",   # the other class in the equivalent / disjoint relationship
    "subsumes": [...],
}
```

For `complex_class_expression_changed`:

```python
details = {
    "change_id": "...",
    "entity_iri": "...",
    "depth": <int>,              # how deep the expression nests
    "subsumes": [<all relevant layer0 ids>],
    "note": "Deep class expression change; structured diff deferred to v2.",
}
```

### Ordering

Within the structural section, sort by:

1. `kind` — `restriction_changed`, then `restriction_added`, `restriction_removed`, `domain_changed`, etc.
2. `subject` (entity IRI alphabetical)
3. `on_property` if applicable (for restriction kinds)

## Edge cases & failure modes

- **Restriction with no `owl:onProperty`:** malformed (or a class expression that isn't a restriction). Classify as `complex_class_expression_changed`.
- **Multiple value predicates on one URN** (e.g., both `someValuesFrom` and `maxCardinality`): malformed. Treat as `complex`.
- **Nested filler — outer cardinality same, inner restriction changed:** emit `complex_class_expression_changed`. Don't try to summarize.
- **`owl:equivalentClass` where one side is a restriction URN:** treat as `equivalent_class_added/removed` with `other_iri = urn:owlcompare:restriction:...`. The renderer can display these as "equivalent to anonymous restriction X" if it cares.
- **Entire class removed (Component 06's territory):** the registry tells us. Skip emitting restriction changes for that entity; the restriction triples are subsumed under `class_removed`.
- **Domain/range on a property that's removed entirely (Component 06):** likewise skip.
- **`owl:AllDisjointClasses`** (the n-ary form): expand into pairwise disjoint relations in the index. Diff per pair.
- **Synthetic IRIs (`urn:owlcompare:list:*`):** these are RDF lists from collapsed list structures. Restriction context doesn't usually involve them, but if encountered, treat as opaque and skip emission for the list URN itself — the list change will surface via its parent restriction's `complex` classification or be subsumed.
- **`owl:hasSelf` restrictions:** rare; treat as `kind = "complex"` for v1.
- **Datatype restrictions** (`owl:DatatypeProperty` with `owl:withRestrictions`): out of scope for v1; treat as `complex`. Add to backlog.

## Dependencies to add

None.

## Acceptance tests

Located in `tests/unit/test_restriction_index.py`, `tests/unit/test_diff_structural_restrictions.py`, extensions to `tests/unit/test_diff_orchestrator.py`, and extensions to `tests/integration/test_diff_integration.py`.

### Fixtures to add (`tests/fixtures/diff/restrictions/`)

Each fixture pair: `_before.ttl` / `_after.ttl`.

- `cardinality_tightened` — `max 5 → max 3` on one property.
- `cardinality_relaxed` — `max 3 → max 5`.
- `cardinality_kind_change` — `min 1 → exact 1`.
- `someValues_to_allValues` — `someValuesFrom → allValuesFrom` (kind change, breaking).
- `someValues_filler_narrowed` — `someValuesFrom Gauge → someValuesFrom NarrowGauge` (Gauge is subclass; should detect narrowing as `breaking`).
- `someValues_filler_widened` — inverse (`non_breaking`).
- `restriction_added` — class gains a new cardinality restriction.
- `restriction_removed` — class loses a cardinality restriction (other restrictions retained).
- `multiple_restrictions_one_changed` — class has 3 restrictions; one cardinality changes.
- `qualified_cardinality` — `min 1 hasGauge Gauge` cardinality with typed filler.
- `domain_swap` — single-domain swap (breaking).
- `domain_extended` — multi-domain extension.
- `range_removed` — property loses one of multiple ranges.
- `equivalent_class_added` — `A equivalentClass B` introduced in v2.
- `disjoint_with_added` — disjointness introduced (breaking).
- `complement_set` — class becomes a complement of another.
- `nested_expression_change` — restriction with a nested expression where the inner changes; should emit `complex_class_expression_changed`.
- `class_with_restriction_removed_entirely` — entire class removed; restriction changes should NOT be emitted separately (Component 06 subsumes).
- `era_restrictions_v1.ttl` / `era_restrictions_v2.ttl` — flagship: era:Track with two restrictions in v1, one in v2 (one removed, one cardinality tightened), plus an added existential restriction. Tests three behaviors in one file.

### Test list

**`tests/unit/test_restriction_index.py`:**
- [ ] `test_build_decodes_max_cardinality`
- [ ] `test_build_decodes_min_cardinality`
- [ ] `test_build_decodes_exact_cardinality`
- [ ] `test_build_decodes_someValues`
- [ ] `test_build_decodes_allValues`
- [ ] `test_build_decodes_hasValue`
- [ ] `test_build_decodes_qualified_cardinality_with_filler`
- [ ] `test_build_collects_domain_per_property`
- [ ] `test_build_collects_range_per_property`
- [ ] `test_build_collects_equivalent_class_pairs`
- [ ] `test_build_collects_disjoint_pairs`
- [ ] `test_build_expands_alldisjointclasses_to_pairs`
- [ ] `test_build_marks_malformed_as_complex`
- [ ] `test_build_records_via_predicate_subclassof_vs_equivalentclass`
- [ ] `test_build_attached_to_resolved_for_subclassof_restriction`
- [ ] `test_build_handles_nested_filler_urns`

**`tests/unit/test_diff_structural_restrictions.py`:**
- [ ] `test_diff_requires_canonical_inputs`
- [ ] `test_diff_identical_inputs_returns_empty`
- [ ] `test_cardinality_tightened_severity_breaking`
- [ ] `test_cardinality_relaxed_severity_non_breaking`
- [ ] `test_cardinality_kind_change_emits_restriction_changed`
- [ ] `test_someValues_to_allValues_severity_breaking`
- [ ] `test_someValues_filler_narrowed_severity_breaking`
- [ ] `test_someValues_filler_widened_severity_non_breaking`
- [ ] `test_restriction_added_severity_breaking`
- [ ] `test_restriction_removed_severity_non_breaking`
- [ ] `test_multiple_restrictions_one_changed_emits_one_change`
- [ ] `test_qualified_cardinality_decoded_correctly`
- [ ] `test_domain_swap_emits_domain_changed`
- [ ] `test_domain_extended_emits_domain_added`
- [ ] `test_range_removed_emits_range_removed`
- [ ] `test_equivalent_class_added_emits_change`
- [ ] `test_disjoint_with_added_severity_breaking`
- [ ] `test_complement_set_emits_change_with_before_after`
- [ ] `test_nested_expression_emits_complex_class_expression_changed`
- [ ] `test_class_removed_does_not_emit_separate_restriction_change` — Component 06 subsumes.
- [ ] `test_restriction_change_subsumes_corresponding_layer0_triples`
- [ ] `test_change_id_present_in_details`
- [ ] `test_summary_uses_prefixed_iris_when_known`
- [ ] `test_summary_cardinality_change_uses_arrow_notation` — "max 1 → max 2"
- [ ] `test_summary_someValues_kind_change_readable`
- [ ] `test_ordering_groups_kind_then_subject`

**`tests/unit/test_diff_orchestrator.py` (extensions):**
- [ ] `test_orchestrator_runs_restrictions_after_hierarchy`
- [ ] `test_orchestrator_layer1_changes_include_restrictions`
- [ ] `test_orchestrator_diffresult_metadata_counts_restriction_changes`

**`tests/integration/test_diff_integration.py` (extensions):**
- [ ] `test_era_restrictions_fixture_emits_three_changes` — exact counts: 1 cardinality_tightened, 1 restriction_removed, 1 restriction_added.
- [ ] `test_era_restrictions_subsumes_all_restriction_triples` — no `urn:owlcompare:restriction:` triples remain unsubsumed.
- [ ] `test_era_evolution_fixture_now_subsumes_restriction_triples` — the existing era_evolution fixture's `_restriction:ca0d5fa4` and `_restriction:e5a6c74d` triples are now subsumed under a `restriction_changed` change. Visible-by-default count drops further from 14 unexplained.
- [ ] `test_era_evolution_emits_cardinality_change_for_maxspeed` — assert there's a `restriction_changed` with `entity_iri = era:Track`, `before.cardinality = 1`, `after.cardinality = 2`.

## Out of scope (deliberately)

- Deep decomposition of nested class expressions (`intersectionOf`, `unionOf` containing further restrictions) — backlog.
- `owl:hasSelf` semantic interpretation (flagged as `complex` for now).
- `owl:DatatypeProperty` restrictions (`withRestrictions` facets) — backlog.
- `owl:propertyChainAxiom`, `owl:hasKey` — backlog.
- Owl 2 RL / EL / QL-specific shape checks — not our domain.
- Reasoning to determine "tightened" vs. "relaxed" without an explicit asserted hierarchy — falls back to `breaking` (cautious default).
- Renames (Components 11+).

## Open questions

- [x] **Q1 (resolved — adopted proposed):** When greedily matching multi-restriction groups (entity A has 3 max-cardinality restrictions on different properties; B has 2), the matching could pair by `on_property` first or by `kind` first. Order matters for the resulting `restriction_changed` vs. `restriction_added/removed` classification.
  **Decision:** Match by `on_property` first (most semantically meaningful), then by `kind` within the property group. Implemented as `_group` (buckets by `(via_predicate, on_property)`) feeding `_match_group`, which pairs in three passes: identical URNs, then same kind, then leftovers across kinds (a kind change). Unmatched A-side become `restriction_removed`, unmatched B-side become `restriction_added`.

- [x] **Q2 (resolved — adopted proposed):** For `restriction_changed` where the URN is *also* different (which it always is after canonicalization — same content yields same URN, different content yields different URN), do we report it as a content-change or as a URN-swap? Should `before.urn` and `after.urn` both be exposed?
  **Decision:** Expose both URNs in `details.before.urn` and `details.after.urn` (see `_decoded_dict`). The user-facing summary talks about cardinality/kind/filler — never about URNs. The shortened `_restriction:<8-hex>` form may still appear in detail-heavy renderings; that's fine.

- [x] **Q3 (resolved — adopted proposed, with the domain/range half relocated to Component 10):** For narrowing-vs-widening detection, should we use Component 07's hierarchy index (which captures asserted subClassOf) or attempt minimal reasoning?
  **Decision:** Asserted hierarchy only, no reasoning (transitive cases via reasoning are deferred to Layer 2). For restriction **fillers**, this is done inside Component 08: `_combined_parents` merges both snapshots' `class_parents` and `_is_descendant` walks them, defaulting to `breaking` on an incomparable swap. For **domain/range**, the implementation deliberately does *not* run this check in Component 08 — `_dr_changed` defaults to `breaking`, and the asserted-hierarchy widening check runs later as **Rule 4 of Component 10** (`dr-widening-detected-late`), after the whole Layer 1 pass has applied any new v2 hierarchy edges. See the "Note on domain/range narrowing detection" subsection above.

All three open questions were resolved by adopting the proposed answers during implementation.

## Resolved design notes (added during implementation)

- **Restriction-vs-entity coordination via the registry:** `restrictions.diff` does not receive Component 06's entity changes directly. To honour "subsume under the `class_*`/`*_property_*` change" for a wholly added/removed class or property, it reads the shared registry — finding the entity's `rdf:type` Layer 0 change and its Component 06 explainer — and registers the restriction (or domain/range) triples under that id, emitting no standalone restriction change (`_defer_restrictions`, `_defer_axiom`). This is the same registry-deferral pattern Component 07 uses for hierarchy edges.
- **Equivalent-class restriction attachment wins over the named-pair path:** a `?c owl:equivalentClass <restriction-URN>` triple is decoded as a restriction attached via `owl:equivalentClass` (it populates `attached_to`/`via_predicate`), not as an `equivalent_class_added/removed`. `equivalent_class_sets` only holds named-to-named pairs.
- **Disjointness is symmetric in the index, deduped at emission:** `disjoint_sets` stores both directions (and expands `owl:AllDisjointClasses` to symmetric pairs); the diff reduces to unordered `frozenset` pairs and emits one change per pair, with `subject` chosen as the lexicographically smaller IRI and Layer 0 matching tried in both edge directions.
- **N802 in tests:** several acceptance-test names mirror OWL constructs verbatim from this spec (`someValuesFrom`, `allValuesFrom`, `hasValue`, `AllDisjointClasses`), so the test function names carry mixedCase fragments. `ruff` `N802` is ignored for `tests/**` only (see `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`).
- **Lambda-in-f-string avoided:** the shortener is exposed as `_Ctx.short` (a bound method) rather than an inline `lambda` inside an implicitly-concatenated multi-line f-string, which makes `ruff format` 0.15.x panic (`Expected end tag of kind Group but found Indent`). Recorded as [[DD-017]] with the ruff `<0.16` pin; the workaround site carries a `# ruff-bug-0.15.x:` comment.

## References

- `docs/ARCHITECTURE.md` § Diff Engine (Layer 1)
- `docs/DESIGN_DECISIONS.md` § DD-006 (frozen), § DD-007 (canonicalize), § DD-008 (severity)
- `docs/GLOSSARY.md` § Change, § Restriction, § Cardinality
- Component 04 spec for restriction URN format
- Component 06 spec for orchestrator and SubsumptionRegistry
- Component 07 spec for hierarchy index (reused for narrowing/widening detection)
