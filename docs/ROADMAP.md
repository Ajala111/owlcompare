# Roadmap

This is the source of truth for what's done, what's in progress, and what's deferred.

**Current phase:** Phase 4 IN PROGRESS — Report renderers, **4 of 5 components done**. Components 14 (JSON Schema Lockdown), 15 (Markdown report), 16 (HTML report — design & wireframe), and **17 (HTML report — implementation)** delivered. Component 17 is the project's **headline visual deliverable** — `owlcompare diff … --format html` now emits a beautiful, self-contained, offline-viewable report. Only Component 18 (JUnit XML / CI output) remains in this phase.

---

## Phase 0 — Foundation

- [x] Project brief written (`docs/PROJECT_BRIEF.md`)
- [x] Architecture documented (`docs/ARCHITECTURE.md`)
- [x] Design decisions logged (`docs/DESIGN_DECISIONS.md`)
- [x] Conventions defined (`docs/CONVENTIONS.md`)
- [x] Glossary established (`docs/GLOSSARY.md`)
- [x] Repo initialized with `uv init`
- [x] `pyproject.toml` configured (ruff, mypy, pytest)
- [x] CI workflow (`.github/workflows/ci.yml`)
- [x] LICENSE (MIT)
- [x] README.md (placeholder, expanded later)

**Exit criteria:** A new contributor can clone the repo, run `uv sync && uv run pytest`, and get a green build (with zero tests).

---

## Phase 1 — Core skeleton

- [x] Component 01: CLI scaffold (`owlcompare --help` works, no real commands yet) — `specs/01-cli.md`
- [x] Component 02: Ontology loader + internal model — `specs/02-loader.md`
      (Component 03 was folded into 02 per the spec; the loader returns a fully-typed `OntologySnapshot`.)
- [x] Component 04: Canonicalization — `specs/04-canonicalize.md`

**Phase 1 complete.** `owlcompare load a.ttl` summarizes an ontology; `owlcompare canonicalize a.ttl` emits a normalized form where two equivalent inputs produce byte-identical output.

---

## Phase 2 — Syntactic and structural diff ✅ COMPLETE

- [x] Component 05: Layer 0 syntactic diff — `specs/05-syntactic-diff.md`
- [x] Component 06: Layer 1 structural diff (entities) — `specs/06-structural-entities.md`
- [x] Component 07: Layer 1 structural diff (hierarchy) — `specs/07-structural-hierarchy.md`
- [x] Component 08: Layer 1 structural diff (restrictions) — `specs/08-structural-restrictions.md`
- [x] Component 09: Layer 1 structural diff (annotations) — `specs/09-structural-annotations.md`
- [x] Component 10: Severity classification — `specs/10-severity.md`

**Phase 2 is COMPLETE.** Components 06–09 cover entities, hierarchy,
restrictions and annotations; Component 10 adds the cross-cutting severity
classifier (six built-in rules + TOML user overrides) that runs last in the
orchestrator pipeline and records its audit trail in
`metadata.severity_refinements`.

**Exit criteria (met):** `owlcompare diff a.ttl b.ttl --format json` produces a complete, accurate Layer 0 + Layer 1 diff for the test fixtures, with refined severities and the refinement audit trail in the JSON metadata.

---

## Phase 3 — Rename detection ✅ COMPLETE

- [x] Component 11: Rename detector — `specs/11-rename-detection.md`
      (Delivered as a single component covering all three tiers: label-based
      **high** confidence, structural-fingerprint **medium** confidence, and
      user-supplied mapping **certain** confidence, plus cascade consolidation
      of referencing changes.)
- [x] Component 12: Rename refinements — `specs/12-rename-refinements.md`
      (Part A: post-rename axiom re-diffing — the [[DD-018]] fix — surfaces
      structural additions on a renamed entity as independent Layer 1 changes via
      `rename.re_diff_renamed_entities`, run inside `detect()`. Part B:
      `--export-rename-mapping` / `rename_mapping.dump()` writes detected renames
      as a `--rename-mapping`-loadable TOML file.)
- [x] Component 12.5: Anonymous structure decoding — `specs/12.5-anonymous-structures.md`
      (Decodes the anonymous OWL structures the raw pipeline left as `_list:` /
      `_restriction:` Layer 0 noise: `owl:unionOf` / `owl:intersectionOf` sets on
      domain/range/subClassOf/equivalentClass → 12 `*_union_*` kinds (flattening
      and unflattening included); `owl:onDatatype` + `owl:withRestrictions` facet
      restrictions → 4 `datatype_facet_*` / `datatype_base_changed` kinds; and
      `dcterms:isReplacedBy` → `replaced_by_set` / `replaced_by_unset`, promoted
      from the generic `annotation_added` via the post-rename retraction pattern.
      Components 07/08 consult the class-set index and step aside for the keys it
      owns. Open questions Q1-Q3 resolved as proposed: single-member-union loss is
      `union_removed` (+`shape_change`), intersection inverts add/remove severity,
      and the `replaced_by` slice retracts the superseding annotation change. Runs
      `restrictions → class_sets → annotations → renames → replaced_by → severity`.)
- [x] Component 13: **considered, deferred from v1.** The originally-sketched
      Component 13 scope is captured in the backlog (see below); none of it is
      needed for the v1 rename system.

**Phase 3 is COMPLETE** (three components: 11, 12, 12.5). Component 11 detects
renames at three confidence tiers and consolidates each rename plus its cascade
consequences into a single `*_renamed` change, running between the Layer 1 slices
and the severity classifier. Component 12 closes the DD-018 gap (renames that
*also* add structure now show both facts) and adds the rename-mapping export
workflow. Component 12.5 closes the anonymous-structure correctness gap, so
real-world ontologies with union domains/ranges, datatype facets, and
`isReplacedBy` assertions surface as structured changes with zero unexplained
Layer 0 noise.

**Exit criteria (met):** A pair of fixture ontologies where entities have been
renamed produces one rename record each, not an add + remove pair — see
`tests/fixtures/rename/era_renames_*.ttl` (2 class renames + 1 property rename,
cascade consequences subsumed, zero unexplained Layer 0 changes); and a rename
that *also* adds structure surfaces both — see
`tests/fixtures/rename/redidiff/era_rename_with_additions_*.ttl` (2 renames + 1
restriction_added + 1 annotation_removed = 4 visible changes).

---

## Phase 4 — Report renderers (IN PROGRESS)

- [x] Component 14: JSON schema lockdown (canonical, versioned schema) — `specs/14-json-schema.md`
      (The JSON output is now a published JSON Schema 2020-12 contract at
      `docs/schema/diff-result.schema.json`, with `owlcompare.schema` load/validate
      helpers, a `--validate-schema` CLI flag, and an autouse test wrapper that
      schema-validates every CLI JSON payload so drift fails CI. See [[DD-019]]
      (compatibility policy) and [[DD-020]] (`jsonschema` as a test-only dep).)
- [x] Component 15: Markdown report (PR-comment style) — `specs/15-markdown-report.md`
      (The `report/` package is now real: the JSON emitter moved to
      `report/json_report.py` (Component 14's Deviation 1, closed) and
      `report/markdown_report.py` renders a severity-sectioned, PR-comment-ready
      document via `render(result, MarkdownOptions(...))`. New CLI surface:
      `--format markdown`, `--markdown-heading-level`, `--no-markdown-emoji`.
      Eight golden fixtures in `tests/fixtures/markdown/` lock the output
      byte-for-byte. Open questions Q1-Q3 resolved as proposed.)
- [x] Component 16: HTML report — design & wireframe — `specs/16-html-design.md`
      (Design-only component, no code: the full brief lives in `docs/design/`
      — 8 `.md` files plus `WIREFRAMES/` with three competing approaches
      (card / table / narrative). Wireframe **A (card-based)** chosen. Open
      questions Q1-Q3 resolved as proposed: both themes from the start, filter
      sidebar deferred to v1.1, no presentation mode. One token deviation: the
      non-breaking severity colour is `#9a6700`, not the spec's `#bf8700`, which
      fails WCAG AA on white. Component 17 consumes every artifact.)
- [x] Component 17: HTML report — implementation — `specs/17-html-report.md`
      (**The project's headline visual deliverable.** `report/html_report.py`
      renders a self-contained single-file HTML5 report (DD-005): all CSS/JS
      inlined from `report/_html_assets/` via `importlib.resources`, no external
      resources, `file://`-openable. Wireframe A (card-based) per Component 16:
      header status badge + sticky summary strip + Renames → Breaking → Other →
      Unexplained-Layer-0 sections, each change a card with severity stripe, an
      in-place "why breaking" severity-refinement note (story 4), and a
      collapsible details `<dl>`. Per-kind summary renderers in
      `_html_components.py` mirror Component 15's templates with HTML markup;
      unknown kinds fall back to the escaped producer summary. First paint works
      with **no JS** (sections expanded, native `<details>`); JS only enhances
      (section collapse, theme cycle auto→light→dark, JSON download, copy-link).
      New CLI surface: `--format html`, `--html-theme {light|dark|auto}`,
      `--no-embed-json`. Output is byte-deterministic (`SOURCE_DATE_EPOCH`); seven
      golden fixtures in `tests/fixtures/html/` lock it. Open questions Q1-Q3
      resolved as proposed (embed JSON unconditionally; "View JSON" downloads;
      details collapsed by default). Two Component 16 doc conflicts surfaced for
      reconciliation — see the build summary / backlog below.)
- [ ] Component 18: JUnit XML / CI output — `specs/18-junit.md` **(next)**

**Exit criteria:** `owlcompare diff a.ttl b.ttl --format html --out report.html` produces a beautiful, self-contained, offline-viewable HTML file. **Met by Component 17.**

---

## Phase 5 — Polish & v1 release

- [ ] Component 19: GitHub Action wrapper — `specs/19-github-action.md`
- [ ] Component 20: Documentation site (`docs/` → static site) — `specs/20-docsite.md`
- [ ] Component 21: Flagship ERA ontology demo — `specs/21-era-demo.md`
- [ ] Component 22: PyPI release pipeline — `specs/22-release.md`

**Exit criteria:** `uv tool install owlcompare` works from PyPI. README links to a public demo HTML report.

---

## Backlog (post-v1)

### Surfaced during Component 17 (HTML report)

- ~~**JSON `subsumes`/`cascade_subsumes` ordering is not cross-process deterministic.**~~
  **Done (Component 17 follow-up; [[DD-021]]).** Every Layer 1 slice plus the
  rename slice now sort these arrays lexicographically at the producer
  (entities/hierarchy/restrictions/annotations/class_sets/replaced_by + `rename`),
  so `--format json` is byte-reproducible across processes (`PYTHONHASHSEED`). The
  HTML report's embedded-copy workaround was removed since the root cause is fixed.

- ~~**Reconcile Component 16 `BROWSER_SUPPORT.md` with the localStorage decision.**~~
  **Done (Component 17 follow-up).** `docs/design/BROWSER_SUPPORT.md` now carves
  out the single `owlcompare:theme` key (values `light`/`dark`/`auto`), wrapped in
  try/catch with session-only fallback, and documents that no other `localStorage`
  use is permitted.

- ~~**Reconcile the "cap at 50 changes per section" design note with render-all.**~~
  **Done (Component 17 follow-up).** `docs/design/FIRST_PAINT.md` and
  `INFORMATION_ARCHITECTURE.md` no longer mention a 50-change cap or "…and N more";
  both state that sections render every change, with performance from native
  scrolling and lazy `<details>` (tested to 2000 changes under 5 MB), matching the
  spec.


- ~~Surface structural additions on renamed entities.~~ **Done in Component 12 Part A** (the [[DD-018]] fix): after rename detection consolidates a pair, `rename.re_diff_renamed_entities` re-runs the Layer 1 slices over the renamed entity's IRI-substituted axioms and surfaces any genuine additions as independent changes.

### Component 13 scope — considered, deferred from v1

These were the refinements originally sketched for a Component 13; each was
weighed during Component 12 and deliberately left out of v1 (see
`specs/12-rename-refinements.md` § Out of scope):

- Many-to-many rename disambiguation via secondary signals (medium priority).
- Confidence calibration with numeric scores beyond the three tiers (low priority).
- Multi-language label weighting in the match heuristics (low priority).
- Negative-evidence scoring (penalize structural mismatches) (low priority).
- `--list-renames` flag (use `--format json | jq` for now) (low priority).
- Surfacing "uncertain" candidates the user might confirm (low priority).
- Reverse-mapping consistency check on imported mappings (low priority).

- Quad-graph aware loader (resolves Component 04 known limitation)
- Layer 2 inferential diff with HermiT
- Layer 2 inferential diff with ELK
- Layer 3 SHACL impact analysis
- Layer 3 SPARQL impact analysis
- VS Code extension
- Imports closure resolution mode
- Three-way merge view (A vs. B vs. common ancestor)
- Diff of *named graphs* within a quad-store
- SKOS-specific diff mode (broader/narrower/related)
- DCAT-specific diff mode
- Hosted webapp (drop two files, get a sharable URL)
- Preserve namespace prefix bindings through canonicalization (Component 04). After canonicalization, rdflib's namespace manager loses some bindings, causing the Layer 0 text summary to render full IRIs (e.g., `<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>`) instead of prefixed forms (`rdf:type`). The data is correct; only the display is verbose. Fix in Component 04 or its renderer helper.

## Out of scope (deliberately)

- Ontology editing
- Building a new reasoner
- General graph visualization
- Becoming a SHACL validator
- Real-time collaboration features
