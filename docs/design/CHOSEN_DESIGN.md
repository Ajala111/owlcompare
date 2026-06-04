# Chosen Design

**Chosen: Wireframe A — Card-based.**

## Why A

The five user stories are not equally common. Story 1 (reviewer skim) and story 4
(CI debugger) are the everyday path; story 2 (deep-dive) is occasional; story 3
(historian) is rare; story 5 (architect's audit) is rarest and explicitly only
single-report-scoped in v1. The right design optimises for the common path while
keeping the others *acceptable*.

A serves the two common stories best:

- **Story 1** is served well: the breaking section is open by default, each
  breaking card carries a red left stripe plus a text badge, so "is this safe?"
  is answerable in a glance without scanning a uniform grid (B's weakness) or
  reading prose (which is fine for one change but not for triage at volume).
- **Story 4** is served best of all three: the severity-refinement "why breaking"
  block lives *inside the card it explains*. Neither B (cross-referencing a row)
  nor C (a footnote) keeps cause and effect as physically adjacent.

A serves the rest acceptably:

- **Story 3 (historian)** is served well: renames lead, with an `EvidenceList`
  per rename. C would serve it slightly better as pure narrative, but A is close
  and far more robust at volume.
- **Story 2 (deep-dive)** is served *acceptably, not ideally*: there is no column
  sort, so the reader leans on `Ctrl-F` and per-card expansion. This is the
  honest cost of not choosing B. It is mitigated by the v1.1 filter sidebar (Q2),
  which the IA already reserves space for.
- **Story 5 (architect's audit)** is served *poorly*: cards give no tabular
  density for eyeballing recurring kinds. We accept this because it is the least
  common workflow and v1 does no cross-report aggregation regardless.

## Why not B or C

- **B (table)** wins stories 2 and 5 but loses the two stories that matter most:
  a breaking row is too easy to miss in a uniform grid, and it is the costliest
  to build (column sort + inline expansion + a filter toolbar that drags the
  deferred v1.1 sidebar into v1). Optimising for the audit at the expense of the
  skim is the wrong trade for a PR-review tool.
- **C (narrative)** wins story 1 for a *handful* of changes and wins story 3, but
  collapses on real diffs of dozens-to-hundreds of changes, and its per-kind
  English templating is the most brittle against forward-compat unknown kinds.
  We borrow its best idea — readable restriction/annotation phrasing — into A's
  card bodies without betting the whole report on prose.

## Honest summary

A is the balanced middle, deliberately. It is not the best possible design for
any single story, but it is the best *aggregate* across the realistic frequency
of the five, and the cheapest of the three to ship self-contained. The close call
was C for its first impression; A wins because it scales and because story 4's
in-place "why" is worth more than C's prose polish. This wireframe is the spec
input for Component 17.
