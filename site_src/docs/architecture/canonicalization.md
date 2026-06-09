# Canonicalization

Before owlcompare compares anything, it **canonicalizes** both ontologies into a
normalized form. Without this step, every diff would be dominated by spurious
blank-node relabeling and triple-reordering noise. This page will document each
normalization stage and why it matters. You can inspect the output of this stage
directly with [`owlcompare canonicalize`](../reference/cli.md#owlcompare-canonicalize).

!!! info "This page is being expanded"
    The outline below anchors the scope; the full per-stage detail is coming.

## What this page will cover

- **Why canonicalize at all** — making two semantically-equal inputs produce
  byte-identical output, so the diff reflects meaning, not serialization.
- **Blank-node normalization** — stable, content-based labels (RDFC-1.0), so
  anonymous nodes stop generating phantom changes.
- **Restriction reification** — giving anonymous `owl:Restriction` structures
  deterministic identifiers so they can be compared.
- **RDF-list collapsing** — turning `rdf:first`/`rdf:rest` chains into ordered
  lists.
- **Triple sorting** — removing order sensitivity where order is semantically
  irrelevant.
- **Anonymous-structure decoding** — `owl:unionOf` / `owl:intersectionOf` sets,
  datatype facet restrictions, and `dcterms:isReplacedBy`, decoded into
  structured changes instead of raw blank-node noise.
- **The `--no-*` flags** — disabling individual stages for debugging.
- **Known limitations** — named graphs and quad sources in v1.
