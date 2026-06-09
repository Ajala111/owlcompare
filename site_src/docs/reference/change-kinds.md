# Change kinds

Every event owlcompare emits carries a `kind` — a stable string like
`class_added`, `restriction_changed`, or `object_property_removed` — that
identifies exactly what changed. This page will be the exhaustive catalog of every
kind, grouped by layer and pattern, with the slice that emits it and the JSON
`details` it carries. New kinds are forward-compatible with the
[JSON schema](json-schema.md) (it deliberately does not constrain `kind` to an
enum), so this catalog grows without a schema bump.

!!! info "This page is being expanded"
    The outline below anchors the structure; the full per-kind table is coming.

## What this page will cover

- **Layer 0 — syntactic** — `triple_added`, `triple_removed`.
- **Entities** — `class_added` / `class_removed`, the property variants, and
  `entity_deprecated`.
- **Hierarchy** — `class_parent_added` / `_removed`, `class_reparented`, and the
  property-hierarchy equivalents.
- **Restrictions** — cardinality, `someValuesFrom` / `allValuesFrom` / `hasValue`,
  and `domain_*` / `range_*` add / remove / change variants.
- **Annotations** — `annotation_added` / `_removed` / `_changed`,
  `label_changed`, and `ontology_metadata_changed`.
- **Class sets** — the `*_union_*` and `datatype_facet_*` decoded-structure
  kinds, plus `replaced_by_*`.
- **Renames** — the consolidated `*_renamed` kinds.
- For each: the **layer**, the **default severity**, the **emitting slice**, and
  the **`details` payload** shape.
