# Architecture overview

This section is for the curious and for contributors: how owlcompare actually
turns two files into a diff. This overview page will sketch the whole pipeline at
a glance and link to the deeper per-topic pages. For the user-facing version of
these ideas, see
[Understanding the output](../getting-started/understanding-output.md).

!!! info "This page is being expanded"
    The outline below is in place; the full narrative and pipeline diagram are
    coming.

## What this page will cover

- **The pipeline, end to end** — load → canonicalize → Layer 0 diff → Layer 1
  slices → rename detection → severity refinement → render.
- **The four-layer model** — what each layer answers and why they're separated.
- **Canonicalization** — why both inputs are normalized before anything is
  compared (see [Canonicalization](canonicalization.md)).
- **The internal model** — frozen dataclasses (`OntologySnapshot`, `Entity`,
  `Change`) rather than raw `rdflib` objects, and why.
- **The orchestrator** — how the slices are sequenced and how subsumption keeps
  the raw triple noise out of the final report.
- **Severity post-processing** — the cross-cutting refinement pass that runs last.
- **The component breakdown** — how the codebase maps onto the spec-driven
  components.
