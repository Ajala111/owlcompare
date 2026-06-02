# Component 07: Layer 1 Structural Diff — Hierarchy

## Identity

- **Component number:** 07
- **Name:** Structural diff — hierarchy (Layer 1, second slice)
- **Module paths:**
  - `src/owlcompare/diff/structural/hierarchy.py` — this component's implementation
  - `src/owlcompare/diff/structural/_hierarchy_index.py` — internal helper: indexed views of subClassOf / subPropertyOf graphs
- **Roadmap phase:** Phase 2 (third component)
- **Depends on components:** 02 (snapshot/model), 04 (canonicalize), 05 (Layer 0 + Change), 06 (orchestrator + SubsumptionRegistry)
- **Depended on by (planned):** 08 (restrictions), 09 (annotations), 10 (severity), 14–17 (renderers)

## Purpose

Detect changes in the class hierarchy (`rdfs:subClassOf`) and property hierarchy (`rdfs:subPropertyOf`) between two canonicalized snapshots. Produce Layer 1 `Change` records that explain what happened structurally — "Track was reparented from Equipment to Asset" — and link them to the underlying Layer 0 triples via subsumption.

What would break if we removed it: every hierarchy edit would appear as a pair of unexplained Layer 0 triples in the "unexplained" Layer 0 section, never consolidating into the human-meaningful "X moved" or "X has a new parent" framing.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Snapshot A | `OntologySnapshot` | Loader + Canonicalize | `canonical=True` precondition |
| Snapshot B | `OntologySnapshot` | Loader + Canonicalize | Same |
| Layer 0 changes | `list[Change]` | Component 05's output | Used for subsumption |
| Registry | `SubsumptionRegistry` | Component 06 | Mutated in-place |
| Options | `DiffOptions` | Optional | |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `list[Change]` | list | Diff orchestrator | All carry `layer="structural"`; new `kind` values described below |
| Updated subsumption | (in-place mutation) | Renderers | Adds entries to the registry |

## Public API

```python
# src/owlcompare/diff/structural/hierarchy.py

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
    """Compute Layer 1 hierarchy-level differences (subClassOf, subPropertyOf).

    Updates `registry` in-place to mark Layer 0 changes that are now explained
    by the structural changes returned here.

    Returns:
        A list of Change records with layer='structural'. Kinds include:
        'class_parent_added', 'class_parent_removed', 'class_reparented',
        'property_parent_added', 'property_parent_removed', 'property_reparented',
        'class_hierarchy_cycle_introduced' (rare; cycle flagged).
    """
```

The orchestrator (Component 06) wires this in: after `entities.diff()` it now calls `hierarchy.diff()` with the same arguments. Both share the registry, so subsumption accumulates correctly.

## Internal design

### Step 1 — Build hierarchy indexes for A and B

`_hierarchy_index.py` produces two views, one per snapshot:

```python
@dataclass(frozen=True, slots=True)
class HierarchyIndex:
    """Indexed asserted subClassOf / subPropertyOf graph."""
    class_parents: dict[str, frozenset[str]]   # IRI -> frozenset of direct parent IRIs
    class_children: dict[str, frozenset[str]]  # inverse (built lazily or eagerly)
    property_parents: dict[str, frozenset[str]]
    property_children: dict[str, frozenset[str]]


def build(snapshot: OntologySnapshot) -> HierarchyIndex: ...
```

Built by scanning the canonical graph for `?c rdfs:subClassOf ?p` and `?p rdfs:subPropertyOf ?q` triples. Filter out triples whose subject or object isn't a named entity (skip restrictions, blank nodes, restriction URNs). The synthetic `urn:owlcompare:restriction:*` IRIs are excluded — they're not entities, they're class expressions.

### Step 2 — Diff the indexes per entity

For each entity (class or property) that exists in either A's or B's index:

1. Get `parents_a = a_index.class_parents.get(iri, frozenset())`.
2. Get `parents_b = b_index.class_parents.get(iri, frozenset())`.
3. `removed = parents_a - parents_b`
4. `added = parents_b - parents_a`
5. If `removed` and `added` are both non-empty → emit a **`class_reparented`** change with full before/after parent sets.
6. If only `removed` is non-empty → emit one or more **`class_parent_removed`** changes (one per removed parent).
7. If only `added` is non-empty → emit one or more **`class_parent_added`** changes.

Symmetric logic applies for properties using `property_parents` and emitting `property_parent_added` / `property_parent_removed` / `property_reparented`.

### Step 3 — Annotate reparenting with direction hint

For each `class_reparented` change (and `property_reparented`), determine the "direction" of the move:

- **generalization**: the new parent set contains an ancestor of (any of) the old parent(s). The entity moved *up* the hierarchy (became more general).
- **specialization**: the new parent set contains a descendant of (any of) the old parent(s). The entity moved *down*.
- **lateral**: neither generalization nor specialization (truly moved sideways or the relationship is incomparable).

Compute by transitively walking the *new* hierarchy starting at the new parent(s) looking for the old parent(s) (specialization), and the *old* hierarchy starting at the old parent(s) looking for the new parent(s) (generalization). Limit recursion depth to 50 to avoid pathological cycles.

Record in `details["direction"]`. If neither side decides cleanly (or if the entity has multiple removed parents AND multiple added parents and they tell different stories), `direction = "lateral"`. The direction is a hint, not a contract.

### Step 4 — Cycle detection (defensive)

After step 2, check whether any new `subClassOf` edges create a cycle in B's hierarchy. A cycle = transitively, `A subClassOf B` AND `B subClassOf A`. Use a depth-first walk from each affected entity.

If a cycle is detected: emit one `class_hierarchy_cycle_introduced` change per affected entity, with severity `breaking`, listing the cycle path in `details["path"]` (e.g., `["A", "B", "C", "A"]`). This is rare in practice; pre-existing cycles in B (not introduced by the diff) are not flagged here.

### Step 5 — Subsumption

For each emitted Layer 1 hierarchy change, find the Layer 0 triple changes that match:

- **`class_parent_added`** for `(child, parent)`: subsumes any Layer 0 `triple_added` where subject=child, predicate=`rdfs:subClassOf`, object=parent.
- **`class_parent_removed`** for `(child, parent)`: subsumes any Layer 0 `triple_removed` matching the same pattern.
- **`class_reparented`** for entity X with before=Pold and after=Pnew: subsumes ALL the corresponding Layer 0 triples (one per old parent removed, one per new parent added).
- Property-side rules analogous.
- Cycle changes subsume the triples in the cycle path that were added in B.

Register each subsumption via `registry.register(higher.change_id, [matching_layer0_changes])`.

### Severity rules

| Kind | Severity |
|------|----------|
| `class_parent_added` (direction=`generalization`) | `additive` — entity gained a broader supertype, doesn't break existing consumers |
| `class_parent_added` (direction=`specialization` or `lateral`) | `non_breaking` — entity gained a new dimension of classification |
| `class_parent_removed` (still has other parents) | `non_breaking` |
| `class_parent_removed` (entity had only this one parent → now has none asserted) | `breaking` — entity is now classification-rootless |
| `class_reparented` (direction=`generalization`) | `non_breaking` — broader |
| `class_reparented` (direction=`specialization`) | `breaking` — narrower; instances that were valid may no longer be |
| `class_reparented` (direction=`lateral`) | `breaking` — semantics shifted |
| `property_parent_added` (any direction) | same logic as class side |
| `property_parent_removed` (any direction) | same logic as class side |
| `property_reparented` (any direction) | same logic as class side |
| `class_hierarchy_cycle_introduced` | `breaking` |

Property-side severity mirrors class-side. Severity is a default; Component 10 may refine.

### Subject and summary

`Change.subject` = the entity IRI whose hierarchy changed (the child, not the parent).

`Change.summary` patterns (with prefixed IRIs when known):

- `"Class era:Track gained parent era:Asset"` (class_parent_added)
- `"Class era:Signal lost parent era:Equipment"` (class_parent_removed)
- `"Class era:Track reparented: era:Equipment → era:Asset (generalization)"`
- `"Class era:Track reparented: {era:Equipment, era:Vehicle} → {era:Asset} (lateral)"` (multiple-parent case)
- `"Property era:hasGauge gained parent era:hasDimension"`
- `"Property era:locatedOn lost parent era:hasLocation"`
- `"Property era:hasGauge reparented: era:hasDimension → era:hasMeasurement (specialization)"`
- `"Cycle introduced: era:A → era:B → era:C → era:A"` (cycle case)

Multiple-parent cases use brace notation; single-parent cases skip braces for readability.

### Details dictionary

For `class_reparented` and `property_reparented`:

```python
details = {
    "change_id": "structural:class_reparented:...",
    "entity_iri": "http://data.europa.eu/949/Track",
    "entity_kind": "class",
    "parents_before": ["http://data.europa.eu/949/Equipment"],
    "parents_after": ["http://data.europa.eu/949/Asset"],
    "direction": "generalization",  # or "specialization" or "lateral"
    "subsumes": [<layer0 change_ids>],
}
```

For `class_parent_added` / `class_parent_removed`:

```python
details = {
    "change_id": "...",
    "entity_iri": "...",
    "entity_kind": "class",
    "parent_iri": "...",
    "subsumes": [<layer0 change_ids>],
}
```

For `class_hierarchy_cycle_introduced`:

```python
details = {
    "change_id": "...",
    "entity_iri": "...",  # an entity on the cycle
    "path": ["http://...A", "http://...B", "http://...C", "http://...A"],
    "subsumes": [<layer0 change_ids>],
}
```

### Ordering

Hierarchy changes sort within the structural section by:

1. `kind` (groups all reparents together, then parent_added, then parent_removed, then cycles)
2. `subject` (entity IRI alphabetical)

## Edge cases & failure modes

- **Entity exists in A but not B (already removed):** entity-level diff handles the remove; hierarchy diff *also* sees `parents_a = X`, `parents_b = empty`. Don't double-count: if the entity itself is in the "removed" list from `entities.diff()`, skip hierarchy emission for that entity. Read the registry to check.
- **Entity exists in B but not A (newly added):** symmetric. If the entity is in the entity-level "added" list, the parent assertions are part of the entity's introduction — subsume the Layer 0 triples under the `*_added` change, not under a `class_parent_added`. Read the registry.
- **Entity unchanged in entity-level diff but parents changed:** the bread-and-butter case. Emit hierarchy changes freely.
- **Synthetic IRIs in parent slot:** `_restriction:...` URNs *can* legitimately appear as `subClassOf` objects (a class is a subclass of a restriction). Treat these as edges into the restriction graph, NOT as hierarchy moves. **Skip emission of a hierarchy change when the parent is a synthetic URN.** Component 08 will handle restriction edges as a different kind of change.
- **Self-loop** (`A rdfs:subClassOf A`): not a cycle in the formal sense, but invalid. Emit a `class_hierarchy_cycle_introduced` with `path = [A, A]` only if introduced in B.
- **Pre-existing cycle in B unchanged by the diff:** don't flag. We only report changes.
- **Cycle in A removed in B:** treat as `class_parent_removed` for each edge in the cycle; don't emit a "cycle removed" change in v1 (we'd need symmetric logic; deferred).
- **Reparent across kinds (a class previously also a subPropertyOf, etc.):** impossible in well-formed OWL. If observed, treat the class and property hierarchies independently — each side sees its own remove or add.
- **Multi-parent entity loses one of three parents:** emit one `class_parent_removed`. Don't emit `class_reparented` — there must be both a removal AND an addition to count as reparenting.

## Dependencies to add

None. Pure-Python.

## Acceptance tests

Located in `tests/unit/test_hierarchy_index.py`, `tests/unit/test_diff_structural_hierarchy.py`, `tests/integration/test_diff_integration.py` (extensions).

### Fixtures to add (`tests/fixtures/diff/hierarchy/`)

Each fixture pair: `_before.ttl` / `_after.ttl`.

- `parent_added` — class gains a new parent (additive case).
- `parent_removed_keeps_others` — class loses one of multiple parents (non-breaking).
- `parent_removed_orphan` — class loses its only parent (breaking).
- `simple_reparent_generalization` — A was subclass of B; B was subclass of C. In B (new), A is now subclass of C directly. Direction should resolve as `generalization`.
- `simple_reparent_specialization` — inverse of above.
- `simple_reparent_lateral` — A was subclass of B; now A is subclass of D, where D has no hierarchy relation to B.
- `multi_parent_reparent` — A was subclass of {B, C}; now A is subclass of {D, E}. Lateral; brace summary expected.
- `property_parent_added` — object property gains a parent.
- `property_reparent` — property reparented.
- `cycle_introduced` — A subClassOf B, B subClassOf C, then in v2 add C subClassOf A → cycle. Should produce one cycle change.
- `synthetic_restriction_parent` — class has `subClassOf _restriction:...` in v1, doesn't in v2. Confirm NO hierarchy change is emitted (Component 08's territory).
- `era_hierarchy_v1.ttl` / `era_hierarchy_v2.ttl` — flagship: a small ERA-style hierarchy with `Track subClassOf TransportInfrastructure`, plus a `Signal subClassOf Equipment` that gets reparented in v2 to `Signal subClassOf Asset` (with `Asset` being a new class added independently — exercises Component 06 + 07 interaction).

### Test list

**`tests/unit/test_hierarchy_index.py`:**
- [ ] `test_build_index_captures_direct_class_parents`
- [ ] `test_build_index_captures_direct_property_parents`
- [ ] `test_build_index_skips_blank_node_parents`
- [ ] `test_build_index_skips_synthetic_restriction_parents`
- [ ] `test_build_index_empty_ontology_produces_empty_index`
- [ ] `test_class_children_inverse_of_parents`
- [ ] `test_property_children_inverse_of_parents`

**`tests/unit/test_diff_structural_hierarchy.py`:**
- [ ] `test_diff_requires_canonical_inputs`
- [ ] `test_diff_identical_inputs_returns_empty`
- [ ] `test_class_parent_added_emits_correct_change`
- [ ] `test_class_parent_added_when_entity_is_newly_added_does_not_emit_hierarchy_change` — subsumption is by Component 06; this layer skips.
- [ ] `test_class_parent_removed_when_other_parents_remain_severity_non_breaking`
- [ ] `test_class_parent_removed_when_orphaned_severity_breaking`
- [ ] `test_class_reparented_single_to_single_generalization` — direction=`generalization`.
- [ ] `test_class_reparented_single_to_single_specialization` — direction=`specialization`.
- [ ] `test_class_reparented_single_to_single_lateral` — direction=`lateral`.
- [ ] `test_class_reparented_severity_generalization_non_breaking`
- [ ] `test_class_reparented_severity_specialization_breaking`
- [ ] `test_class_reparented_severity_lateral_breaking`
- [ ] `test_class_reparented_multi_parent_uses_brace_notation`
- [ ] `test_class_reparented_emits_single_change_not_add_plus_remove` — must not emit both `class_parent_added` and `class_parent_removed` for an entity that has both.
- [ ] `test_property_parent_added_emits_correct_kind`
- [ ] `test_property_reparented_emits_correct_kind`
- [ ] `test_synthetic_restriction_parent_does_not_emit_hierarchy_change`
- [ ] `test_cycle_introduced_emits_cycle_change_with_path`
- [ ] `test_cycle_self_loop_emits_cycle_change`
- [ ] `test_preexisting_cycle_in_b_not_flagged`
- [ ] `test_change_subsumes_corresponding_layer0_triples`
- [ ] `test_change_id_present_in_details`
- [ ] `test_summary_uses_prefixed_iris_when_known`
- [ ] `test_summary_includes_direction_for_reparent`
- [ ] `test_summary_multi_parent_uses_braces`
- [ ] `test_ordering_groups_kinds_then_subjects`
- [ ] `test_hierarchy_diff_does_not_duplicate_entity_diff_subsumption` — when entity X was both newly added (entities) AND has parent edges (hierarchy), subsumption from entities should NOT be overridden by hierarchy.

**`tests/unit/test_diff_orchestrator.py` (extensions):**
- [ ] `test_orchestrator_runs_hierarchy_after_entities`
- [ ] `test_orchestrator_layer1_changes_include_both_entities_and_hierarchy`
- [ ] `test_orchestrator_diffresult_metadata_counts_hierarchy_changes`

**`tests/integration/test_diff_integration.py` (extensions):**
- [ ] `test_era_hierarchy_fixture_emits_one_reparented_change` — `Signal` reparented `Equipment → Asset`.
- [ ] `test_era_hierarchy_fixture_emits_one_class_added_for_asset`
- [ ] `test_era_hierarchy_fixture_subsumes_subclassof_triples`
- [ ] `test_era_evolution_fixture_unchanged_results` — the existing era_evolution fixture has no hierarchy changes, so the visible default output for it should be identical to Component 06's output. Regression test.

## Out of scope (deliberately)

- Transitive reasoning over the hierarchy (Layer 2 / future).
- `owl:equivalentClass` and `owl:equivalentProperty` — they're not strict hierarchy; Component 08.
- `owl:disjointWith` — Component 08.
- Detecting that a removed edge was actually moved to an *equivalent* class — reasoning territory.
- Detecting renames disguised as remove+add of an entire entity (different IRI) — Components 11+.
- Showing the new hierarchy as a tree visualization — that's the HTML report (Phase 4).

## Open questions

- [x] **Q1 (resolved — adopted proposed):** For a reparent with multiple parents on both sides (e.g., `{A,B} → {C,D}`), should we emit one `class_reparented` change or four separate changes (2 removes + 2 adds)?
  **Decision:** One `class_reparented`. The whole point of Layer 1 is consolidation; emitting four lower-level changes defeats it. `direction` for these is `lateral` (a multi-to-multi move short-circuits to lateral in `_reparent_direction`). `details.parents_before` and `parents_after` carry the full data; the summary uses brace notation.

- [x] **Q2 (resolved — adopted proposed):** When detecting `direction` for a reparent, what's the recursion depth limit?
  **Decision:** 50 (`hierarchy._MAX_DEPTH`). The deepest real-world ontology hierarchies (SNOMED, NCIt) are around 20–30 deep; 50 is comfortable margin. The depth-limited, cycle-safe DFS gracefully returns "not reachable" (→ `"lateral"`) on depth exceed or a visited cycle.

- [x] **Q3 (resolved — adopted proposed):** Should `class_hierarchy_cycle_introduced` be emitted *per entity in the cycle* or *once per detected cycle*?
  **Decision:** Per entity. A cycle of N entities → N changes, each with the same `path` but a different `subject` (and therefore a different `change_id`). This makes filtering by `subject` work naturally; the user can de-dup on `path` if desired.
  **Note:** the `cycle_introduced` fixture entry above says "Should produce one cycle change" — that wording predates the Q3 resolution. Per Q3 the three-class cycle `A→B→C→A` produces **three** cycle changes (one per entity), which the acceptance test `test_cycle_introduced_emits_cycle_change_with_path` pins.

All three open questions were resolved by adopting the proposed answers during implementation.

## Resolved design notes (added during implementation)

- **Direction for `class_parent_added` / `property_parent_added`:** the spec gives an explicit direction algorithm only for reparents, but the severity table keys parent-added off direction. We compute it by comparing the added parent against the entity's *retained* parents: `generalization` if the added parent is an ancestor of a retained parent (broader supertype → `additive`); `specialization` if it is a descendant; otherwise `lateral` (a new classification axis → `non_breaking`). When the entity had no other parents, the result is `lateral`. Direction is used only for severity here and is **not** stored in the parent-added/removed `details` (which carry just `entity_iri`, `entity_kind`, `parent_iri`, `subsumes`, `change_id`, per the spec).
- **Deferral via the registry:** `hierarchy.diff` does not receive Component 06's entity changes directly. To honour the "subsume under the `*_added`/`*_removed` change" rule for newly added/removed entities, it reads the shared registry — it finds the entity's `rdf:type` Layer 0 change, looks up its explainer (Component 06's change id), and registers the entity's hierarchy edges under that id. No standalone hierarchy change is emitted for such entities.

## References

- `docs/ARCHITECTURE.md` § Diff Engine (Layer 1)
- `docs/DESIGN_DECISIONS.md` § DD-008 (severity), § DD-006 (frozen)
- `docs/GLOSSARY.md` § Change, § Layer
- Component 06 spec for the orchestrator / subsumption pattern
