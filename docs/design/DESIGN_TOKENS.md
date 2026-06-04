# Design Tokens

Every value here is final — no "approximately." Component 17 turns these into CSS
custom properties verbatim. Contrast ratios are computed against the token's
background per WCAG 2.1 (see `ACCESSIBILITY.md` for the worked arithmetic).

## Typography

- **Body font stack:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
  sans-serif`. System fonts only — the report is self-contained and loads no
  remote font.
- **Code font stack:** `ui-monospace, "SF Mono", Menlo, Consolas, monospace`.
  For IRIs, triples, and rule ids.
- **Base size / line-height:** 14px / 1.5.
- **Scale:** 12px caption · 14px body · 18px subheading · 24px section heading ·
  32px page title.
- **Weights:** 400 body, 600 headings and badges, 500 IRI chips.

## Spacing

- **Base unit:** 4px. **Scale:** 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64.
- **Section padding:** 24px on all sides.
- **Card padding:** 16px.
- **Inline gap** (badge↔text, icon↔label): 8px.
- **Max content width:** 960px, centred.

## Borders, radius, shadow

- **Border radius:** 6px on every surface (cards, badges, chips, buttons).
- **Border width:** 1px.
- **Severity stripe width:** 4px (the card's left edge).
- **Shadow:** none, except sticky elements: `0 1px 3px rgba(0,0,0,0.12)`.

## Color — light theme (default)

| Token | Hex | On | Contrast | Use |
|-------|-----|----|----------|-----|
| `--bg` | `#ffffff` | — | — | Page background |
| `--surface` | `#f6f8fa` | — | — | Summary strip, collapsed panels |
| `--border` | `#d0d7de` | `#ffffff` | 1.4:1 (non-text) | Hairlines |
| `--text` | `#1f2328` | `#ffffff` | **15.8:1** | Body + all badge text |
| `--text-muted` | `#656d76` | `#ffffff` | **5.2:1** | Captions, secondary IRIs |
| `--sev-breaking` | `#cf222e` | `#ffffff` | **5.4:1** | Breaking stripe / icon / text |
| `--sev-non-breaking` | `#9a6700` | `#ffffff` | **4.9:1** | Non-breaking stripe / icon / text |
| `--sev-additive` | `#1a7f37` | `#ffffff` | **5.1:1** | Additive stripe / icon / text |
| `--sev-info` | `#656d76` | `#ffffff` | **5.2:1** | Info stripe / icon / text |
| `--sev-rename` | `#0969da` | `#ffffff` | **5.2:1** | Rename stripe / icon / text |

> **Note:** `--sev-non-breaking` is `#9a6700`, **not** the `#bf8700` the spec
> proposed. `#bf8700` is only 3.1:1 on white and fails WCAG AA for text. `#9a6700`
> keeps the amber hue at 4.9:1. See the deviation note in the build summary and
> `ACCESSIBILITY.md`.

### Severity badge construction (AAA target)

Per-hue colours top out near 5:1 on white, short of the AAA 7:1 the spec wants for
badges. Rather than muddy every hue to near-black, a badge is built so its
*readable text* hits AAA while colour stays a redundant cue:

- **Badge background:** the severity hue at a light tint (`--sev-*` mixed to ~12%
  over `--bg`, e.g. breaking → `#ffebe9`).
- **Badge text:** `--text` (`#1f2328`), which is **≥13.7:1** on every tint — well
  past AAA.
- **Severity hue** carries the left stripe and the icon — non-text graphical
  elements that need only 3:1, which every hue clears.

## Color — dark theme (toggle + `prefers-color-scheme`)

| Token | Hex | On `--bg` | Contrast |
|-------|-----|-----------|----------|
| `--bg` | `#0d1117` | — | — |
| `--surface` | `#161b22` | — | — |
| `--border` | `#30363d` | `#0d1117` | non-text |
| `--text` | `#e6edf3` | `#0d1117` | 14.6:1 |
| `--text-muted` | `#8b949e` | `#0d1117` | 5.9:1 |
| `--sev-breaking` | `#ff7b72` | `#0d1117` | **7.5:1** |
| `--sev-non-breaking` | `#d29922` | `#0d1117` | 7.0:1 |
| `--sev-additive` | `#3fb950` | `#0d1117` | 7.6:1 |
| `--sev-info` | `#8b949e` | `#0d1117` | 5.9:1 |
| `--sev-rename` | `#58a6ff` | `#0d1117` | 6.7:1 |

Dark severity hues are lighter (raised against the dark ground) and all clear AA;
most clear AAA. Dark badge text is `--text` on a dark-tinted hue background.

## Motion

- One transition only: `120ms ease` on collapse/expand and theme swap. Suppressed
  entirely under `prefers-reduced-motion: reduce` (see `ACCESSIBILITY.md`).
