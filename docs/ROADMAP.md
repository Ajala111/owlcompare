# Roadmap

This is the source of truth for what's done, what's in progress, and what's deferred.

**Current phase:** Phase 2 — Syntactic and structural diff (Phase 1 complete)

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

## Phase 2 — Syntactic and structural diff

- [ ] Component 05: Layer 0 syntactic diff — `specs/05-syntactic-diff.md`
- [ ] Component 06: Layer 1 structural diff (entities) — `specs/06-structural-entities.md`
- [ ] Component 07: Layer 1 structural diff (hierarchy) — `specs/07-structural-hierarchy.md`
- [ ] Component 08: Layer 1 structural diff (restrictions) — `specs/08-structural-restrictions.md`
- [ ] Component 09: Layer 1 structural diff (annotations) — `specs/09-structural-annotations.md`
- [ ] Component 10: Severity classification — `specs/10-severity.md`

**Exit criteria:** `owlcompare diff a.ttl b.ttl --format json` produces a complete, accurate Layer 0 + Layer 1 diff for the test fixtures.

---

## Phase 3 — Rename detection

- [ ] Component 11: Rename detector (label-based) — `specs/11-rename-labels.md`
- [ ] Component 12: Rename detector (structural fingerprint) — `specs/12-rename-fingerprint.md`
- [ ] Component 13: Rename mapping file support — `specs/13-rename-mapping.md`

**Exit criteria:** A pair of fixture ontologies where 5 entities have been renamed produces 5 high-confidence rename records, not 10 (5 add + 5 remove) entries.

---

## Phase 4 — Report renderers

- [ ] Component 14: JSON report (canonical schema) — `specs/14-json-report.md`
- [ ] Component 15: Markdown report (PR-comment style) — `specs/15-markdown-report.md`
- [ ] Component 16: HTML report — design & wireframe — `specs/16-html-design.md`
- [ ] Component 17: HTML report — implementation — `specs/17-html-impl.md`
- [ ] Component 18: JUnit XML / CI output — `specs/18-junit.md`

**Exit criteria:** `owlcompare diff a.ttl b.ttl --format html --out report.html` produces a beautiful, self-contained, offline-viewable HTML file.

---

## Phase 5 — Polish & v1 release

- [ ] Component 19: GitHub Action wrapper — `specs/19-github-action.md`
- [ ] Component 20: Documentation site (`docs/` → static site) — `specs/20-docsite.md`
- [ ] Component 21: Flagship ERA ontology demo — `specs/21-era-demo.md`
- [ ] Component 22: PyPI release pipeline — `specs/22-release.md`

**Exit criteria:** `uv tool install owlcompare` works from PyPI. README links to a public demo HTML report.

---

## Backlog (post-v1)

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

## Out of scope (deliberately)

- Ontology editing
- Building a new reasoner
- General graph visualization
- Becoming a SHACL validator
- Real-time collaboration features
