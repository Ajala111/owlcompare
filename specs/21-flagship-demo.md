# Component 21: Flagship FIBO Demo

## Identity

- **Component number:** 21
- **Name:** Flagship FIBO demo (public showcase)
- **Module paths:** (no source code; content + assets)
- **Output paths:**
  - `site_src/docs/showcase/fibo.md` — the showcase page itself
  - `site_src/docs/showcase/assets/fibo-diff-report.html` — the full HTML report (downloadable; linked from the page)
  - `site_src/docs/showcase/assets/fibo-diff-report.json` — JSON output (download link)
  - `site_src/docs/showcase/assets/fibo-diff-report.md` — Markdown output (download link)
  - `site_src/docs/showcase/assets/fibo-diff-report.xml` — JUnit XML output (download link)
  - `site_src/docs/showcase/assets/fibo-diff-report-preview.png` — landing-page-style screenshot of the HTML report
  - `examples/fibo_demo/v1/` — FIBO 2023Q3 source files (committed)
  - `examples/fibo_demo/v2/` — FIBO 2024Q3 source files (committed)
  - `examples/fibo_demo/README.md` — reproduction instructions, source URLs, license attribution
  - `examples/fibo_demo/LICENSE-FIBO` — copy of the FIBO MIT license, preserved per attribution requirements
  - `scripts/generate_flagship.py` — script that runs owlcompare against the FIBO files and produces all output formats
- **Roadmap phase:** Phase 5 (third component)
- **Depends on components:** 14 (JSON schema), 15 (Markdown), 17 (HTML), 12.5 (anonymous structures), 20 (docs site infrastructure)
- **Depended on by:** evaluators considering owlcompare for production use

## Purpose

Demonstrate owlcompare on real published versions of a production multi-stakeholder ontology — the Financial Industry Business Ontology (FIBO), published quarterly by EDM Council and standardized by OMG. The flagship shows owlcompare's diff engine working on the kind of complex, evolving, real-world ontology it was designed for: ~10,000 entities, anonymous structures throughout, deprecation patterns, hierarchical refinements, and the rapid evolution rate (~1/3 of entities changing per quarter per academic research) that motivates having a tool like owlcompare in the first place.

The goal is to convert evaluators who've read the docs into users who'll try owlcompare on their own data.

What would break if we removed it: the docs site is the *what* and *how*; the flagship is the *why and on what real data*. Without it, evaluators only see the synthetic Vehicle example and reasonably wonder whether owlcompare scales to production ontology work.

## Why FIBO

FIBO was chosen as the flagship subject for four reasons:

1. **Permissive license (MIT).** The Hugging Face mirror of FIBO documents MIT licensing; the canonical EDM Council repo's `LICENSE` file will be verified during implementation. MIT permits redistribution with attribution, which means we can commit the FIBO source files to the owlcompare repo for fully-reproducible demos.

2. **Substantive quarterly evolution.** EDM Council publishes detailed release notes for each quarterly release. Academic research has documented that approximately one-third of FIBO entities change per quarter — exactly the kind of rapid, multi-stakeholder evolution that makes ontology diff hard and that owlcompare is designed to handle.

3. **Exercises owlcompare's diff engine on a representative real-world evolution.** A year of FIBO-BE evolution (2023Q3 → 2024Q3) is dominated by hierarchy refinements (class/property reparenting), restriction tightening and relaxation, signature changes (domain/range), and severity-classified breaking changes — exactly the kind of editorial, multi-stakeholder churn owlcompare is built to summarize. (Empirical note, recorded during implementation: this particular module/window contains **zero entity renames and zero anonymous-structure changes** — no `unionOf`/`intersectionOf` shifts, datatype-facet changes, or `dcterms:isReplacedBy` assertions. Component 12.5's anonymous-structure decoder and the rename detector therefore do *not* fire here. That is characteristic of this editorial period, not a gap in owlcompare; those features are exercised by the synthetic fixtures and the test suite. The flagship narrative is pivoted accordingly — see § Page structure, Section 5.)

4. **Recognizable to the target audience.** Finance vocabulary is familiar to professional software engineers, data engineers, and knowledge engineers — the primary owlcompare audience. More universal than biomedical ontologies (OBO), less domain-specific than the original ERA candidate.

5. **EDM Council's own release notes provide independent validation.** This is the unique value: FIBO maintainers document what changed in each quarterly release. We can cross-reference owlcompare's findings against the official release notes ("per EDM Council's Q3 2024 release notes, the funds area was cleaned up — owlcompare detects N changes in the Funds ontology, consistent with this"). This grounds the showcase in real evidence, not just our own claims.

## Versions to diff

- **Baseline:** FIBO 2023Q3 (released September 2023)
- **Target:** FIBO 2024Q3 (released September 2024)
- **Time gap:** approximately one year, four quarterly releases
- **Why this pair:** far enough apart to have substantive evolution (the academic research suggests roughly 4× one-quarter rate of change between these), close enough that the diff remains comprehensible

EDM Council's release notes for 2023Q3 through 2024Q3 will be cited in the showcase commentary.

## Positioning principles

1. **owlcompare is the subject; FIBO is the data.** Every framing centers owlcompare's capabilities.

2. **No claim of partnership or endorsement.** owlcompare is not affiliated with EDM Council, OMG, or any FIBO contributor. The demo uses publicly-available data with proper attribution.

3. **Clear, prominent attribution to EDM Council.** They publish, maintain, and own FIBO. The MIT license requires preserving copyright/license notices; we go beyond that to credit visibly on the showcase page.

4. **Reproducibility from public sources.** Anyone can clone the owlcompare repo, navigate to `examples/fibo_demo/`, run the reproduction command, and get identical output.

5. **Honest framing of limitations.** The diff will include any `complex_class_expression_changed` fallbacks owlcompare emits. We don't cherry-pick to make owlcompare look better than it is.

6. **Phelz is positioned as owlcompare author only.** No mention of any other professional affiliation.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| FIBO 2023Q3 release | RDF/Turtle files | github.com/edmcouncil/fibo (tag) or spec.edmcouncil.org | Public; MIT license |
| FIBO 2024Q3 release | RDF/Turtle files | github.com/edmcouncil/fibo (tag) or spec.edmcouncil.org | Public; MIT license |
| EDM Council release notes Q3 2023–Q3 2024 | HTML/Markdown | github.com/edmcouncil/fibo/releases | Reference material for showcase commentary |
| owlcompare diff engine | already in the codebase | Internal | Components 02–17 |

## Outputs

| Output | Description |
|--------|-------------|
| `fibo.md` | Showcase page: header, at-a-glance, embedded screenshot, commentary, reproduction, attribution |
| `fibo-diff-report.html` | Full self-contained HTML report (linked, opens in new tab) |
| `fibo-diff-report.json` | JSON output (download) |
| `fibo-diff-report.md` | Markdown output (download) |
| `fibo-diff-report.xml` | JUnit XML output (download) |
| `fibo-diff-report-preview.png` | Screenshot of the HTML report |
| `examples/fibo_demo/v1/` | Committed FIBO 2023Q3 source files |
| `examples/fibo_demo/v2/` | Committed FIBO 2024Q3 source files |
| `examples/fibo_demo/README.md` | Reproduction instructions |
| `examples/fibo_demo/LICENSE-FIBO` | FIBO's MIT license, preserved |
| `scripts/generate_flagship.py` | Regeneration script |

## Public API

None — this is a content artifact.

## Internal design

### Acquiring the FIBO files

The implementation begins by:

1. **Verifying the FIBO license** by reading the `LICENSE` file at `https://github.com/edmcouncil/fibo/blob/main/LICENSE`. The Hugging Face metadata states MIT; the GitHub `LICENSE` file is authoritative. If the license is not MIT (or a similarly permissive license that permits redistribution with attribution), pause and reassess. **This verification is the first concrete action in Component 21.**

2. **Downloading the two FIBO versions** from their canonical release URLs at `github.com/edmcouncil/fibo/releases/tag/{tag}`. EDM Council uses git tags for each quarterly release; identify the exact tag names for 2023Q3 and 2024Q3.

3. **Selecting the appropriate file subset.** FIBO is large (~10,000 entities across multiple modules). Two options:
   - **Option A (full):** include all FIBO modules. Diff will be substantial — possibly thousands of changes. Realistic, but the rendered HTML report may be large.
   - **Option B (subset):** include only a coherent subset (e.g., FIBO-FBC, FIBO-BE, or another single domain). Diff is more focused and the report is more manageable.

   **Recommendation: start with Option B (a focused subset).** Pick one or two FIBO modules — recommend **FIBO-BE (Business Entities)** since legal entities, organizations, and the kinds of entities BE models are universally recognizable. Full-FIBO is impressive but overwhelming; a single-module diff is comprehensible while still showing substantial evolution.

   The implementation prompt should fetch FIBO-BE (or a similarly self-contained module) for v1 and v2.

### Page structure (`site_src/docs/showcase/fibo.md`)

#### Section 1 — Header

```markdown
# Flagship: FIBO Business Entities, 2023Q3 → 2024Q3

owlcompare diffing two published quarterly releases of the
[Financial Industry Business Ontology (FIBO)](https://spec.edmcouncil.org/fibo/),
a production multi-stakeholder ontology for financial industry vocabulary,
published by the Enterprise Data Management Council (EDM Council) and
standardized by the Object Management Group (OMG).

**Source:** [FIBO at EDM Council](https://github.com/edmcouncil/fibo) ·
**License:** MIT ·
**Module:** FIBO-BE (Business Entities) ·
**Versions:** 2023Q3 (released September 2023) → 2024Q3 (released September 2024) ·
**Run on:** {date} · **owlcompare version:** {version}

Why this comparison: FIBO is a real production ontology under continuous
multi-stakeholder development. [Academic research](https://arxiv.org/abs/2108.05401)
has documented that approximately one-third of FIBO entities change per quarter.
This flagship shows what owlcompare makes of four quarterly releases of evolution
in a single FIBO module.
```

#### Section 2 — At a glance

```markdown
## At a glance

| Metric | Value |
|--------|-------|
| Total Layer 1 changes | NN |
| Breaking changes | NN |
| Additive changes (new classes/properties) | NN |
| Non-breaking changes (restriction relaxations) | NN |
| Info changes (labels, comments, metadata) | NN |
| Renames detected | NN |
| Anonymous structure changes | NN |
| Datatype facet changes | NN |
| Unexplained Layer 0 | N |
```

The "Unexplained Layer 0" line is owlcompare's headline correctness claim — a low or zero count on a real production ontology is the evidence that the diff engine works.

#### Section 3 — Cross-validation against EDM Council release notes

This section is the showcase's unique value-add — owlcompare's findings cross-referenced against EDM Council's own published release notes for each intervening quarter.

```markdown
## Cross-validating with EDM Council's release notes

Between 2023Q3 and 2024Q3, EDM Council published four sets of quarterly release
notes documenting what changed. Let's see how owlcompare's diff aligns with what
the FIBO maintainers themselves recorded.

### From the EDM Council 2023Q4 release notes

> "[Specific claim from release notes — e.g., 'We refined the legal entity
> hierarchy in BE, including reorganizing the relationship between Person and
> LegalPerson.']"
>
> — [EDM Council, FIBO 2023Q4 Release Notes](https://github.com/edmcouncil/fibo/releases/tag/2023Q4)

owlcompare reports the corresponding changes:

> [Rendered owlcompare output showing the related changes — e.g., "Class
> renamed: fibo-be:OldName → fibo-be:NewName (high confidence)"]

### From the EDM Council 2024Q1 release notes

[Similar pattern...]

### ... continued for Q2 and Q3
```

The cross-validation pattern is: quote the official release note, then show owlcompare's corresponding output. This grounds the showcase in evidence and lets evaluators see *both* sides of the comparison.

The 4 quarterly release notes between 2023Q3 and 2024Q3 (i.e., 2023Q4, 2024Q1, 2024Q2, 2024Q3) provide several concrete cross-references. Pick 3-5 that best showcase owlcompare's strengths (renames, anonymous structure decoding, severity classification).

#### Section 4 — The full report

```markdown
## The full interactive report

[**Open the interactive HTML report ↗**](assets/fibo-diff-report.html){:target="_blank"}

![Screenshot of the FIBO diff HTML report](assets/fibo-diff-report-preview.png)

Self-contained HTML; opens offline; no dependencies. Also available as
[Markdown](assets/fibo-diff-report.md), [JSON](assets/fibo-diff-report.json),
or [JUnit XML](assets/fibo-diff-report.xml).
```

#### Section 5 — Commentary: how owlcompare describes the changes

Walk through 3–4 specific changes that demonstrate owlcompare's strengths. Each example is a small subsection.

**Macro framing (the headline).** The flagship's story is *not* "lots of changes" — it's that **owlcompare describes a coordinated multi-file refactor in 41 comprehensible events.** Of the 41 Layer 1 changes, **34 are one coordinated migration**: FIBO-BE's adoption of the OMG Commons Ontology Library, swapping its own `fibo-fnd-pty-pty:` Parties vocabulary for the shared `cmns-pts:` / `cmns-rlcmp:` vocabulary (24 restriction add/removes + 10 reparents). FIBO's own embedded `skos:changeNote` (ticket FND-380) confirms it — see Section 3. Lead the page with this observation.

**For the chosen flagship file (`BE/OwnershipAndControl/Executives.rdf`, 2023Q3 → 2024Q3), the diff contains no renames and no anonymous-structure changes** (see "Why FIBO" §3). The four confirmed commentary blocks:

1. **Lateral reparenting — the Commons-adoption migration, consolidated.** Name Commons-adoption as the editorial event. Frame: "owlcompare detects FIBO's Commons-adoption migration as **10 lateral reparents, consolidated from 20 raw triple changes**." Highlight the `(lateral)` direction — owlcompare recognizes the parent moved to a same-named concept in a different namespace (e.g. `fibo-fnd-pty-pty:actsOn → cmns-pts:actsOn`), neither up nor down the hierarchy.
2. **Severity classification at scale.** The 24 restriction changes split into 12 breaking adds + 12 non-breaking removes; explain owlcompare's asymmetry (adding a constraint can invalidate data → breaking; removing relaxes → non-breaking). Honest forward-looking note: "A future owlcompare version could collapse these pairs into a `restriction_predicate_migrated` kind; for v1, they're correctly reported as independent breaking/non-breaking changes."
3. **Signature evolution** — keep as a separate, briefer block (do *not* merge with Block 2). `domain_changed` / `range_changed` on `fibo-be-oac-exec:elects` (both domain and range) and `nominates`: how a property's applicability surface shifts under the migration.
4. **Honest limits + correctness callout** — two paragraphs. *Paragraph 1 (limits):* the single `complex_class_expression_changed` on `fibo-be-oac-exec:BoardCapacity` (`depth 2`, structured diff deferred) — owlcompare tells you what it didn't fully decode rather than hiding it. *Paragraph 2 (correctness):* the Layer 0 accounting — 214 raw triple changes distilled to 41 structured events, with the only 10 "unexplained" being meaningful metadata (`owl:imports` reorg, `owl:versionIRI` bump, copyright-year update), plus zero renames and zero anonymous-structure changes this window.

Each commentary block is:
1. A heading describing the pattern
2. A literal blockquote of owlcompare's rendered output
3. 2-3 sentences of plain-language explanation of what the tool detected and why it matters

#### Section 6 — Reproduce this diff

```markdown
## Reproduce this diff

The exact FIBO source files and reproduction command are committed to the
owlcompare repo:

​```bash
# Clone owlcompare
git clone https://github.com/Ajala111/owlcompare.git
cd owlcompare

# Install owlcompare
uv sync                     # if you have uv
# OR: pip install -e .       # if you prefer pip

# Run the flagship diff
uv run python -m owlcompare diff \
  examples/fibo_demo/v1/{appropriate-file}.ttl \
  examples/fibo_demo/v2/{appropriate-file}.ttl \
  --format html --out flagship-report.html

# Open flagship-report.html in your browser
​```

Or regenerate every output format used on this page:

​```bash
python scripts/generate_flagship.py
​```

The FIBO source files in this repo are unmodified copies of EDM Council's
publicly-released versions (MIT license; see `examples/fibo_demo/LICENSE-FIBO`).
The reproduction output may differ slightly from this page if you run a
newer owlcompare version with updated classifiers.
```

#### Section 7 — Attribution

```markdown
## Attribution

The Financial Industry Business Ontology is published by the
[Enterprise Data Management Council (EDM Council)](https://edmcouncil.org/) and
standardized by the [Object Management Group (OMG)](https://www.omg.org/).
FIBO is licensed under the [MIT License](LICENSE-FIBO).

This showcase demonstrates owlcompare's diff capabilities. owlcompare is not
affiliated with EDM Council, OMG, or any FIBO contributor. We use the
publicly-available FIBO files as a representative test case for the kinds of
multi-stakeholder ontology evolution owlcompare is designed for.

owlcompare is authored by [Olatunji Felix Ajala (phelz)](https://github.com/Ajala111),
who chose FIBO as the flagship subject for its permissive license, its rapid
quarterly evolution, and its broad recognizability to the ontology engineering
community.
```

#### Section 8 — Footer

```markdown
---

← [Back to owlcompare docs](../index.md)
```

### Generating the demo outputs (`scripts/generate_flagship.py`)

A Python script that automates the demo regeneration:

1. Reads source files from `examples/fibo_demo/v1/` and `examples/fibo_demo/v2/`
2. Runs `owlcompare diff` for each output format
3. Writes outputs to `site_src/docs/showcase/assets/`
4. Optionally generates the preview screenshot via headless browser (or documents how to capture manually)
5. Reads metrics from the JSON output for the at-a-glance table — outputs them as text the implementation can paste into the markdown

The script is run *manually* during implementation; it's not part of the docs build pipeline. The outputs are committed to the repo. A contributor regenerates by running the script after a future owlcompare upgrade.

### Screenshot of the HTML report

Static PNG capture at `site_src/docs/showcase/assets/fibo-diff-report-preview.png`. Same workflow as the landing page screenshots:
1. Open `fibo-diff-report.html` in Chrome at 1440×900 viewport
2. Capture full-size screenshot via DevTools
3. Save as PNG, overwriting any placeholder

Documented in `examples/fibo_demo/README.md` for regeneration.

### The FIBO TTL files

Stored at `examples/fibo_demo/v1/` and `examples/fibo_demo/v2/`. The specific files depend on which FIBO module(s) we include — for FIBO-BE only, this is approximately a dozen `.ttl` files per version.

The `examples/fibo_demo/README.md` documents:
- Exact FIBO versions (with git tags from `github.com/edmcouncil/fibo`)
- Source URLs for each file
- MD5/SHA256 hashes for verification (optional)
- The MIT license attribution

The `examples/fibo_demo/LICENSE-FIBO` file is a verbatim copy of FIBO's `LICENSE` file from the canonical EDM Council distribution.

### Docs nav integration

`mkdocs.yml` adds the showcase as a top-level nav entry, positioned **after** the existing tabs (Getting Started, Guides, Reference, Architecture) so it doesn't compete with onboarding flow:

```yaml
nav:
  # ... existing ...
  - Showcase:
    - showcase/fibo.md
```

Material's tabs render this as a top-level "Showcase" tab. Evaluators ready to see real-world capability find it easily; new users hit Getting Started first.

## Edge cases & failure modes

- **The FIBO license at the canonical repo isn't MIT.** If the GitHub `LICENSE` file says something else (Apache 2.0, CC BY 4.0, EDM Council custom), pause and reassess. Apache 2.0 and CC BY 4.0 are both permissive and acceptable; custom licenses require careful analysis. The Hugging Face mirror's metadata is suggestive but not authoritative.

- **The diff is overwhelming (10,000+ changes).** If full FIBO produces an unmanageable diff, scope to a smaller module. FIBO-BE has hundreds of entities; the diff between 2023Q3 and 2024Q3 should be in the hundreds-of-changes range — interesting but comprehensible.

- **The diff is uninteresting (a handful of trivial changes).** If FIBO-BE didn't evolve much in this period, switch to a more actively-evolved module (FIBO-FND, FIBO-FBC) or expand to two modules.

- **The HTML report file is large** (multi-MB). Acceptable; modern browsers handle multi-MB HTML files fine. Document the size on the showcase page so users know what to expect when they click the link.

- **Many `complex_class_expression_changed` fallbacks.** This is owlcompare admitting its limits. The commentary section acknowledges them honestly. The headline metric "X% of changes resolved to specific semantic kinds; Y% fell back to complex_class_expression_changed" tells the truth.

- **EDM Council updates FIBO during the implementation period.** Acceptable; we pin to specific git tags. The showcase is a snapshot of two specific releases.

- **Future owlcompare upgrades produce different output.** Documented in the reproduction section. The showcase pins to the owlcompare version at time of publication; running the regeneration script with a newer version may produce slightly different output as classifiers evolve.

- **The cross-validation reveals an owlcompare bug.** If owlcompare misses a change that EDM Council's release notes clearly document — or detects a change that isn't real — that's a bug. Surface it: file an issue, fix it before publishing the flagship.

## Dependencies

No new code dependencies. Possibly add `playwright` as an optional dev dependency if we want automated screenshot capture — but the manual screenshot workflow used in Component 20 is also acceptable.

## Acceptance tests

The flagship is content, not code. Automated tests verify structural soundness:

- [ ] `site_src/docs/showcase/fibo.md` exists and is valid Markdown
- [ ] All linked assets exist (`fibo-diff-report.html`, `.json`, `.md`, `.xml`, `.png`)
- [ ] `fibo-diff-report.json` validates against the bundled schema
- [ ] `examples/fibo_demo/v1/` and `v2/` directories exist with `.ttl` content
- [ ] `examples/fibo_demo/LICENSE-FIBO` exists (preserved MIT license)
- [ ] `examples/fibo_demo/README.md` exists with reproduction instructions
- [ ] `scripts/generate_flagship.py` exists and is syntactically valid Python
- [ ] `mkdocs build --strict` succeeds with the showcase page in nav
- [ ] No broken internal links from the showcase page

These extend `tests/unit/test_docs_build.py` following Component 20's pattern.

## Manual verification

- [ ] The FIBO license at the canonical repo confirmed as MIT (or equivalent permissive)
- [ ] The reproduction command runs cleanly from a fresh clone
- [ ] The showcase page renders correctly in light and dark modes
- [ ] All download links work
- [ ] The HTML report opens correctly in a new tab
- [ ] The cross-validation quotes from EDM Council's release notes are accurate (not paraphrased loosely)
- [ ] The owlcompare output quoted in commentary is current (not stale from an earlier dev iteration)
- [ ] All four download formats (HTML, MD, JSON, XML) work and open correctly
- [ ] The screenshot reflects current owlcompare HTML report output (not a previous design)

## Out of scope (deliberately)

- A live in-browser FIBO diff playground. Defer to v1.1.
- Comparing more than two FIBO versions. One pair is enough for v1.
- Comparing FIBO against another ontology (e.g., schema.org). Apples-to-oranges; not the point.
- Performance benchmarks. v1 showcase is about correctness, not speed.
- Auto-regeneration on every docs build. Manual via the script.
- Multi-module FIBO diff (all of FIBO at once). v1 starts with one module.
- Sentiment analysis of FIBO release notes ("did EDM Council describe this change as a refinement or a deprecation?"). Out of scope; we cite their notes verbatim.

## Open questions

- [ ] **Q1:** Which FIBO module(s) should the flagship diff?
  **Proposed:** **FIBO-BE (Business Entities)** as the primary subject. Legal persons, organizations, and business identifiers are universally recognizable to the target audience. If the diff is too small to be interesting, expand to FIBO-FBC or FIBO-FND. The implementation should choose based on what produces the most interesting (but not overwhelming) diff.

- [ ] **Q2:** Should the showcase appear in the docs nav as a top-level tab or as a sub-section?
  **Proposed:** **Top-level "Showcase" tab**, positioned after the existing onboarding/reference tabs. Visible to evaluators ready to see real-world capability; not the first thing new users see.

- [ ] **Q3:** Should EDM Council release notes be quoted verbatim with attribution, or summarized in plain language?
  **Proposed:** **Quote verbatim with clear attribution to "EDM Council, FIBO [quarter] Release Notes" and a link to the release on GitHub.** Verbatim quotations are honest and credible; summaries risk misrepresenting their stance. Keep each quote short (under 50 words) per copyright fair use.

- [ ] **Q4:** Should the showcase include "owlcompare missed this" or "owlcompare wrongly detected that" content if cross-validation surfaces such cases?
  **Proposed:** **Yes, honestly acknowledge limitations.** If cross-validation reveals owlcompare missed a documented change, surface it: "EDM Council notes X; owlcompare did not detect this — open issue: [link]." Honest framing builds credibility; pretending perfection erodes it.

- [ ] **Q5:** Should we redistribute the entire FIBO module's source files (potentially dozens of .ttl files per version) in the repo, or just the specific files needed for the diff?
  **Proposed:** **Redistribute the entire chosen module per version** so that `owlcompare diff examples/fibo_demo/v1 examples/fibo_demo/v2` (passing directories, not single files) becomes possible in a future enhancement, and so users exploring the source can see the full FIBO module context, not just isolated files. The repo size grows modestly; this is the right trade-off for a reproducible flagship.

If you have preferences on these, override before implementation.

## References

- FIBO at EDM Council: https://github.com/edmcouncil/fibo
- FIBO specification: https://spec.edmcouncil.org/fibo/
- FIBO release notes: https://github.com/edmcouncil/fibo/releases
- The ontology drift paper documenting FIBO's quarterly evolution: https://arxiv.org/abs/2108.05401
- `docs/PROJECT_BRIEF.md` (motivation for real-world demo)
- `specs/12.5-anonymous-structures.md` (the patterns FIBO heavily uses)
- The bundled JSON schema (`docs/schema/diff-result.schema.json`)
- DD-024 (docs site infrastructure), DD-025 (exit codes)
