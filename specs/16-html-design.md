# Component 16: HTML Report Design

## Identity

- **Component number:** 16
- **Name:** HTML report design (wireframes, IA, design tokens — no code)
- **Module paths:** none (this component produces docs only)
- **Output paths:**
  - `docs/design/CONTENT_INVENTORY.md` — every data point the report can show
  - `docs/design/USER_STORIES.md` — 3–5 named scenarios
  - `docs/design/INFORMATION_ARCHITECTURE.md` — page structure + navigation
  - `docs/design/WIREFRAMES/` — directory with three competing wireframes
  - `docs/design/CHOSEN_DESIGN.md` — selected wireframe + rationale
  - `docs/design/DESIGN_TOKENS.md` — typography, spacing, color
  - `docs/design/UI_PRIMITIVES.md` — component catalog
  - `docs/design/FIRST_PAINT.md` — what must be visible in 100 ms
  - `docs/design/ACCESSIBILITY.md` — a11y requirements
  - `docs/design/BROWSER_SUPPORT.md` — target browsers + fallback policy
- **Roadmap phase:** Phase 4 (third component)
- **Depends on components:** 14 (JSON schema — defines what data is available), 15 (Markdown report — establishes which data points are user-visible vs technical)
- **Depended on by:** 17 (HTML report implementation — consumes every artifact this produces)

## Purpose

Produce a complete design brief for the HTML report before any HTML/CSS/JavaScript is written. After this component, Component 17 implements against a fully-specified design — no UX decisions are made during implementation.

What would break if we removed it: Component 17 would default to "designed by code" — its structure determined by implementation convenience rather than user need. Internal inconsistencies would proliferate. We'd rewrite it.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| JSON schema | docs | Component 14's `docs/schema/diff-result.schema.json` | Defines the available data |
| Existing terminal renderer | code | Component 05's `_render_diff.py` | Reference for what works at small scale |
| Existing Markdown renderer | code | Component 15's `markdown_report.py` | Reference for what's prioritized in narrow contexts |
| Project brief | doc | `docs/PROJECT_BRIEF.md` § Non-negotiables | "The HTML report has to be beautiful and fast" |

## Outputs

| Output | Description | Audience |
|--------|-------------|----------|
| `CONTENT_INVENTORY.md` | Every data point the HTML report could show, classified by importance | Anyone reasoning about info density |
| `USER_STORIES.md` | 3–5 named workflows | Anyone testing whether the design actually serves users |
| `INFORMATION_ARCHITECTURE.md` | Page structure + navigation model | Component 17's implementer |
| `WIREFRAMES/*.md` | Three competing wireframe sketches | Decision-makers reviewing options |
| `CHOSEN_DESIGN.md` | Selected wireframe + rationale | Onboarding context for Component 17 |
| `DESIGN_TOKENS.md` | Visual constants (typography, spacing, color) | CSS values in Component 17 |
| `UI_PRIMITIVES.md` | Reusable component catalog | Component class names in Component 17 |
| `FIRST_PAINT.md` | What loads first | Component 17's loading strategy |
| `ACCESSIBILITY.md` | A11y requirements | Component 17 must implement these |
| `BROWSER_SUPPORT.md` | Target browsers + fallback policy | Component 17's CSS feature choices |

## Public API

None — Component 16 produces no code. The "API" is the design brief itself.

## Internal design

### Section 1 — Content inventory

Categorize every data field from the JSON schema into three tiers:

**Tier 1 — Always visible (the headline information):**
- The top-level "what changed" summary: title, counts of breaking vs other
- Renames (because they're the most informative pattern)
- Breaking changes (because they affect downstream consumers)
- Source-A vs Source-B identification

**Tier 2 — Available on first scroll or one-click expansion:**
- Non-breaking, additive, info changes (grouped)
- Per-change details: subject IRI, before/after values, evidence
- Severity refinements (the audit trail)
- Restriction full readable forms with `before`/`after`

**Tier 3 — Available behind navigation or filters:**
- The full Layer 0 syntactic change list
- `change_id` values (debugging)
- Subsumption registry contents
- Schema version, generator version

The CONTENT_INVENTORY.md lists every field, its tier, and a one-sentence rationale.

### Section 2 — User stories

Three to five named scenarios. Each story has: persona, goal, entry point, navigation path, success outcome. Examples to develop:

1. **"The reviewer skim"** — A senior ontology engineer opens an attached `report.html` from a colleague's PR. They have 30 seconds to decide whether the PR is safe to approve. Goal: see breaking changes within 5 seconds; understand them within 30. Entry: opens the file. Path: title → breaking section → done.

2. **"The integrator deep-dive"** — A data engineer whose pipeline depends on the ontology is investigating why their SHACL validation broke after a version bump. Goal: find every change affecting properties they reference. Entry: opens the file. Path: filter by entity kind = object_property → expand each → read full before/after.

3. **"The historian"** — A new team member is learning the ontology by reviewing its evolution. They open archived `report.html` files from the project history. Goal: understand each version's intent. Entry: opens the file. Path: read top summary → expand all → study the rename + reparent narrative.

4. **"The CI debugger"** — A developer whose CI failed due to a breaking-change exit code wants to understand which specific change tripped the build. Goal: identify the single change that pushed severity into breaking. Entry: clicks the report link from the CI log. Path: title → breaking section → drill into the specific change → see "this is why."

5. **"The architect's audit"** — An ontology lead reviews the evolution of their model over six months to identify patterns ("are we narrowing too aggressively?"). Goal: aggregate insight, not individual changes. Entry: opens several reports across versions. Path: counts at top → severity breakdown chart (if present) → identify patterns.

Each story includes a "design implication" — what the page structure must support to make that story work.

### Section 3 — Information architecture

Define the page structure. The default proposal (subject to wireframe alternatives):

```
┌─────────────────────────────────────────────────────────────────┐
│  Header                                                          │
│    ‣ owlcompare logo/wordmark                                    │
│    ‣ Title: "Diff: source_A vs source_B"                        │
│    ‣ Status badge: "🔴 1 breaking change" or "🟢 No breaking"   │
│    ‣ Toolbar: download JSON, copy link, theme toggle             │
├─────────────────────────────────────────────────────────────────┤
│  Summary strip (sticky)                                          │
│    Breaking: 1  ·  Additive: 1  ·  Non-breaking: 1  ·  Info: 2  │
├─────────────────────────────────────────────────────────────────┤
│  Main content (scrollable)                                       │
│                                                                  │
│    Section: Renames (always first if present)                    │
│    Section: Breaking changes                                     │
│    Section: Other changes                                        │
│    Section: Unexplained Layer 0 (collapsed by default)           │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Sidebar (optional, hidden on narrow screens)                    │
│    ‣ Filter: by severity                                         │
│    ‣ Filter: by entity kind                                      │
│    ‣ Filter: by namespace                                        │
│    ‣ Search: free text                                           │
├─────────────────────────────────────────────────────────────────┤
│  Footer                                                          │
│    ‣ Generated by owlcompare X.Y.Z · Schema link · GitHub link  │
└─────────────────────────────────────────────────────────────────┘
```

Navigation model: **single-page, scroll-anchored**. No tabs, no SPA routing. Each section has a stable ID; the sidebar (when present) navigates via fragment links. The whole document is one scrollable view, which keeps "Ctrl-F" useful and works in any browser context (including when the file is opened from email or saved locally).

Document the IA decisions:

- **Why single-page (not multi-tab)?** A user pasting into an email or attaching to a PR expects one document. Tabs imply state that doesn't survive saving as a file or sharing.
- **Why scroll-anchored (not SPA)?** Files-as-reports must be self-contained. SPA routing inside a single HTML file is fragile across browsers and breaks Ctrl-F.
- **Why severity-grouped (not entity-grouped)?** The user stories overwhelmingly support "what's broken" as the primary question; entity-centric views are secondary use cases addressed by the sidebar filter.
- **Why progressively disclosed (not paginated)?** A typical real-world diff has dozens to a few hundred changes. Paginating splits context across pages; progressive disclosure (sections collapse/expand) keeps everything searchable while managing visual weight.

### Section 4 — Three competing wireframes

Produce three distinct visual approaches. The goal is not "three slight variants" but "three meaningfully different bets" so we can compare tradeoffs.

**Wireframe A — Card-based ("Notion style").** Each change is a card with a clear hierarchy of subject, kind, severity, and expandable details. Cards have generous whitespace. Severity is shown as a left-edge color stripe. Filters in a left sidebar.

**Wireframe B — Table-dense ("GitHub style").** A single dense table with sortable columns (severity, kind, subject, summary). One row per change. Click a row to expand inline detail. Severity as a colored cell. Sticky header. No sidebar; filters via a top toolbar.

**Wireframe C — Narrative ("blog post style").** Severity-grouped sections with prose-like headings ("3 breaking changes"). Each change is a paragraph or two, not a structured card. Restriction changes are rendered as nearly-readable English. Footnote-style for technical detail. No filters. Optimized for the "reviewer skim" user story above all.

For each wireframe:
- One ASCII or simple text mockup showing the key page
- Strengths (which user stories does it serve best?)
- Weaknesses (which does it serve poorly?)
- Implementation cost estimate (rough: hours for Component 17)

### Section 5 — Chosen wireframe + rationale

Pick one. Write the rationale honestly: "We chose B because [user stories X, Y, Z] are best served and the tradeoff against story W is acceptable because [reason]." If the choice is close, say so.

The chosen wireframe becomes the spec input for Component 17.

### Section 6 — Design tokens

The visual constants. All values explicit; no "or thereabouts."

**Typography:**
- Body font: system font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`). System fonts because the report must be self-contained — no remote font loading.
- Code font: `ui-monospace, "SF Mono", Menlo, Consolas, monospace`. For IRIs and triples.
- Scale: 14px base, 1.5 line-height, sizes at 12 (caption), 14 (body), 18 (subheading), 24 (section), 32 (page title).

**Spacing:**
- Base unit: 4px.
- Scale: 4, 8, 12, 16, 24, 32, 48, 64.
- Section padding: 24px.
- Card padding: 16px.
- Inline gap: 8px.

**Color (light theme default; dark theme as optional toggle):**

Severity colors must work in both themes and be distinguishable by colorblind users.

Light theme:
- Background: `#ffffff`
- Surface: `#f6f8fa`
- Border: `#d0d7de`
- Text primary: `#1f2328`
- Text muted: `#656d76`
- Severity breaking: `#cf222e` (red)
- Severity non_breaking: `#bf8700` (amber)
- Severity additive: `#1a7f37` (green)
- Severity info: `#656d76` (muted gray)
- Severity rename: `#0969da` (blue)

Dark theme equivalents, with adjusted contrast.

Each color choice includes its WCAG contrast ratio vs. background. Minimum AA (4.5:1) for body text, AAA (7:1) for severity badges.

**Borders, radius, shadows:**
- Border radius: 6px (consistent across all surfaces).
- Shadows: minimal — only on sticky elements.

### Section 7 — UI primitives

The reusable components, each described in prose with semantic meaning. No CSS yet; that's Component 17.

- **`Badge`** — small inline element showing a single label with severity color. Used for severity tags, kind labels.
- **`Card`** — a bordered container with padding and a colored edge stripe indicating severity. Holds one change.
- **`CollapsibleSection`** — a heading with a chevron; clicking expands/collapses the children. Used for severity groups, Layer 0 unexplained, change details.
- **`IRIChip`** — a code-styled inline element showing an IRI (full or prefixed). Hovering shows the full IRI in a title tooltip.
- **`ArrowChange`** — the `before → after` notation for cardinality changes, label changes, etc. Visually distinct.
- **`EvidenceList`** — for renames: a small bulleted list of "matching label X", "shared parent Y", etc.
- **`StatusBadge`** — the page-level summary badge ("🔴 1 breaking change") in the header.
- **`Toolbar`** — the top-right button cluster: download JSON, copy link, theme toggle.

Each gets a one-paragraph description, plus an ASCII sketch of its visual treatment, plus the data it consumes from the JSON.

### Section 8 — First-paint requirements

What must be in the DOM before any JavaScript runs:

- The header with title and status badge
- The summary strip with counts
- All section headings
- The first 5 changes in each section
- The footer

What can wait for JS:
- The toolbar's interactive buttons (functional after JS)
- Collapsible state toggling
- Filter and search behavior
- Theme toggle
- Hover tooltips

Goal: even with JS disabled, the report is *readable*. Interactive features degrade gracefully.

This is a hard requirement because:
- Some corporate environments disable JS in HTML attachments
- Email clients may strip JS
- The fallback case has to look fine, not broken

### Section 9 — Accessibility

The non-negotiables:

- All severity indicators include text labels in addition to color
- Color contrast meets WCAG AA minimum, AAA for badges
- Keyboard navigation: Tab through interactive elements, Enter/Space to activate, Esc to close expanded sections
- Screen reader landmarks: `<header>`, `<main>`, `<nav>`, `<footer>`, each with appropriate ARIA labels
- Focus indicators visible (not removed via `outline: none`)
- Form-like controls (filters, search) have associated labels
- Images and icons have alt text or aria-hidden if decorative

A pre-launch checklist:
- [ ] WCAG 2.1 AA conformance (verify with automated tool: axe-core)
- [ ] Tested with keyboard-only navigation
- [ ] Tested with NVDA (Windows) or VoiceOver (macOS)
- [ ] Tested with browser zoom at 200%
- [ ] Tested with system "reduce motion" preference enabled

### Section 10 — Browser support

Targets:
- Chromium-based browsers (Chrome, Edge): last 2 versions
- Firefox: last 2 versions
- Safari: last 2 versions
- No IE11, no Edge Legacy

CSS features we can use:
- CSS custom properties (variables)
- CSS Grid and Flexbox
- `:has()` and `:is()` selectors (for advanced cases; with fallback)
- CSS nesting
- Container queries (only with fallback)

JS features we can use:
- ES2022 features
- Standard DOM APIs
- No build step (Component 17 will write JS that runs directly in the browser)

What's banned:
- Web Components / custom elements (overkill)
- IndexedDB or localStorage (single-document state is sufficient)
- Web fonts loaded from CDN (must be self-contained)
- Any external HTTP request from the rendered report

Document each decision with a one-sentence rationale.

## CLI integration

None. Component 16 produces no executable code.

## Edge cases & failure modes

- **The wireframe alternatives are too similar.** If A, B, C are slight variations of the same idea, redo them with more meaningful diversity. Three near-identical options provide no decision value.
- **The chosen wireframe is impossible to implement self-contained.** If the design requires complex JS frameworks or build steps, revise. Self-contained single-file HTML is non-negotiable.
- **The content inventory misses fields.** Cross-check against the JSON schema (`docs/schema/diff-result.schema.json`). Every field in the schema must appear somewhere in the content inventory (tier 1, 2, or 3, but somewhere).
- **A user story implies a navigation pattern not in the IA.** Either expand the IA to support it or revise the user story to fit. Don't ship a brief where stories and IA contradict.

## Open questions

- [ ] **Q1:** Should the design include a dark theme from the start, or only a light theme with dark as v2?
  **Proposed:** Both themes from the start. Dark mode is now common-enough that shipping without it feels dated. The implementation cost is small if the design tokens are set up correctly (CSS custom properties keyed by `prefers-color-scheme`).

- [ ] **Q2:** Should the design include the filter sidebar from the start, or only the main scrolling view (with filters deferred to v1.1)?
  **Proposed:** Main scrolling view in v1; filter sidebar is v1.1. The filter sidebar adds significant implementation complexity and benefits only the deeper user stories (integrator deep-dive, architect's audit). The reviewer skim and CI debugger stories don't need filters. Ship the core experience first.

- [ ] **Q3:** Should the design support multiple visual themes (e.g., a "presentation mode" with larger text for screen-sharing)?
  **Proposed:** No, only the standard view in v1. Visual theme proliferation is a slippery slope. The light/dark toggle (Q1) is sufficient. Larger text is what browser zoom is for.

If you have a preference, override before working through the artifacts; otherwise proceed with the proposed answers.

## Acceptance criteria

The component is "done" when:

- [ ] All 10 design artifact files exist in `docs/design/`
- [ ] The content inventory covers every field in the JSON schema
- [ ] There are at least 3 named user stories with implications
- [ ] The IA addresses each user story
- [ ] Three meaningfully different wireframes exist in `WIREFRAMES/`
- [ ] One wireframe is chosen, with rationale
- [ ] Design tokens are explicit (no "approximately X" — every value is final)
- [ ] At least 5 UI primitives are described in `UI_PRIMITIVES.md`
- [ ] First-paint requirements are clear
- [ ] Accessibility checklist exists
- [ ] Browser support policy is documented
- [ ] `docs/ROADMAP.md` ticks Component 16

There are no automated tests. The artifact is documentation, not code. Review is manual: a fresh reader should be able to read the design brief and predict what Component 17 will look like.

## Out of scope (deliberately)

- Any HTML, CSS, or JavaScript code — that's all Component 17.
- Pixel-perfect mockups in Figma/Sketch. ASCII or simple text mockups are sufficient.
- Animation specs — animations are decorations; if they appear in Component 17, they're additive.
- Print stylesheet — defer to v2 if there's demand.
- A formal design system (Storybook, etc.) — overkill for a single report.
- Mobile-specific design — defer. The HTML report is primarily viewed on desktop in PR review contexts.

## References

- `docs/PROJECT_BRIEF.md` § Non-negotiables (the "beautiful and fast" requirement)
- `docs/ARCHITECTURE.md` § Report Renderers
- `docs/schema/diff-result.schema.json` (the data we're rendering)
- The existing terminal renderer (`_render_diff.py`) and Markdown renderer (`markdown_report.py`) for reference patterns
