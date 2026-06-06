# Component 17: HTML Report Implementation

## Identity

- **Component number:** 17
- **Name:** HTML report implementation
- **Module paths:**
  - `src/owlcompare/report/html_report.py` — the renderer
  - `src/owlcompare/report/_html_components.py` — Python functions for each UI primitive
  - `src/owlcompare/report/_html_assets/` — bundled static asset strings (CSS, JS) inlined at render time
- **Roadmap phase:** Phase 4 (fourth component)
- **Depends on components:**
  - 14 (JSON schema — defines available data)
  - 15 (Markdown report — sets a precedent for the renderer interface)
  - 16 (HTML design brief — implementing against this)
  - 12.5 (anonymous structure decoding — ensures rendered data is structured, not `_list:` noise)
  - 06–11 (all the diff slices whose changes get rendered)
- **Depended on by (planned):** 19 (GitHub Action — generates and uploads HTML reports), 21 (flagship ERA demo — the visible deliverable)

## Purpose

Produce a self-contained, single-file HTML report of a `DiffResult` per the design brief in `docs/design/`. The report is the project's most user-visible deliverable — a non-technical decision-maker should be able to open the report and understand what changed without reading documentation.

What would break if we removed it: every project review, every demo, every "show this to your team" moment would have to be done through terminal output or Markdown in a PR comment. The project would remain technically excellent and look like 2009.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Diff result | `DiffResult` | Orchestrator output | Final: severity-refined, rename-consolidated, anonymous-structure-decoded |
| Snapshot metadata | from `result.a`, `result.b` | Source identification | Path/URL strings |
| Options | `HtmlOptions` | Optional | Theme default, embed JSON, etc. |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| HTML document | `str` | CLI stdout / `--out` file | UTF-8, self-contained, valid HTML5 |

## Public API

```python
# src/owlcompare/report/html_report.py

from dataclasses import dataclass
from typing import Literal
from .._common import DiffResult


@dataclass(frozen=True, slots=True)
class HtmlOptions:
    """Configuration for HTML rendering."""
    default_theme: Literal["light", "dark", "auto"] = "auto"  # 'auto' respects prefers-color-scheme
    embed_json: bool = True              # If True, embeds the raw JSON in a hidden block for download
    include_footer: bool = True
    title_override: str | None = None    # If set, replaces the default page title
    inline_svg_logo: bool = True         # Inline owlcompare wordmark


def render(
    result: DiffResult,
    options: HtmlOptions | None = None,
) -> str:
    """Render a DiffResult as a self-contained HTML document.

    Returns the full HTML5 document as a string. No external dependencies;
    valid for offline viewing, email attachment, and archival.

    Implements the design brief in docs/design/. Design changes require
    updating that brief, not this implementation.
    """
```

## CLI integration

Extend `--format` to include `html`:

```
owlcompare diff [OPTIONS] ONTOLOGY_A ONTOLOGY_B

  --format [json|text|markdown|html]    Output format
  --out PATH                            Write output to file instead of stdout
  --html-theme [light|dark|auto]        Default theme (default: auto)
  --no-embed-json                       Don't embed the JSON payload in the HTML
```

When `--format html` is set, render with `html_report.render()` and write to stdout (default) or `--out PATH`.

A typical workflow:
```bash
owlcompare diff a.ttl b.ttl --format html --out report.html
open report.html
```

The output file must be openable directly in a browser without a web server.

## Internal design

### Document structure

The rendered document follows this exact skeleton (informed by Component 16's chosen wireframe — card-based, single-page, scroll-anchored):

```html
<!DOCTYPE html>
<html lang="en" data-theme-default="auto">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>{inlined CSS from _html_assets/styles.css}</style>
</head>
<body>
  <header class="report-header">
    <div class="header-left">
      {inline SVG logo} <span class="wordmark">owlcompare</span>
    </div>
    <div class="header-center">
      <h1 class="report-title">Diff: <code>{source_a}</code> vs <code>{source_b}</code></h1>
      <div class="status-badge severity-{worst_severity}">
        {status_icon} {status_text}
      </div>
    </div>
    <div class="header-right toolbar">
      <button class="toolbar-btn" data-action="download-json" aria-label="Download JSON">
        ⬇ JSON
      </button>
      <button class="toolbar-btn" data-action="copy-link" aria-label="Copy link">
        🔗 Copy link
      </button>
      <button class="toolbar-btn" data-action="theme-toggle" aria-label="Toggle theme">
        🌓
      </button>
    </div>
  </header>

  <div class="summary-strip" role="region" aria-label="Change counts by severity">
    <span class="count count-breaking">Breaking: <strong>{n}</strong></span>
    <span class="count count-non-breaking">Non-breaking: <strong>{n}</strong></span>
    <span class="count count-additive">Additive: <strong>{n}</strong></span>
    <span class="count count-info">Info: <strong>{n}</strong></span>
    <span class="count count-renames">Renames: <strong>{n}</strong></span>
  </div>

  <main class="report-main">
    {renames_section}
    {breaking_section}
    {other_changes_section}
    {unexplained_layer0_section}
  </main>

  <footer class="report-footer">
    <p>Generated by <a href="https://github.com/.../owlcompare">owlcompare</a> {version}
       on {timestamp} ·
       <a href="#" data-action="view-schema">Schema</a> ·
       <a href="#" data-action="view-json">View JSON</a></p>
  </footer>

  <!-- Hidden JSON payload for download -->
  {if embed_json}
  <script id="diff-json" type="application/json">{json_payload}</script>
  {endif}

  <script>{inlined JS from _html_assets/interactive.js}</script>
</body>
</html>
```

Each `{section}` is built from the Change list using the per-kind templates defined below.

### Per-section rendering

Each section is rendered as:

```html
<section class="change-section section-{severity-or-kind-class}" id="section-{anchor-id}">
  <header class="section-header">
    <h2 class="section-title">{section_title}</h2>
    <span class="section-count">{count}</span>
    <button class="section-toggle" aria-expanded="true" aria-controls="section-{anchor-id}-body">
      <span class="chevron"></span>
    </button>
  </header>
  <div class="section-body" id="section-{anchor-id}-body">
    {change_cards}
  </div>
</section>
```

The toggle button collapses the body (animation in CSS; state in `aria-expanded` and a `data-collapsed` attribute). JavaScript adds the click handler; without JS, all sections are expanded.

### Per-change card rendering

Each change renders as one card following Component 16's Wireframe A (card-based):

```html
<article class="change-card severity-{severity}" data-change-id="{change_id}" data-kind="{kind}" data-severity="{severity}">
  <div class="card-stripe" aria-hidden="true"></div>
  <div class="card-body">
    <header class="card-header">
      <span class="card-badge severity-{severity}">{severity_label}</span>
      <h3 class="card-title">{kind_pretty_name}</h3>
      <code class="card-subject">{subject_iri_short}</code>
    </header>
    <div class="card-summary">{rendered_summary}</div>
    <details class="card-details">
      <summary class="card-details-toggle">Show details</summary>
      <div class="card-details-body">
        {details_table}
      </div>
    </details>
  </div>
</article>
```

The card stripe is a 4px colored left edge using the severity color. The card body has the change information.

`{rendered_summary}` uses the same per-kind template approach as Component 15's Markdown renderer, but with HTML markup:
- IRIs become `<code class="iri">era:Track</code>` (clickable to show full IRI in a tooltip)
- Arrows become `<span class="arrow">→</span>`
- Before/after values become `<del>{before}</del> <span class="arrow">→</span> <ins>{after}</ins>`
- Restriction expressions become `<code class="restriction">era:hasMaxSpeed max 1 → max 2</code>`

`{details_table}` is a key-value rendering of the change's `details` dict:

```html
<dl class="details-list">
  <dt>Change ID</dt><dd><code>{change_id}</code></dd>
  <dt>Entity IRI</dt><dd><code>{full_iri}</code></dd>
  <dt>Kind</dt><dd><code>{kind}</code></dd>
  <!-- ...more entries per kind -->
</dl>
```

Details are collapsed by default (the `<details>` element). They expand on click. They use semantic HTML so screen readers announce them as definition lists.

### Per-kind summary templates

The HTML summary for each kind mirrors the Markdown templates from Component 15 but with richer markup. Each kind has a dedicated function in `_html_components.py`:

```python
def render_change_summary(change: dict) -> str:
    """Dispatch to the per-kind renderer."""
    kind = change["kind"]
    if kind == "class_added":
        return _render_class_added(change)
    elif kind == "class_renamed":
        return _render_class_renamed(change)
    # ...etc for all 50+ kinds
    else:
        # Forward-compatible fallback: render change.summary plain
        return f'<p>{escape_html(change["summary"])}</p>'
```

The fallback is critical: when v1.1 adds a new kind, the v1 renderer doesn't break — it falls back to the plain summary text from the producer.

### CSS architecture

CSS lives in `src/owlcompare/report/_html_assets/styles.css` as a single file, loaded by the Python renderer and inlined into the `<style>` block.

Structure:
1. **Reset / normalize** — minimal CSS reset (margins, box-sizing).
2. **Design tokens** — CSS custom properties keyed by `:root` (light) and `[data-theme="dark"]` (dark). One source of truth for every color, spacing, typography value.
3. **Theme switching** — `prefers-color-scheme` media query at the top; explicit override via `[data-theme]` attribute on `<html>` set by JS.
4. **Layout** — header, summary strip, main, footer. Flexbox-based; no grid for v1 (simpler fallbacks).
5. **Components** — section, card, badge, IRI chip, arrow, details list. Each named class scoped.
6. **Interactive states** — `:hover`, `:focus-visible`, `:active`, plus the JS-toggled `[data-collapsed]` and `[data-theme]`.
7. **Print styles** — `@media print` ensuring the report prints sensibly (no toolbar, no collapsed sections — all expanded).
8. **Reduced motion** — `@media (prefers-reduced-motion: reduce)` removing transitions.

The CSS file is committed to the repo as a source file, formatted readably. The Python renderer reads it via `importlib.resources` and inlines it. The file should not exceed ~600 lines.

### JavaScript architecture

JS lives in `src/owlcompare/report/_html_assets/interactive.js` and provides three behaviors:

1. **Section toggling** — clicking a section header toggles `aria-expanded` and `data-collapsed`. CSS handles the visual collapse via `max-height` transitions.
2. **Theme toggle** — clicking the theme button cycles `auto → light → dark → auto`, setting `[data-theme]` on `<html>` and persisting to `localStorage` (the only allowed browser storage usage; document a fallback if storage is blocked).
3. **JSON download** — clicking "JSON" downloads the embedded `<script id="diff-json">` content as a `.json` file using a Blob URL.
4. **Copy link** — clicking "Copy link" copies the page's current URL (or `window.location.href`) to the clipboard.

Total JS code should be under ~200 lines of vanilla ES2022. No frameworks, no build step, no transpilation.

### First-paint (no-JS) behavior

Without JavaScript:
- All sections are expanded (the default state of `aria-expanded="true"`)
- Theme is whatever `prefers-color-scheme` evaluates to (no toggle available)
- Toolbar buttons are visible but non-functional; document this behavior with a `<noscript>` block hidden from JS-enabled users
- The JSON `<script>` tag's content is not accessible via download button, but is still readable in browser dev tools
- `<details>` elements work via native browser support (no JS needed)

The full document is readable and informative without JS. This is the design brief's hard requirement.

### Severity to CSS class mapping

| Severity | CSS class | Color variable |
|----------|-----------|----------------|
| breaking | `severity-breaking` | `--color-breaking` (#cf222e light, adjusted for dark) |
| non_breaking | `severity-non-breaking` | `--color-non-breaking` (#9a6700 — per Component 16's WCAG-corrected value) |
| additive | `severity-additive` | `--color-additive` (#1a7f37) |
| info | `severity-info` | `--color-info` (#656d76) |
| rename | `severity-rename` | `--color-rename` (#0969da) |

The badge construction (per Component 16's Deviation 2) uses these as the *stripe* and *icon* colors. Badge text is dark on a light tinted background (the tint is a `color-mix()` of the hue with the background at ~10% saturation).

### Section ordering and severity sort

Sections appear in this order (omitted if empty):

1. **Renames** — even though renames are `info` severity, they come first because they're the most informative pattern when present.
2. **Breaking changes** — all changes with severity `breaking`.
3. **Other changes** — `non_breaking` + `additive` + `info`, grouped under one section but sorted internally by severity (non_breaking → additive → info).
4. **Unexplained Layer 0** — only if non-zero. Collapsed by default.

Within each section, cards are sorted by:
1. Subject IRI (for visual grouping of related changes)
2. Kind (alphabetical, as a stable tiebreaker)

### Status badge logic

The header's status badge reflects the *overall verdict* in one phrase:

| Condition | Status badge |
|-----------|--------------|
| Any breaking changes | `🔴 N breaking changes` (red) |
| No breaking, total > 0 | `🟢 No breaking changes` (green) |
| Total == 0 | `⚪ No changes` (gray) |

The badge color uses the severity color of the worst severity present.

### Source rendering

The "Diff: source_a vs source_b" line in the header renders source paths/URLs as truncated text with a tooltip showing the full string:

```html
<code class="source-name" title="{full_path}">{basename}</code>
```

If the source is a URL, the basename is the last path segment. If it's a local path, the basename is the filename only.

## Edge cases & failure modes

- **Empty diff** (no changes): renders the header, summary strip ("No changes"), an empty main, and the footer. No sections. The status badge says "No changes."
- **Very long IRIs** (>80 chars): truncate in the card title with ellipsis; full IRI in `title` attribute and in the details list.
- **Labels containing HTML-like text** (`<script>`, `&amp;`): escape all user-supplied strings via a centralized `escape_html()` helper. Verified by tests with malicious-looking labels.
- **No source identifiers** (sources are `None`): render "Source A" / "Source B" placeholders.
- **Identical sources** (user diffed a file against itself): render both names; status badge shows "No changes." Document as a known harmless edge case.
- **Changes referencing entities not in B** (after-the-fact rename references): use whatever IRI is on the change; don't try to resolve.
- **Restriction summaries containing `<`, `>`, `&`**: HTML-escape inside the restriction code span. The visual representation uses entity-encoded characters where necessary.
- **Very large diffs** (>1000 changes): render every change; performance comes from native scrolling. No pagination. Test with a 2000-change synthetic diff to verify the document size is manageable (<5MB).
- **Browser without `<details>` support** (none in our supported set, but defensive): the content is still visible as a fallback.
- **`localStorage` blocked by browser policy:** the theme toggle still works for the current session; it just doesn't persist. Catch the exception silently.
- **`navigator.clipboard` unavailable** (older browsers, file:// protocol restrictions): the copy-link button shows a temporary "Not supported in this context" message.
- **The JSON payload exceeds typical browser script-tag limits** (multi-megabyte payloads): tested. Modern browsers handle multi-MB inline JSON fine. If a future limit is hit, we'd write to a sibling file; out of scope for v1.

## Dependencies to add

None for the runtime. For development:

- Optionally, a CSS linter (`stylelint`) — defer to v1.1; not in v1.
- Optionally, an HTML validator — defer.

The renderer is pure Python writing strings. No new runtime dependencies.

## Acceptance tests

Located in `tests/unit/test_html_report.py` (new), extensions to `tests/unit/test_cli_diff.py`, extensions to `tests/integration/test_diff_integration.py`.

### Fixtures to add (`tests/fixtures/html/`)

Goldens — captured HTML outputs, structurally compared (not byte-for-byte, because attribute ordering and whitespace are flexible). Test framework uses an HTML diffing approach: parse expected and actual as HTML5, compare semantic equivalence ignoring insignificant whitespace.

For golden comparison, use `beautifulsoup4` from dev dependencies (small, well-known, MIT). Add as test-only.

Or: use string equality but normalize the renderer's output deterministically (sort attributes, normalize whitespace) and assert string equality against carefully-generated goldens. **Recommendation: deterministic string output + string-equality goldens.** Simpler, no new dependency. Document the determinism requirements (sorted attributes, fixed indentation).

Fixtures:
- `empty_diff.html` — diff with no changes.
- `era_evolution.html` — the canonical 5-change result.
- `era_renames.html` — rename-heavy diff.
- `era_axleSpacingDistance_domain_union.html` — Component 12.5's flagship case.
- `breaking_only.html` — only breaking changes; tests the "no Other" branch.
- `large_diff.html` — 100+ changes synthetic fixture.
- `escaping_specials.html` — labels with `<script>`, `&`, `"`, quotes verifying HTML escaping.

### Test list

**`tests/unit/test_html_report.py`:**

- [ ] `test_render_returns_valid_html5_document`
- [ ] `test_render_includes_doctype`
- [ ] `test_render_includes_charset_utf8`
- [ ] `test_render_includes_viewport_meta`
- [ ] `test_render_inlines_full_css`
- [ ] `test_render_inlines_full_js`
- [ ] `test_render_no_external_resources_loaded` — assert no `<link>`, no `<script src=>`, no `<img src=>` referencing external URLs
- [ ] `test_render_title_includes_severity_summary`
- [ ] `test_render_status_badge_breaking_when_breaking_present`
- [ ] `test_render_status_badge_green_when_no_breaking`
- [ ] `test_render_status_badge_no_changes_when_empty`
- [ ] `test_render_summary_strip_has_count_for_each_severity`
- [ ] `test_render_summary_strip_omits_zero_counts` — or shows them as muted (decide; spec implies show all)
- [ ] `test_render_renames_section_appears_first_when_renames_present`
- [ ] `test_render_breaking_section_omitted_when_no_breaking`
- [ ] `test_render_other_changes_section_groups_non_breaking_additive_info`
- [ ] `test_render_unexplained_layer0_section_collapsed_by_default`
- [ ] `test_render_card_has_correct_severity_class`
- [ ] `test_render_card_includes_stripe_div`
- [ ] `test_render_card_includes_change_id_data_attribute`
- [ ] `test_render_card_includes_kind_data_attribute`
- [ ] `test_render_card_details_collapsed_by_default`
- [ ] `test_render_iri_uses_prefixed_form_when_known`
- [ ] `test_render_arrow_change_uses_del_and_ins_tags`
- [ ] `test_render_class_renamed_includes_confidence_evidence`
- [ ] `test_render_restriction_changed_includes_readable_form`
- [ ] `test_render_domain_union_changed_includes_member_diff`
- [ ] `test_render_datatype_facet_changed_includes_facet_diff`
- [ ] `test_render_replaced_by_set_includes_target`
- [ ] `test_render_escapes_html_in_labels` — assert `<script>` rendered as `&lt;script&gt;`
- [ ] `test_render_escapes_ampersand_in_labels`
- [ ] `test_render_escapes_quotes_in_attributes`
- [ ] `test_render_embeds_json_payload_when_option_set`
- [ ] `test_render_does_not_embed_json_when_option_unset`
- [ ] `test_render_footer_includes_version`
- [ ] `test_render_footer_includes_timestamp`
- [ ] `test_render_omits_footer_when_disabled`
- [ ] `test_render_unknown_kind_falls_back_to_summary_text`
- [ ] `test_render_output_is_deterministic` — render twice, assert byte-equal
- [ ] `test_render_status_badge_uses_aria_label`
- [ ] `test_render_sections_have_aria_expanded_initial_true`
- [ ] `test_render_toolbar_buttons_have_aria_labels`
- [ ] `test_render_html_lang_attribute_set_to_en`
- [ ] `test_render_no_inline_style_attributes` — all styles in the `<style>` block, not on individual elements
- [ ] `test_render_no_javascript_event_handlers_inline` — no `onclick=`, etc.; JS handlers attached programmatically
- [ ] `test_render_document_size_under_5mb_for_2000_changes`
- [ ] `test_render_default_theme_attribute_set_to_auto`
- [ ] `test_render_default_theme_attribute_set_to_light_when_option_light`
- [ ] `test_render_default_theme_attribute_set_to_dark_when_option_dark`
- [ ] `test_render_golden_empty_diff`
- [ ] `test_render_golden_era_evolution`
- [ ] `test_render_golden_era_renames`
- [ ] `test_render_golden_era_axleSpacingDistance_domain_union`
- [ ] `test_render_golden_breaking_only`
- [ ] `test_render_golden_escaping_specials`

**`tests/unit/test_cli_diff.py` extensions:**

- [ ] `test_cli_diff_format_html_writes_html_to_stdout`
- [ ] `test_cli_diff_format_html_writes_to_out_file`
- [ ] `test_cli_diff_html_theme_light_sets_data_attribute`
- [ ] `test_cli_diff_html_theme_dark_sets_data_attribute`
- [ ] `test_cli_diff_html_theme_auto_default`
- [ ] `test_cli_diff_no_embed_json_omits_payload_script`
- [ ] `test_cli_diff_format_html_exit_code_matches_severity` — HTML rendering doesn't affect exit code

**`tests/integration/test_diff_integration.py` extensions:**

- [ ] `test_era_evolution_html_output_matches_golden`
- [ ] `test_era_axleSpacingDistance_html_renders_domain_union_cleanly` — visible verification that Component 12.5's structured data renders well in HTML

## Manual verification checklist

Beyond automated tests, a human must open the rendered HTML and verify:

- [ ] Opens cleanly in Chrome, Firefox, Safari (latest 2 versions of each)
- [ ] Renders correctly with JS disabled
- [ ] Renders correctly with `prefers-color-scheme: dark` (the dark theme is visually correct)
- [ ] Section collapse/expand works smoothly
- [ ] JSON download produces a valid JSON file
- [ ] Copy-link works
- [ ] Theme toggle cycles correctly
- [ ] Keyboard navigation works (Tab through interactive elements, Enter/Space to activate)
- [ ] WCAG AA color contrast verified with axe-core or similar tool
- [ ] Print stylesheet looks reasonable (try browser print preview)
- [ ] Document size is reasonable (~50-200KB for typical diffs)

## Out of scope (deliberately)

- A multi-page or tabbed interface (single-page per Component 16's IA decision).
- Client-side filtering or search (deferred to v1.1 per Component 16's Q2).
- Animations beyond simple transitions (`prefers-reduced-motion` is respected).
- SVG-based diagrams or charts of the change distribution.
- Bookmarklet integration or browser-extension support.
- Embedding the JSON schema inline (link to schema instead).
- A "share as URL" feature — `localStorage`-only state.
- Mobile-specific layouts beyond the responsive design tokens (defer mobile design to v1.1).
- Internationalization (English only).
- Custom theming beyond light/dark (per Component 16's Q3).
- Tests against actual browser DOMs (Selenium etc.) — out of scope; rely on string-based assertions.

## Open questions

- [ ] **Q1:** How should we handle the "embed JSON" feature when the JSON payload is very large (e.g., 50MB)? The spec defaults to embed-on; should we add a size threshold above which embed automatically disables?
  **Proposed:** Embed unconditionally. Modern browsers handle multi-MB inline JSON fine. A user with a 50MB diff is in a specialized situation; they can use `--no-embed-json` if performance bites. Don't add automatic thresholding.

- [ ] **Q2:** For the "View JSON" footer link, should it open a modal dialog showing the embedded JSON pretty-printed, or trigger the download?
  **Proposed:** Trigger the download (same action as the toolbar JSON button). A modal would require modal infrastructure (CSS, focus management, escape-key handling); download is simpler and equally useful. Document the link's behavior in the footer text.

- [ ] **Q3:** Should the per-change "details" `<details>` element start collapsed (default `<details>` behavior) or expanded?
  **Proposed:** Collapsed. The card's summary line is what users scan; details are for diving deeper on a specific change. Expanding all details by default would make the page very tall for non-trivial diffs.

If you have a preference, override before implementing.

## References

- `docs/design/` — the entire design brief (Component 16's output)
- `docs/schema/diff-result.schema.json` — the data shape
- `src/owlcompare/report/markdown_report.py` — the precedent renderer
- DD-005 (self-contained single-file HTML), DD-019 (JSON schema versioning), DD-008 (severity)
- HTML5 spec: https://html.spec.whatwg.org/
- WCAG 2.1: https://www.w3.org/TR/WCAG21/
