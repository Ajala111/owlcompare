# Site assets

This directory holds the images and styles that the documentation site and the
custom landing page reference. MkDocs copies everything here to `site/assets/`
during the build (it lives inside `docs_dir`, so the theme can resolve
`logo`, `favicon`, and `extra_css`).

## Authored, final assets

| File | Used by | Notes |
|------|---------|-------|
| `logo.svg` | Material header (`theme.logo`) | White owl wordmark; reads on the indigo bar. |
| `favicon.svg` | Browser tab (`theme.favicon`) | Indigo square owl glyph. |
| `overrides.css` | Material (`extra_css`) | Theme customizations (severity palette, spacing). |

> **Why SVG, not `.ico`/`.png`?** The spec sketch names `favicon.ico` and
> `.png` screenshots. We ship SVGs instead: they are text (so they live happily
> in git and can be authored from a code session), scale crisply, and are
> supported as favicons by every browser owlcompare targets. The screenshots are
> the one thing that must be captured from real output — see below.

## Placeholder assets — replace before launch

These are **grey placeholders**. They must be regenerated from real owlcompare
output before the site is announced. They are also referenced inline (as SVG)
in the landing page, so the landing page stays self-contained regardless.

| File | What it should become | How to capture |
|------|-----------------------|----------------|
| `screenshot-html.svg` | A real HTML-report screenshot (PNG) | See "Capture the HTML report" below. |
| `screenshot-pr.svg` | A real PR-comment screenshot (PNG) | See "Capture the PR comment" below. |
| `og-image.svg` | A 1200×630 social-share card (PNG) | Export the SVG, or design in any tool. |

### Capture the HTML report

The screenshots **cannot** be generated from a headless code session — they need
a real browser. Run owlcompare against the flagship fixtures and screenshot the
result:

```bash
# 1. Generate a real report (this produces HTML, not an image).
uv run python -m owlcompare diff \
  tests/fixtures/sample/sample_v1.ttl \
  tests/fixtures/sample/sample_v2.ttl \
  --format html --out tmp-report.html

# 2. Open tmp-report.html in Chrome at a 1440×900 viewport.
# 3. DevTools → Run command → "Capture full size screenshot"
#    (or screenshot the visible area). Use 2× DPI for retina sharpness.
# 4. Save it as screenshot-html.png in this directory and update the
#    references in ../../index.html and the relevant guide pages.
```

### Capture the PR comment

```bash
# 1. Render the Markdown the GitHub Action posts.
uv run python -m owlcompare diff \
  tests/fixtures/sample/sample_v1.ttl \
  tests/fixtures/sample/sample_v2.ttl \
  --format markdown --out tmp-report.md

# 2. Paste it into a draft PR comment in the owlcompare repo, submit, and
#    screenshot the rendered comment. Save as screenshot-pr.png here.
```

Regenerate both whenever the HTML or Markdown rendering changes materially
(a UI revision, a new section). There is no automated drift detection — this
note is the reminder. The contributing guide repeats it.
