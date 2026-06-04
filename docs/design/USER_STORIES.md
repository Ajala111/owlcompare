# User Stories

Five named workflows the HTML report must serve, ordered by frequency. Each has a
persona, goal, entry point, navigation path, success outcome, and — most
importantly — a **design implication**: the structural thing the page must do to
make the story work. The Information Architecture is answerable to this list; if a
story implies a navigation pattern the IA lacks, one of the two is wrong.

## Story 1 — The reviewer skim *(most common)*

- **Persona:** Senior ontology engineer reviewing a colleague's PR.
- **Goal:** Decide in ~30 seconds whether the change is safe to approve.
- **Entry:** Opens `report.html` attached to the PR.
- **Path:** Status badge → breaking section → approve or comment.
- **Success:** Breaking changes understood within 30 s; no breaking changes
  recognised within 5 s.
- **Design implication:** The breaking count and the breaking changes themselves
  must be *above the fold* with zero interaction. A green "no breaking changes"
  state must be unmistakable at a glance.

## Story 2 — The integrator deep-dive

- **Persona:** Data engineer whose SHACL pipeline broke after a version bump.
- **Goal:** Find every change touching the properties they consume.
- **Entry:** Opens the file, knows the property IRIs.
- **Path:** `Ctrl-F` the property IRI → expand each matching change → read full
  `before`/`after`.
- **Success:** Every relevant change found; no false sense of completeness.
- **Design implication:** Every IRI is selectable plain text (not an image, not a
  pseudo-element) so browser find works. Each change must be individually
  expandable to its full detail without expanding everything.

## Story 3 — The historian

- **Persona:** New team member learning the ontology from its history.
- **Goal:** Understand each version's *intent*, not just its mechanics.
- **Entry:** Opens archived `report.html` files one by one.
- **Path:** Read the title → read the renames section → expand the structural
  changes as a narrative.
- **Success:** Can describe in a sentence what each version set out to do.
- **Design implication:** Renames lead, because a rename is the most
  intent-revealing pattern. The report must read top-to-bottom as a coherent
  story even years later, offline, with no server.

## Story 4 — The CI debugger

- **Persona:** Developer whose CI failed on a breaking-change exit code.
- **Goal:** Identify the single change that tripped the build, and why.
- **Entry:** Clicks the report link from the CI log.
- **Path:** Status badge → breaking section → expand the offending change → read
  the severity-refinement "why."
- **Success:** Can point at one change and quote the rule that made it breaking.
- **Design implication:** The severity-refinement audit trail
  (`metadata.severity_refinements`) must attach to its change, in place, as a
  "why this is breaking: *rationale* (rule X)" note — not live in a separate
  table the reader has to cross-reference by `change_id`.

## Story 5 — The architect's audit *(least common)*

- **Persona:** Ontology lead reviewing six months of evolution for patterns.
- **Goal:** Aggregate insight ("are we narrowing cardinalities too aggressively?").
- **Entry:** Opens several reports across versions.
- **Path:** Summary counts → scan severity groups → eyeball recurring kinds.
- **Success:** Spots a trend across reports.
- **Design implication:** The summary strip must expose counts by severity at a
  glance. True cross-report aggregation is **out of scope for v1** — each report
  is one version pair — so this story is served only at the single-report level.
  Accepted as the rarest workflow.
