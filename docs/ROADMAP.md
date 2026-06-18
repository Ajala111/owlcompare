# Roadmap

This is the source of truth for what's done, what's in progress, and what's deferred.

**Current phase:** Phase 5 — Polish & v1 release. **Phase 5 is COMPLETE**:
Component 19 (GitHub Action wrapper) and Component 20 (documentation site) are
delivered. **Phase 4 (Report renderers) is COMPLETE**: Components 14 (JSON Schema
Lockdown), 15 (Markdown report), 16 (HTML report — design & wireframe), 17 (HTML
report — implementation), and 18 (JUnit XML / CI output) all delivered.
`owlcompare diff` now emits JSON, text, Markdown, HTML, and JUnit XML, is
wrappable as a three-line GitHub Actions step, and has a public MkDocs Material
documentation site (build pipeline + landing page + priority pages + stubs).
**Component 21 (flagship FIBO demo) is delivered** — a public Showcase tab diffing
two real FIBO Business Entities releases. **Component 22 (PyPI release pipeline)
is delivered** — the final Phase 5 component: the package metadata, CHANGELOG, and
the two tag-triggered Trusted-Publishing workflows are in place and the build is
verified locally. **v0.1.0 is the planned first public tag** (push of `v0.1.0`
triggers `release.yml` → PyPI). Phase 5 — and the v1 roadmap — is complete.

> **Soft prerequisite flagged:** Component 22 (PyPI release pipeline) is now a
> soft prerequisite for the Action to be fully usable by **external** users —
> `owlcompare-version: latest` can only `pip install owlcompare` once owlcompare
> is on PyPI. Until then external users install a pinned commit via
> `pip install git+https://github.com/Ajala111/owlcompare.git@<ref>`, and the Action
> self-tests inside this repo via `owlcompare-version: local`.

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

## Phase 4 — Report renderers ✅ COMPLETE

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
- [x] Component 18: JUnit XML / CI output — `specs/18-junit-xml.md`
      (`report/junit_report.py` renders a `DiffResult` as a JUnit XML document via
      `render(result, JUnitOptions(...))` — one `<testcase>` per change, breaking
      changes as `<failure>`, info changes optionally as `<skipped>`
      (`--junit-include-skipped`), renames always pass, and the whole text diff
      embedded as a `<system-out>` CDATA section (with `]]>`-terminator guarding).
      New CLI surface: `--format junit`, `--junit-suite-name`,
      `--junit-include-skipped`; the exit-code logic (10 if breaking, else 0) is
      unchanged. Output is byte-deterministic — testcases sorted by
      `(classname, name)`, `timestamp` honours `SOURCE_DATE_EPOCH`, stable attribute
      order; seven golden fixtures in `tests/fixtures/junit/` lock it and every one
      round-trips through `xml.etree.ElementTree`. Built from string templates with
      stdlib `xml.sax.saxutils.escape` (no new dependency). Open questions Q1-Q3
      resolved as proposed: generic suite name, full text rendering in
      `<system-out>`, no `<system-err>`.)

**Exit criteria:** `owlcompare diff a.ttl b.ttl --format html --out report.html`
produces a beautiful, self-contained, offline-viewable HTML file (met by Component
17); `--format junit --out junit.xml` produces a CI-ready JUnit XML report (met by
Component 18). **Phase 4 complete.**

---

## Phase 5 — Polish & v1 release

- [x] Component 19: GitHub Action wrapper — `specs/19-github-action.md`
      (Composite Action at the repo-root `action.yml`: full input/output schema,
      baseline detection (PR base / `HEAD~1` / previous tag / explicit /
      fallback) with `git worktree` checkout, multi-format diff runs, artifact
      upload, update-in-place PR comment via a marker, and deferred
      `fail-on-breaking` build status. `docs/github-action.md` is the user
      reference; `tests/unit/test_action_yml.py` statically validates the YAML
      (PyYAML, dev-only — [[DD-022]]); `.github/workflows/action-smoke-test.yml`
      is the manual end-to-end check. Open questions Q1-Q3 resolved as proposed.
      Three deviations surfaced below.)
- [x] Component 20: Documentation site (`docs/` → static site) — `specs/20-docs-site.md`
      (MkDocs Material site at `https://ajala111.github.io/owlcompare/`: optional
      `docs` dependency group (default `uv sync` doesn't pull it), `mkdocs.yml` at
      the repo root (`docs_dir: site_src/docs`), a self-contained custom landing
      page (`site_src/index.html` — hero, see-it-in-action, three columns, install
      tabs, real-world "18 raw → 5 meaningful" example, footer; no external
      resources), and a structure-plus-stubs content set: 10 complete priority
      pages (landing, installation, first-diff, understanding-output,
      ci-integration, cli, exit-codes, faq, changelog, contributing) plus 12
      well-structured stubs (100+ words each, with an `!!! info` "being expanded"
      note). Two live interactive example reports generated from the era fixtures
      ship at `/examples/`. `.github/workflows/docs.yml` builds with
      `mkdocs build --strict` and deploys to GitHub Pages; `tests/unit/test_docs_build.py`
      and `test_docs_content.py` (16 + 63 cases) validate config, nav targets,
      landing-page self-containment, and zero broken internal links as part of the
      normal pytest run. Open questions Q1-Q3 resolved as proposed (live sample
      reports linked from the landing page; ROBOT comparison as a single FAQ
      entry; no custom domain in v1). Deviations surfaced in the build summary.
      **Positioning follow-up (2026-06-10):** the public-facing docs (landing
      page, first-diff tutorial, example reports) use a generic Vehicle example
      fixture (`tests/fixtures/sample/sample_*.ttl`, `ex:` prefix) rather than the
      railway/ERA fixtures, so the public framing isn't tied to one domain; the
      ERA fixtures remain internal (test suite + the planned Component 21 demo).
      Tone softened to category-level framing throughout.)
- [x] Component 21: Flagship FIBO demo — `specs/21-flagship-demo.md`
      (Public showcase at `site_src/docs/showcase/fibo.md`, wired into the docs
      nav as a top-level **Showcase** tab. Diffs two published quarterly releases
      of the **FIBO Business Entities** module — git tags `master_2023Q3` →
      `master_2024Q3` (MIT-licensed; sources committed under `examples/fibo_demo/`
      with `LICENSE-FIBO` preserved) — on `OwnershipAndControl/Executives.rdf`.
      owlcompare distills 214 raw triple changes into **41 structured events**
      (28 breaking / 12 non-breaking / 1 info; 0 renames, 0 anonymous-structure
      changes, 10 unexplained Layer 0 — all meaningful metadata). The headline
      story: **34 of 41 changes are one coordinated migration** — FIBO-BE adopting
      the OMG Commons vocabulary (`fibo-fnd-pty-pty:` → `cmns-pts:`) — cross-
      validated against three verbatim EDM Council release-note quotes (2023Q4,
      2024Q1 ×2) and FIBO's own embedded `skos:changeNote` (ticket FND-380).
      `scripts/generate_flagship.py` regenerates all four output formats (clean,
      repo-relative, reproducible) plus a stdlib-only placeholder preview PNG;
      `tests/unit/test_docs_build.py` gains 11 structural checks. **Narrative
      pivot (recorded in spec "Why FIBO" §3):** this module/window contains no
      renames and no anonymous structures, so the commentary leads with severity
      classification, hierarchy reparenting, signature evolution, and an honest
      `complex_class_expression_changed` fallback — not the rename/Component-12.5
      features the spec originally anticipated. See the build summary below.)
- [x] Component 22: PyPI release pipeline — `specs/22-pypi-release.md` (written retroactively)
      (Package metadata completed in `pyproject.toml` — keywords, full classifier
      set, OSI license classifier, expanded `project.urls`; version single-sourced
      at `0.1.0` in `src/owlcompare/_version.py` per DD-013, *not* statically in
      pyproject. The wheel excludes `examples/fibo_demo/` (data, ~3 MB) while the
      sdist ships it for completeness — verified against the built artifacts
      (wheel: 0 demo files + bundled schema; sdist: 108 demo files). `CHANGELOG.md`
      (Keep a Changelog) added at the repo root with an honest v0.1.0 entry
      (Layers 0–1 only; Layers 2–3 deferred; four severity levels). Two
      tag-triggered workflows: `release.yml` (`v*.*.*` tags → PyPI, environment
      `pypi`, OIDC Trusted Publishing, strict final-release guard + tag/version
      match check, `python -m build`, `twine check`,
      `pypa/gh-action-pypi-publish@release/v1`, GitHub Release via
      `softprops/action-gh-release@v2` with the CHANGELOG section as the body) and
      `release-test.yml` (`pre/*` tags → TestPyPI, environment `testpypi`, no
      GitHub Release). Release process + recovery/yank + semver policy documented
      in `site_src/docs/contributing.md`. 27 tests in `tests/unit/test_release.py`.
      `python -m build` + `twine check` PASS locally; the wheel installs and runs
      in a fresh venv (`python -m owlcompare --version` → `0.1.0`). **NOTE:** this
      component had no spec during implementation — it was built to the operator's
      detailed brief; `specs/22-pypi-release.md` was written **retroactively** to
      preserve the design record (it documents what shipped, not what was planned).
      Author email omitted from `pyproject.toml` (name only) at the maintainer's
      request. **Phase C (Phelz's manual step):** tag and push `v0.1.0` to trigger
      the publish.)

**Exit criteria:** `uv tool install owlcompare` works from PyPI (pipeline ready;
fires on the `v0.1.0` tag — Phase C). README links to a public demo HTML report.

---

## v0.2.0 — Severity refinement and Layer 2 prep

Driven by community feedback on v0.1.0:

### Per-layer severity classification

v0.1.0 classifies severity globally per change kind. Community feedback
has pointed out that severity is consumer-dependent — what's breaking for
a SPARQL-query consumer is not breaking for a SHACL validator, and vice
versa.

v0.2.0 will move toward per-layer severity:

- **Layer 1 (structural)** — severity based on the ontology's own axioms
  (current v0.1.0 behavior; refined for clarity)
- **Layer 2 (inferential)** — severity based on what a reasoner derives
  (new in v0.2.0)
- **Layer 3 (impact)** — severity based on downstream consumer impact
  (planned for v0.3.0+)

A single change may carry different severity at different layers. Removing
a class is structural-breaking; adding `owl:disjointWith` may be
inferential-breaking even though it's a structural addition.

### Use-case profiles

Replace the kind-level `--severity-config` with profile-based
classification. Profiles describe the consumer's relationship with the
ontology (SPARQL queries, SHACL validation, instance data, reasoner-derived
facts). Each profile maps change kinds to severity based on what actually
breaks that consumer.

v0.2.0 will ship built-in profiles for common cases (SPARQL consumer, SHACL
validator, schema-only consumer); user-defined profiles via TOML remain
supported.

### Acknowledgment

These directions are driven by user feedback on the v0.1.0 LinkedIn
announcement — particularly comments from ontology engineers pointing out
that severity classification is consumer-dependent and can't be a global
property of change kinds. Continuing engagement welcome at the
[GitHub Issues page](https://github.com/Ajala111/owlcompare/issues).

---

## Backlog (post-v1)

### Surfaced during Component 19 (GitHub Action)

- **One diff run, many output formats.** The Action runs `owlcompare diff` once
  per requested format (JSON for counts, then JUnit/HTML/Markdown), which re-parses
  and re-diffs each time. A CLI enhancement — e.g. `--format a,b,c` with an
  `--out-template report.{ext}` — would let one invocation emit every format. v1.1;
  the Action's per-format loop is already shaped to adopt it. (From specs/19 § CLI
  integration.)
- **A `pull_request_target` recipe for trusted forks.** The PR-comment step can't
  write on fork PRs (read-only token). A documented, safe `pull_request_target`
  pattern would let maintainers opt trusted forks in. Security-sensitive; deferred.

#### Component 19 deviations (delivered, intentional)

1. **`baseline-ref` default is the sentinel `auto`, not a raw GitHub expression.**
   The spec's inputs table shows the default as
   `${{ github.event.pull_request.base.ref }}` (auto) or `main`. A single input
   default can't express the full algorithm (PR base / `HEAD~1` / previous tag /
   fallback), so the default is the literal `auto` and the detection runs in bash
   — exactly as the spec's § Baseline detection prose describes ("defaults to
   auto"). Explicit refs are honoured verbatim.
2. **Inputs are passed to `run:` scripts via `env:`, never interpolated with
   `${{ }}`.** The spec outline interpolates inputs directly; injecting
   user-controlled values into a shell is a known injection vector, so every
   input reaches bash as an environment variable instead. Also fixes quoting for
   paths with spaces. (Surfaced per the "be attentive to runner-environment
   surprises / permissions" instruction.)
3. **The `latest` git-install fallback uses `github.repository`/`github.sha`,
   which only resolves to owlcompare inside this repo.** For external repos the
   canonical path is PyPI (Component 22) or an explicit pinned commit; the git
   fallback is a development-testing convenience, documented as such in
   `docs/github-action.md` § Installation modes and § Known limitations. The
   `owlcompare-version: local` mode (editable install of the checkout) is what the
   smoke test uses to exercise live code with no published package.

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
