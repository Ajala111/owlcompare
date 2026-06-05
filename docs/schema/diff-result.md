# The `owlcompare diff` JSON output

This is the human-readable companion to
[`diff-result.schema.json`](./diff-result.schema.json), the formal JSON Schema
(2020-12) that every `owlcompare diff --format json` payload conforms to. The
schema is the machine-checkable source of truth; this document explains it in
prose and shows the shapes you actually need to read. When the two disagree, the
schema wins — but they are kept in lockstep (see
[DD-019](../DESIGN_DECISIONS.md#dd-019-json-schema-compatibility-policy)).

The output is **versioned**. `schema_version` is currently `1`. Forward-compatible
changes (a new optional field, a new `kind`) do not bump it; breaking changes do.
The compatibility rules are in DD-019.

```bash
owlcompare diff a.ttl b.ttl --format json            # emit the payload
owlcompare diff a.ttl b.ttl --format json --validate-schema   # validate before emitting (exit 5 on failure)
```

---

## Top-level shape

```jsonc
{
  "schema_version": 1,   // integer, always 1 in v1
  "summary": { ... },    // headline counts
  "changes": [ ... ],    // every change, every layer (may be empty)
  "metadata": { ... }    // producer-side context (optional, but always present today)
}
```

**`schema_version`** — the contract version. Pin your tooling to it; refuse a
version you do not understand.

**`summary`** — four integers. `added` and `removed` count Layer 0 *triples*
(added / removed); `total` is the number of entries in `changes`; `breaking` is
how many of those changes have `severity: "breaking"`. The object is strict —
exactly these four keys.

**`changes`** — the array of [Change](#the-change-object) objects, in
deterministic order. An empty array is valid and means the two ontologies are
identical after canonicalization.

**`metadata`** — producer-side context. Unlike everything else, `metadata` is
**permissive**: tooling may add keys here without a schema bump, so consumers
should ignore keys they do not recognize. The only key emitted today is
`severity_refinements` (see [below](#severity-refinements)); `layer_counts`,
`subsumption_registry`, `rename_candidates` and `renames_applied` are reserved
shapes the schema knows about but the CLI does not currently serialize.

---

## The `Change` object

Every entry in `changes` has the same eight required fields:

```jsonc
{
  "layer": "syntactic" | "structural",
  "kind": "triple_added",        // string; NOT an enum — new kinds may appear
  "severity": "breaking" | "non_breaking" | "additive" | "info",
  "subject": "http://…" | null,  // the affected entity IRI, when there is one
  "summary": "Added: …",         // one-line human description
  "details": { … },              // per-kind; see below
  "before": null,                // reserved; currently always null
  "after":  null                 // reserved; currently always null
}
```

A few things worth internalizing:

- **`kind` is intentionally open.** The schema does not enumerate it, so a future
  owlcompare can introduce a new `kind` without breaking you. Switch on the kinds
  you handle and fall back gracefully on the rest.
- **`before` / `after` are reserved.** They are part of the contract as nullable
  fields, but the diff layers currently carry their before/after payloads *inside
  `details`* (e.g. a restriction's old and new cardinality), so the top-level
  pair is always `null` today. Do not rely on them; read `details`.
- **`details` is where the per-kind information lives**, and its shape is pinned
  per `kind`. For every well-known kind the schema applies a strict object
  (`additionalProperties: false`) via an `allOf` + `if`/`then` branch on `kind`.
  For an unknown kind no branch matches and `details` is validated only as a
  generic object — that is exactly what makes new kinds forward-compatible.

Every structural `details` object carries two bookkeeping fields:

- **`change_id`** — a stable id of the form `"<layer>:<kind>:<sha1>"`, computed
  from the change's intrinsic content. Use it to cross-reference.
- **`subsumes`** — a list of the `change_id`s of the lower-level (Layer 0)
  changes this structural change explains. Renderers fold those away so the diff
  reads semantically instead of as raw triples. (Layer 0 `triple_*` changes have
  no `subsumes` — they are the base.) The ids are unique by construction; the
  schema does not enforce uniqueness.

---

## Details by kind

The kinds below are everything owlcompare emits today. Grouped by the layer /
component that produces them.

### Layer 0 — syntactic (Component 05)

`triple_added`, `triple_removed` — one raw triple changed. No `subsumes`.

```jsonc
"details": {
  "subject": "ex:Dog",                 // n3 form (may be a prefixed name, bnode, or literal)
  "predicate": "rdfs:label",
  "object": "\"Dog\"@en",
  "subject_iri": "http://example.org/Dog" | null,   // null when the subject is not an IRI
  "predicate_iri": "http://…#label" | null,
  "change_id": "syntactic:triple_added:…"
}
```

### Layer 1 — entities (Component 06)

`class_added`/`class_removed`, `object_property_*`, `data_property_*`,
`annotation_property_*`, `individual_*`, `datatype_*`:

```jsonc
"details": {
  "entity_iri": "http://…",
  "entity_kind": "class",     // one of the six entity kinds
  "label": "Dog" | null,      // best label; null if the entity has none
  "language": "en" | null,    // language tag of that label
  "subsumes": [ … ],
  "change_id": "…"
}
```

`entity_kind_changed` — an IRI that moved from one entity kind to another (e.g.
class → datatype):

```jsonc
"details": { "entity_iri": "…", "from_kind": "class", "to_kind": "datatype", "subsumes": [ … ], "change_id": "…" }
```

### Layer 1 — hierarchy (Component 07)

`class_parent_added`/`class_parent_removed`, `property_parent_added`/`property_parent_removed`:

```jsonc
"details": { "entity_iri": "…", "entity_kind": "class", "parent_iri": "…", "subsumes": [ … ], "change_id": "…" }
```

> Note: `entity_kind` here is the coarse `"class"` / `"property"` axis, not the
> six-way entity kind used by the entity-level changes above. The schema leaves
> it as a plain string for this reason.

`class_reparented`, `property_reparented` — a simultaneous parent gain *and* loss,
with a direction hint:

```jsonc
"details": {
  "entity_iri": "…",
  "entity_kind": "class",
  "parents_before": [ "…", "…" ],
  "parents_after":  [ "…" ],
  "direction": "generalization" | "specialization" | "lateral",
  "subsumes": [ … ],
  "change_id": "…"
}
```

`class_hierarchy_cycle_introduced` — a `subClassOf` cycle that a new edge closed.
One change is emitted per entity on the cycle; they share the same `path`:

```jsonc
"details": { "entity_iri": "…", "path": [ "ex:C", "ex:A", "ex:B", "ex:C" ], "subsumes": [ … ], "change_id": "…" }
```

### Layer 1 — restrictions and class axioms (Component 08)

`restriction_added`, `restriction_removed`, `restriction_changed` — see the
[worked example](#example-restriction_changed) below:

```jsonc
"details": {
  "entity_iri": "…",
  "via_predicate": "rdfs:subClassOf" | "owl:equivalentClass",
  "on_property": "http://…/hasMaxSpeed" | null,
  "before": { "kind": "max_cardinality", "cardinality": 5, "filler": null, "urn": "urn:owlcompare:restriction:…" } | null,
  "after":  { … } | null,
  "subsumes": [ … ],
  "change_id": "…"
}
```

The `before` / `after` objects are the *decoded restriction*: `kind` (the
restriction flavour, e.g. `max_cardinality`, `some_values_from`), `cardinality`
(integer or null), `filler` (the IRI/URN it points at, or null), and `urn` (the
synthetic id minted by canonicalization). On an add, `before` is null; on a
remove, `after` is null.

`domain_changed`, `range_changed` — a single-value domain/range *swap*:

```jsonc
"details": { "property_iri": "…", "before": "…", "after": "…", "subsumes": [ … ], "change_id": "…" }
```

`domain_added`, `domain_removed`, `range_added`, `range_removed` — one
domain/range value added or removed when the property has several. Note this uses
`value`, **not** `before`/`after`:

```jsonc
"details": { "property_iri": "…", "value": "…", "subsumes": [ … ], "change_id": "…" }
```

`equivalent_class_added`/`equivalent_class_removed`, `disjoint_added`/`disjoint_removed`:

```jsonc
"details": { "entity_iri": "…", "other_iri": "…", "subsumes": [ … ], "change_id": "…" }
```

`complement_set`, `complement_unset` — an `owl:complementOf` target set or cleared:

```jsonc
"details": { "entity_iri": "…", "before": "…" | null, "after": "…" | null, "subsumes": [ … ], "change_id": "…" }
```

`complex_class_expression_changed` — the opaque fallback for a nested or malformed
class expression whose structured diff is deferred to v2:

```jsonc
"details": { "entity_iri": "…", "depth": 3, "note": "Deep class expression change; structured diff deferred to v2.", "subsumes": [ … ], "change_id": "…" }
```

### Layer 1 — annotations (Component 09)

`annotation_changed` — a single-value swap. `before` / `after` are **objects**:

```jsonc
"details": {
  "entity_iri": "…",
  "predicate_iri": "http://…#label",
  "predicate_short": "label",
  "language": "fr" | null,
  "before": { "value": "Voie",       "is_iri_value": false },
  "after":  { "value": "Voie ferrée", "is_iri_value": false },
  "subsumes": [ … ],
  "change_id": "…"
}
```

`annotation_added`, `annotation_removed` — one value added or removed. Here the
value is **flat** (`value` + `is_iri_value`), not nested:

```jsonc
"details": {
  "entity_iri": "…",
  "predicate_iri": "…",
  "predicate_short": "label",
  "language": "fr" | null,
  "value": "Signalisation",
  "is_iri_value": false,
  "subsumes": [ … ],
  "change_id": "…"
}
```

> The asymmetry — nested `{value, is_iri_value}` for `annotation_changed`, flat
> for add/remove — mirrors the data: a change has two values, an add/remove has
> one. `is_iri_value` says whether `value` is an IRI (a resource-valued
> annotation) rather than a literal.

`entity_deprecated`, `entity_undeprecated` — an `owl:deprecated true` flip:

```jsonc
"details": { "entity_iri": "…", "subsumes": [ … ], "change_id": "…" }
```

`ontology_metadata_changed` — an annotation edit on the `owl:Ontology` subject
itself. Like `annotation_changed` it nests `before`/`after`, but they may be null
(value added or removed) and the subject key is `ontology_iri`:

```jsonc
"details": {
  "ontology_iri": "…",
  "predicate_iri": "…",
  "predicate_short": "versionInfo",
  "language": null,
  "before": { "value": "1.0", "is_iri_value": false } | null,
  "after":  { "value": "1.1", "is_iri_value": false } | null,
  "subsumes": [ … ],
  "change_id": "…"
}
```

### Renames (Components 11/12)

`class_renamed`, `object_property_renamed`, `data_property_renamed`,
`annotation_property_renamed` — a removed entity and an added entity recognized as
the *same* entity under a new IRI, consolidated into one change. See the
[worked example](#example-class_renamed) below:

```jsonc
"details": {
  "before_iri": "http://…/Signal",
  "after_iri":  "http://…/RailwaySignal",
  "entity_kind": "class",        // one of the four renameable kinds
  "confidence": "certain" | "high" | "medium" | "low",
  "score": 1.0,                  // 0.0–1.0 fingerprint match score
  "evidence": [ "matching label \"Signal\"@en" ],
  "cascade_subsumes": [ … ],     // change_ids of cascade consequences absorbed
  "subsumes": [ … ],             // change_ids of the paired add + remove
  "change_id": "…"
}
```

`subsumes` holds the two `change_id`s of the `*_removed` and `*_added` changes
this rename replaced. `cascade_subsumes` holds the ids of *consequence* changes —
a `subClassOf` edge that merely re-pointed at the new IRI, a restriction whose
filler was substituted, or (since Component 12) a genuinely new axiom on the
renamed entity that was re-diffed out and surfaced as its own change.

### Anonymous class sets (Component 12.5)

`domain_union_added` / `_removed` / `_changed`, and the `range_union_*`,
`subclass_union_*`, `equivalent_class_union_*` analogues — a member was added to
or removed from an anonymous `owl:unionOf` / `owl:intersectionOf` set attached via
`rdfs:domain` / `rdfs:range` / `rdfs:subClassOf` / `owl:equivalentClass`. One
change per `(entity, predicate)`; `shape_change` records the union↔bare reshape
(a single-member union normalizes to a bare class). `operator` distinguishes
union from intersection — for an intersection the add/remove severities invert
(adding narrows → breaking; removing broadens → non_breaking).

```jsonc
"details": {
  "entity_iri": "http://…/axleSpacingDistance",
  "via_predicate": "rdfs:domain",         // one of the four attachment predicates
  "operator": "unionOf" | "intersectionOf",
  "members_before": [ … ], "members_after": [ … ],
  "added_members": [ … ], "removed_members": [ … ],
  "shape_change": "stable" | "flattened" | "unflattened",
  "subsumes": [ … ], "change_id": "…"
}
```

### Datatype facets (Component 12.5)

`datatype_facet_added` / `_removed` / `_changed`, and `datatype_base_changed` — a
change to an `owl:onDatatype` + `owl:withRestrictions` facet restriction on a data
property's range. `base_before` / `base_after` are the base datatype IRIs (one is
`null` on a one-sided facet add/remove); `facets_*` map facet names
(`min_inclusive`, `max_inclusive`, `pattern`, …) to numeric or string values.

```jsonc
"details": {
  "property_iri": "http://…/dNvovtrp",
  "base_before": "http://…/decimal", "base_after": "http://…/decimal",
  "facets_before": { "min_inclusive": 0, "max_inclusive": 327670 },
  "facets_after":  { "min_inclusive": 0, "max_inclusive": 100000 },
  "changed_facets": [ "max_inclusive" ],
  "subsumes": [ … ], "change_id": "…"
}
```

### Soft deprecation (Component 12.5)

`replaced_by_set` / `replaced_by_unset` — a curator's `dcterms:isReplacedBy`
assertion was added (non_breaking) or withdrawn (info). `matches_detected_rename`
flags consistency with an accepted rename; `target_existed_in_b` records whether
the replacement IRI exists in the new snapshot.

```jsonc
"details": {
  "entity_iri": "http://…/TSIMagneticFields",
  "target_iri": "http://…/tsiMagneticFields",
  "matches_detected_rename": true,
  "target_existed_in_b": true,
  "subsumes": [ … ], "change_id": "…"
}
```

---

## `severity_refinements`

`metadata.severity_refinements` is the audit trail of the severity classifier
(Component 10): each entry records a change whose severity was *refined* from the
value its producing layer assigned, and why.

```jsonc
{
  "change_id": "syntactic:triple_removed:…",
  "original_severity": "breaking",
  "refined_severity": "info",
  "rule_id": "user-override",          // e.g. "subsumed-layer0-info", "user-override"
  "rationale": "matched pattern '*'"
}
```

The array is always present (possibly empty). Each entry is strict — exactly
these five keys.

---

## Worked examples

### Example: `restriction_changed`

`era:Track` tightened a max-cardinality restriction on `era:hasMaxSpeed` from 5 to
3. The three-or-four reified Layer 0 triples collapse into one structural change;
the `before`/`after` carry the decoded restrictions, and `subsumes` lists the raw
triples folded away.

```jsonc
{
  "layer": "structural",
  "kind": "restriction_changed",
  "severity": "breaking",
  "subject": "http://data.europa.eu/949/Track",
  "summary": "Restriction changed on era:Track: era:hasMaxSpeed max 5 → max 3",
  "details": {
    "entity_iri": "http://data.europa.eu/949/Track",
    "via_predicate": "rdfs:subClassOf",
    "on_property": "http://data.europa.eu/949/hasMaxSpeed",
    "before": { "kind": "max_cardinality", "cardinality": 5, "filler": null, "urn": "urn:owlcompare:restriction:7d3b…" },
    "after":  { "kind": "max_cardinality", "cardinality": 3, "filler": null, "urn": "urn:owlcompare:restriction:1f72…" },
    "subsumes": [ "syntactic:triple_removed:…", "syntactic:triple_added:…" ],
    "change_id": "structural:restriction_changed:…"
  },
  "before": null,
  "after": null
}
```

To render "max 5 → max 3", read `details.before.cardinality` and
`details.after.cardinality`; do **not** look at the top-level `before`/`after`,
which are null.

### Example: `class_renamed`

`era:Signal` was renamed to `era:RailwaySignal`. Rename detection paired the
`class_removed` and `class_added` (listed in `subsumes`) and absorbed a
consequence change — here a French-label removal on the renamed class — into
`cascade_subsumes`. The whole rename reads as one `info`-severity row.

```jsonc
{
  "layer": "structural",
  "kind": "class_renamed",
  "severity": "info",
  "subject": "http://data.europa.eu/949/RailwaySignal",
  "summary": "Class renamed: era:Signal → era:RailwaySignal (high confidence; matching label \"Signal\"@en)",
  "details": {
    "before_iri": "http://data.europa.eu/949/Signal",
    "after_iri": "http://data.europa.eu/949/RailwaySignal",
    "entity_kind": "class",
    "confidence": "high",
    "score": 1.0,
    "evidence": [ "matching label \"Signal\"@en" ],
    "cascade_subsumes": [ "structural:annotation_removed:…" ],
    "subsumes": [ "structural:class_removed:…", "structural:class_added:…" ],
    "change_id": "structural:class_renamed:…"
  },
  "before": null,
  "after": null
}
```

A change whose `change_id` appears in some rename's `cascade_subsumes` (the label
removal above) still appears in `changes` in its own right when Component 12
re-diffed it as a genuine new fact; pure IRI-substitution consequences are folded
away entirely. Either way, `cascade_subsumes` is the audit link back to the
rename that explains it.

---

## Validating output yourself

The schema ships inside the installed package and is reachable from Python:

```python
from owlcompare.schema import load_schema, validate_diff_json

schema = load_schema()                 # the parsed JSON Schema dict
validate_diff_json(some_payload)       # raises SchemaValidationError (exit code 5) on failure
```

`validate_diff_json` uses [`jsonschema`](https://python-jsonschema.readthedocs.io/),
which owlcompare carries as a **test-only** dependency (DD-020) — so calling the
validator requires the dev extras, while `load_schema()` works with the standard
library alone. External tools in any language can consume the schema file
directly from the repository.
