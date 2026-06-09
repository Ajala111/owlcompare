# Rename detection internals

This page will document how owlcompare's rename detector actually works: the
matching algorithm across the three confidence tiers, how it consolidates a
rename plus its cascade of reference updates into a single event, and how
genuinely-new structure on a renamed entity still surfaces. For the user-facing
version, see the [rename detection guide](../guides/rename-detection.md).

!!! info "This page is being expanded"
    The outline below is in place; the full algorithm walkthrough is coming.

## What this page will cover

- **The three tiers and how each match is made:**
    - **certain** — user-asserted mappings.
    - **high** — shared `rdfs:label` matching.
    - **medium** — structural fingerprint (shared parents, restrictions,
      domain/range) when labels don't align.
- **Where detection runs** in the pipeline — between the Layer 1 slices and the
  severity classifier.
- **Cascade consolidation** — pairing the renamed entity's add/remove and
  absorbing the pure IRI-substitution references that follow from it.
- **The post-rename re-diff** — surfacing structural additions on a renamed entity
  as independent changes, so a rename-plus-new-constraint shows both facts.
- **Confidence and honesty** — why owlcompare reports a confidence level instead
  of pretending to certainty.
- **Known limitations** carried into v1 and what's deferred.
