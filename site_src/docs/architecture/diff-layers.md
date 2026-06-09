# Diff layers

owlcompare analyzes a change at four increasing levels of meaning. This page will
document each layer in detail — what it detects, how it's implemented, and how the
layers cooperate so that a higher layer's events *subsume* the lower-layer triples
that caused them. It draws on the internal slice specs but is rewritten for
comprehension rather than implementation. The
[overview](overview.md) places these layers in the full pipeline.

!!! info "This page is being expanded"
    The outline below anchors the scope; the per-layer detail is coming.

## What this page will cover

- **Layer 0 — Syntactic.** The raw triple delta. Always computed, hidden when a
  higher layer explains it. The `--show-syntactic` escape hatch.
- **Layer 1 — Structural.** The four slices:
    - **Entities** — classes and properties added, removed, deprecated.
    - **Hierarchy** — `subClassOf` / `subPropertyOf` edges and reparenting.
    - **Restrictions** — cardinality, value restrictions, domain/range.
    - **Annotations** — labels, comments, metadata.
- **Subsumption** — how a Layer 1 event claims the Layer 0 triples behind it, and
  how the subsumption registry is recorded.
- **Layer 2 — Inferential (planned).** Diffing entailed facts with a reasoner.
- **Layer 3 — Impact (planned).** SHACL-shape and SPARQL-query impact analysis.
- **Why v1 ships 0 and 1 only** — the deliberate scoping decision.
