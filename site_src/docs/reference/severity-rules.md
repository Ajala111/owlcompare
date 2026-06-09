# Severity rules

owlcompare assigns every change one of four severities — `breaking`,
`non_breaking`, `additive`, `info` — and then applies a small set of
**cross-cutting refinement rules** that adjust a severity using context no single
diff slice can see. This page documents those built-in rules and the override
format. For the conceptual introduction, see
[Understanding the output](../getting-started/understanding-output.md); for a
task-focused walkthrough, see the
[severity overrides guide](../guides/severity-overrides.md).

!!! info "This page is being expanded"
    The outline below is in place; the full per-rule documentation is coming.

## The four severities

| Severity | Meaning |
|----------|---------|
| `breaking`{ data-severity="breaking" } | Downstream consumers may fail. |
| `non_breaking`{ data-severity="non-breaking" } | Semantics changed, valid usage still works. |
| `additive`{ data-severity="additive" } | A pure addition. |
| `info`{ data-severity="info" } | Editorial / metadata. |

## What this page will cover

- **The six built-in refinement rules**, in order, each with its trigger and
  rationale:
    1. User overrides (always win).
    2. Annotation change on a deprecated entity → `info`.
    3. Restriction removal consequent to a property removal → `info`.
    4. Late-detected domain/range widening → `non_breaking`.
    5. Reparent with a new restriction → `breaking`.
    6. Subsumed Layer 0 change → `info`.
- **The override file format** — `kind_pattern`, `subject_pattern`, `layer`,
  `severity`, with glob semantics and `schema_version`.
- **The severity → color/label mapping** shared with the HTML and Markdown
  reports.
- **The refinement audit trail** recorded in the JSON `metadata`.
