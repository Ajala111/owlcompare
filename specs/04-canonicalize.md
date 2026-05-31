# Component 04: Canonicalization

## Identity

- **Component number:** 04
- **Name:** Canonicalization
- **Module path:** `src/owlcompare/canonicalize.py` (primary), with internal helper modules under `src/owlcompare/_canonical/` if the implementation grows
- **Roadmap phase:** Phase 1 (final component)
- **Depends on components:** 02 (consumes `OntologySnapshot`, produces `OntologySnapshot`)
- **Depended on by (planned):** 05–09 (all diff layers)

## Purpose

Normalize an `OntologySnapshot` so that two semantically-equivalent inputs produce structurally-identical canonical forms. This is the prerequisite that makes meaningful diffing possible — without it, every diff layer drowns in spurious blank-node-label changes and triple-ordering noise.

What would break if we removed it: every diff layer would produce thousands of false-positive "changes" for any two real-world ontologies, because no two serializations of the same ontology are byte-identical even when semantically identical.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Snapshot | `OntologySnapshot` | Loader output (Component 02) | Not modified; new snapshot returned |
| Options | `CanonicalizeOptions` | Optional dataclass | Knobs for which passes run, debug output |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| Canonical snapshot | `OntologySnapshot` | Diff layers | Same shape as input; `graph` is normalized; new `canonical` field set to `True` |
| `CanonicalizationError` | exception | Library caller | Subclass of `OwlCompareError`, exit code 4 |

## Public API

```python
# src/owlcompare/canonicalize.py

from dataclasses import dataclass
from .model import OntologySnapshot


@dataclass(frozen=True, slots=True)
class CanonicalizeOptions:
    canonicalize_blank_nodes: bool = True
    reify_restrictions: bool = True
    collapse_lists: bool = True
    sort_triples: bool = True
    algorithm: str = "rdfc-1.0"   # only option in v1; future: "urdna-2015", "custom"


def canonicalize(
    snapshot: OntologySnapshot,
    options: CanonicalizeOptions | None = None,
) -> OntologySnapshot:
    """Return a canonicalized copy of the input snapshot.

    The returned snapshot has the same entities (same IRIs) but a normalized
    graph: blank nodes have stable labels, anonymous restrictions are reified
    with deterministic identifiers, RDF lists are collapsed, and triples are
    sorted. The original snapshot is not modified.

    Raises:
        CanonicalizationError: if a normalization pass fails.
    """
```

Also extend `OntologySnapshot` in `model.py` with a new boolean field:

```python
@dataclass(frozen=True)
class OntologySnapshot:
    # ...existing fields...
    canonical: bool = False  # True if produced by canonicalize()
```

## Exception

```python
# Add to src/owlcompare/exceptions.py
class CanonicalizationError(OwlCompareError):
    """Failure during canonicalization."""
    exit_code: int = 4
```

## CLI integration

Add a `canonicalize` subcommand to `cli.py`. Two purposes: (a) let users see the canonical form for debugging, (b) provide a clean way to test the component end-to-end.

```
owlcompare canonicalize [OPTIONS] SOURCE

Arguments:
  SOURCE                File path or URL  [required]

Options:
  --format [turtle|xml|n3|nt|json-ld|trig]   Format hint (passed to loader)
  --out PATH                                  Output file (default: stdout)
  --output-format [turtle|nt]                 Serialization for output (default: turtle)
  --no-blank-nodes                            Skip blank node canonicalization
  --no-reify-restrictions                     Skip restriction reification
  --no-collapse-lists                         Skip list collapsing
  --no-sort                                   Skip triple sorting
  --help                                      Show this message and exit
```

Behavior: load → canonicalize → serialize. Output the resulting Turtle (or N-Triples) to stdout or `--out`. Exit 0 on success, 3 on load error, 4 on canonicalization error.

Don't render a summary panel here — the output should be machine-friendly Turtle/NT. A separate `--summary` flag could be added later; out of scope for v1.

## Internal design

### Pass 1 — Blank node canonicalization

Use the **RDF Dataset Canonicalization (RDFC-1.0)** algorithm, the W3C Recommendation. rdflib implements this via `rdflib.compare.to_canonical_graph()`. Output: a new `Graph` where blank node labels are stable hashes of their structural position.

The same blank node, expressing the same restriction, in two different input files, gets the same label.

**Edge case:** very large blank-node-heavy ontologies make RDFC-1.0 expensive (O(n²) in pathological cases). For v1, accept this cost. If profiling shows it dominates, the option `algorithm="custom"` is reserved for a faster simplified pass.

### Pass 2 — Restriction reification

Anonymous OWL restrictions look like:

```turtle
:Track rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty :hasGauge ;
    owl:someValuesFrom :Gauge
] .
```

These are syntactically anonymous (the restriction is a blank node) but semantically content-addressable: the same `(owl:Restriction, onProperty=hasGauge, someValuesFrom=Gauge)` should compare equal across ontologies.

After RDFC-1.0, blank nodes already have stable labels. The reification pass goes further:

1. Find every blank node typed as `owl:Restriction`, `owl:Class` (anonymous unions/intersections/complements), or one of the OWL class expression constructors.
2. Compute a content hash from the restriction's properties (`onProperty`, `someValuesFrom`, `allValuesFrom`, `hasValue`, `qualifiedCardinality`, etc., recursing for nested expressions).
3. Replace the blank node with a deterministic IRI in a reserved namespace: `urn:owlcompare:restriction:<hash>`.
4. Update all in-graph references.

After this pass, anonymous restrictions are no longer anonymous — they have content-addressed URNs. Diff layers can treat them as named entities.

**Why a `urn:owlcompare:` namespace:** clearly marks these as synthetic, unambiguous, never collides with user IRIs, doesn't pollute any HTTP namespace.

### Pass 3 — RDF list collapsing

RDF lists serialize as:

```turtle
:something :hasItems ( :a :b :c ) .
```

Internally that's:

```
:something :hasItems _:list1 .
_:list1 rdf:first :a .
_:list1 rdf:rest  _:list2 .
_:list2 rdf:first :b .
_:list2 rdf:rest  _:list3 .
_:list3 rdf:first :c .
_:list3 rdf:rest  rdf:nil .
```

The pass: detect blank-node chains that are RDF lists, and convert them to a single reified IRI in `urn:owlcompare:list:<hash>` namespace, with companion triples preserving the ordered content. This keeps order-dependent diffs (list reorderings) detectable as such, instead of appearing as random blank-node mutations.

### Pass 4 — Triple sorting

The simplest pass. Produce a new `Graph` with triples added in deterministic order. Order: by (subject_term, predicate_term, object_term) using rdflib's `Node.n3()` representation as the sort key for stability across versions.

This doesn't change RDF semantics (sets are unordered), but produces byte-identical Turtle output for byte-identical inputs.

### Composition

```python
def canonicalize(snapshot, options=None):
    opts = options or CanonicalizeOptions()
    graph = snapshot.graph
    if opts.canonicalize_blank_nodes:
        graph = _canonicalize_blank_nodes(graph)
    if opts.reify_restrictions:
        graph = _reify_restrictions(graph)
    if opts.collapse_lists:
        graph = _collapse_lists(graph)
    if opts.sort_triples:
        graph = _sort_triples(graph)
    return replace(snapshot, graph=graph, canonical=True)
```

Each pass takes a graph and returns a new graph; they compose cleanly. Each pass is independently testable.

### Idempotency

`canonicalize(canonicalize(s)) == canonicalize(s)` must hold. Add an explicit test for it. This is the safest single check that the pipeline is correct.

## Edge cases & failure modes

- **Already canonical input** (the `canonical` flag is True): re-running is a no-op-ish — should still produce the same output, idempotently.
- **Empty graph:** returns an empty canonical snapshot with `canonical=True`. No error.
- **Graph with no blank nodes:** blank-node pass is a no-op; other passes still run.
- **Self-referential anonymous restriction** (`:A owl:equivalentClass [ owl:intersectionOf ( :A :B ) ]`): RDFC-1.0 handles cycles; our reification must too. The recursion must detect cycles and break them with a placeholder hash.
- **Malformed list** (an `rdf:first` without a corresponding `rdf:rest`): leave the triples as-is, log a warning at INFO. Do not raise.
- **Hash collision** in restriction reification: extraordinarily unlikely with SHA-256; if detected (extremely unlikely), append a counter suffix. Add a test that demonstrates two distinct restrictions get distinct URNs.
- **Graph with N-Quads / multiple named graphs:** v1 accepts only the default graph. If named graphs are detected, raise `CanonicalizationError("named graphs not supported in v1")` with exit code 4.

## Performance targets

| Ontology size | Canonicalization time |
|---------------|------------------------|
| Small (< 1k triples) | < 200 ms |
| Medium (1k–10k triples) | < 3 s |
| Large (10k–100k triples) | < 30 s |

Measured separately from load time. If a pass exceeds these substantially, log an INFO message noting which pass is slowest.

## Dependencies to add

None — all needed functionality is in rdflib (already approved in DD-001). Specifically:
- `rdflib.compare.to_canonical_graph()` for RDFC-1.0.
- `rdflib.collection.Collection` for list detection.
- Standard `hashlib` for content hashing.

## Acceptance tests

Located in `tests/unit/test_canonicalize.py` (the main suite) and additions to `tests/unit/test_cli_canonicalize.py`.

### Fixtures to add (nine total, in `tests/fixtures/canonicalize/`)

- `same_ontology_different_serialization_a.ttl` and `..._b.ttl` — the same ontology, one written compactly, one written verbosely (different blank node labels, different triple order). Canonicalizing both must produce byte-identical Turtle output.
- `restriction_simple.ttl` — a class with a simple `someValuesFrom` restriction.
- `restriction_nested.ttl` — a restriction whose filler is itself a restriction (recursion test).
- `restriction_self_ref.ttl` — a self-referential anonymous restriction (cycle test).
- `lists.ttl` — uses an RDF list.
- `lists_reordered.ttl` — the same triples but with the list elements in a different order (must produce a *different* canonical form).
- `with_named_graph.trig` — a TriG file with a named graph (must raise `CanonicalizationError`).
- `malformed_list.ttl` — an `rdf:first` triple with no `rdf:rest` companion.

### Test list

**Core pipeline:**
- [ ] `test_canonicalize_empty_graph_returns_canonical_flag_true`
- [ ] `test_canonicalize_sets_canonical_flag`
- [ ] `test_canonicalize_does_not_mutate_input` — input snapshot's `graph` is unchanged after the call.
- [ ] `test_canonicalize_is_idempotent` — `canonicalize(canonicalize(s)).graph` equals `canonicalize(s).graph` (triple-by-triple).
- [ ] `test_canonicalize_two_equivalent_inputs_produce_identical_output` — load both `same_ontology_different_serialization_a.ttl` and `..._b.ttl`, canonicalize each, serialize to Turtle, assert byte-equal.

**Blank node canonicalization:**
- [ ] `test_blank_node_labels_stable_across_runs` — canonicalize twice, blank-node label set is identical both times.
- [ ] `test_blank_node_labels_content_addressed` — the same logical blank node in two ontologies gets the same label.

**Restriction reification:**
- [ ] `test_simple_restriction_gets_urn_iri` — `:Track rdfs:subClassOf <urn:owlcompare:restriction:...>` after reification.
- [ ] `test_same_restriction_same_urn_across_ontologies` — same `(someValuesFrom, onProperty, filler)` in two ontologies produces the same URN.
- [ ] `test_distinct_restrictions_distinct_urns`
- [ ] `test_nested_restriction_reified_recursively`
- [ ] `test_self_referential_restriction_does_not_recurse_infinitely`

**List collapsing:**
- [ ] `test_list_collapse_produces_single_urn` — the list becomes one `urn:owlcompare:list:...` IRI.
- [ ] `test_list_order_preserved` — different element orders produce different list URNs.
- [ ] `test_malformed_list_warns_does_not_raise` — log capture at INFO shows warning; no exception.

**Triple sorting:**
- [ ] `test_triple_sorting_produces_deterministic_serialization` — serialize to N-Triples twice; output is byte-identical.

**Options:**
- [ ] `test_disable_blank_node_pass_preserves_original_labels`
- [ ] `test_disable_reify_restrictions_leaves_blank_nodes`
- [ ] `test_disable_collapse_lists_preserves_list_triples`
- [ ] `test_disable_sort_still_correct_just_undeterministic` — disable sort, canonical form may differ run-to-run but other invariants hold.

**Errors:**
- [ ] `test_named_graph_input_raises_canonicalization_error`
- [ ] `test_canonicalization_error_exit_code_is_4`

**CLI:**
- [ ] `test_cli_canonicalize_help_lists_options`
- [ ] `test_cli_canonicalize_missing_source_exits_2`
- [ ] `test_cli_canonicalize_minimal_fixture_exits_0_prints_turtle`
- [ ] `test_cli_canonicalize_output_format_nt_exits_0_prints_ntriples`
- [ ] `test_cli_canonicalize_writes_to_out_file`
- [ ] `test_cli_canonicalize_no_blank_nodes_flag_propagates`
- [ ] `test_cli_canonicalize_named_graph_input_exits_4`

**Integration:**
- [ ] `test_load_canonicalize_roundtrip_preserves_entity_count` — entity counts on the canonical snapshot match those on the loaded snapshot (canonicalization doesn't add or remove named entities).

## Out of scope

- Imports closure resolution.
- Removing entailed triples (no reasoning).
- N-Quads / named graphs (raise instead).
- Whitespace normalization in literal values (semantically meaningful).
- Datatype value normalization (e.g., `"1"^^xsd:integer` vs `"+1"^^xsd:integer`) — deferred; would need a separate datatype-aware pass.
- Optimizing RDFC-1.0 performance — out-of-the-box rdflib implementation is acceptable for v1.

## Known limitations

- Library callers who use `load()` to parse a TriG/N-Quads file silently lose the named-graph information (the loader merges into the default graph). Such snapshots, if passed to `canonicalize()`, will not raise. The CLI command catches this by re-parsing the source as a Dataset. Full quad-graph awareness is a v2 feature; tracked in `docs/ROADMAP.md` under Backlog as "Quad-graph aware loader (resolves Component 04 known limitation)".

## Open questions

- [ ] **Q1:** Should the restriction reification URN namespace be `urn:owlcompare:restriction:<hash>` or `https://owlcompare.dev/canonical/restriction/<hash>`?
  **Proposed:** `urn:` form. URNs are clearly synthetic, don't pretend to be resolvable HTTP IRIs, and won't accidentally appear to be "real" addresses if a user pastes the canonical form into a browser.

- [ ] **Q2:** When reifying a restriction whose content depends on another (yet-unreified) restriction, what order are passes applied?
  **Proposed:** Reify bottom-up via recursion within `_reify_restrictions`. The pass computes hashes for innermost restrictions first (no nested anonymous structures), then for restrictions one level up, etc. This is naturally handled by recursion if implemented correctly.

- [ ] **Q3:** Should `canonicalize()` accept a non-canonical snapshot only, or be idempotent on canonical ones?
  **Proposed:** Idempotent. If `snapshot.canonical` is already True, run the passes anyway (their output on canonical input is deterministic and matches the input). A short-circuit "return as-is" is a footgun if a future change weakens canonical-form invariants.

If you have a preference, override before implementing; otherwise proceed with the proposed answers.

## References

- `docs/ARCHITECTURE.md` § Loader (note that canonicalization is mentioned in DD-007 as deferred from the loader)
- `docs/DESIGN_DECISIONS.md` § DD-007 (canonicalize before diffing)
- W3C RDF Dataset Canonicalization (RDFC-1.0): https://www.w3.org/TR/rdf-canon/
- rdflib `to_canonical_graph`: https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.html#rdflib.compare.to_canonical_graph
