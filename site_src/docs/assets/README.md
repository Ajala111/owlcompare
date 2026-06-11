# Screenshot assets

This directory holds the images and styles that the documentation site and the
custom landing page reference. MkDocs copies everything here to `site/assets/`
during the build (it lives inside `docs_dir`, so the theme can resolve `logo`,
`favicon`, and `extra_css`, and the landing page can resolve the screenshots at
`assets/…`).

## Authored, final assets

| File | Used by | Notes |
|------|---------|-------|
| `logo.svg` | Material header (`theme.logo`) | White owl wordmark; reads on the indigo bar. |
| `favicon.svg` | Browser tab (`theme.favicon`) | Indigo square owl glyph. |
| `overrides.css` | Material (`extra_css`) | Theme customizations (severity palette, spacing). |

> **Why SVG for the logo/favicon?** They are text (so they live happily in git
> and can be authored from a code session), scale crisply, and are supported as
> favicons by every browser owlcompare targets.

## Screenshots

The landing page references two screenshot files:

- `screenshot-html.png` — the HTML report rendered by `owlcompare diff --format html`
- `screenshot-pr.png` — the Markdown report rendered as a GitHub PR comment

Both ship with placeholder PNGs in the initial repo. To replace with real
screenshots:

### screenshot-html.png (recommended dimensions: 1440×760 or close)

1. Run: `uv run python -m owlcompare diff tests/fixtures/sample/sample_v1.ttl tests/fixtures/sample/sample_v2.ttl --format html --out /tmp/screenshot.html`
2. Open `/tmp/screenshot.html` in Chrome
3. F12 → Ctrl+Shift+M → set viewport to 1440 × 900
4. DevTools ⋮ menu → "Capture full size screenshot"
5. Save as `site_src/docs/assets/screenshot-html.png`, overwriting the placeholder
6. Delete `/tmp/screenshot.html`
7. Rebuild: `uv run mkdocs build --strict` — confirm the landing page shows the new screenshot

### screenshot-pr.png (recommended dimensions: 1200×400 or close)

Option A (authentic): Paste the markdown into a draft GitHub PR comment in any
repo you own, screenshot the rendered comment, save as
`site_src/docs/assets/screenshot-pr.png`.

Option B (faster): Open a Markdown previewer (PyCharm/VS Code), render the
markdown, screenshot the preview.

Generate the source markdown:
`uv run python -m owlcompare diff tests/fixtures/sample/sample_v1.ttl tests/fixtures/sample/sample_v2.ttl --format markdown --out /tmp/pr.md`

Regenerate both whenever the HTML or Markdown rendering changes materially
(a UI revision, a new section). There is no automated drift detection — this
note is the reminder. The contributing guide repeats it.
