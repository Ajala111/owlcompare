# Accessibility

Target: **WCAG 2.1 AA** for everything, **AAA** for badge text. Accessibility is a
requirement of Component 17, verified here at design time so no colour ships that
fails.

## Non-negotiables

- Every severity indicator carries a **text label**, never colour alone — the
  `Badge` spells out `BREAKING`/`ADDITIVE`/etc. (WCAG 1.4.1 Use of Color).
- Contrast meets **AA (4.5:1)** for all text; **AAA (7:1)** for badge text.
- **Keyboard:** Tab reaches every interactive element; Enter/Space activate
  `<summary>` toggles and toolbar buttons; Esc collapses an open section.
- **Landmarks:** `<header>`, `<main>`, `<footer>` present; the v1.1 sidebar will
  add `<nav>`. Each has an `aria-label`.
- **Focus indicators** stay visible — `outline` is never set to `none` without a
  replacement of equal or greater visibility.
- **Form controls** (v1.1 filters/search) get associated `<label>`s.
- **Icons** are `aria-hidden` when decorative (the `→`, chevrons, severity dot);
  meaning is always also in text.
- **Motion:** all transitions are removed under `prefers-reduced-motion: reduce`.

## Contrast verification (light theme, vs `#ffffff`)

Computed with the WCAG relative-luminance formula
(`L = 0.2126R + 0.7152G + 0.0722B` on linearised channels;
`contrast = (L₁+0.05)/(L₂+0.05)`).

| Colour | Hex | Luminance | Contrast | AA text | AAA |
|--------|-----|-----------|----------|---------|-----|
| Text | `#1f2328` | 0.016 | **15.8:1** | ✅ | ✅ |
| Text muted | `#656d76` | 0.150 | **5.2:1** | ✅ | ✗ |
| Breaking | `#cf222e` | 0.146 | **5.4:1** | ✅ | ✗ |
| Non-breaking | `#9a6700` | 0.166 | **4.9:1** | ✅ | ✗ |
| Additive | `#1a7f37` | 0.157 | **5.1:1** | ✅ | ✗ |
| Info | `#656d76` | 0.150 | **5.2:1** | ✅ | ✗ |
| Rename | `#0969da` | 0.152 | **5.2:1** | ✅ | ✗ |

### The one colour that was changed

The spec proposed `#bf8700` for non-breaking. Its luminance is 0.284, giving only
**3.1:1** on white — it **fails AA for text.** Following the spec's own rule ("if a
color fails AA, change it"), non-breaking is darkened to **`#9a6700`** (4.9:1,
same amber family). This is the single token deviation from the spec's proposed
palette.

### How badges reach AAA

No single severity hue reaches 7:1 on white without becoming an indistinct
near-black. Instead, badge *text* uses `--text` (`#1f2328`) on a light tint of the
hue; that text is **≥13.7:1** on every tint — comfortably AAA. The hue itself only
ever carries the stripe and icon, which are non-text graphics needing **3:1**
(WCAG 1.4.11), a bar every hue clears. AAA-for-badges is met by the readable
element, honestly, without sacrificing hue distinction.

### Dark theme

Dark severity hues (`DESIGN_TOKENS.md`) are raised against `#0d1117`; all clear
AA, most clear AAA. Worked example: breaking `#ff7b72` (L≈0.366) on `#0d1117`
(L≈0.0055) = **7.5:1**.

## Colour-blind safety

Severity is never distinguished by hue alone: each change carries a text badge,
and the five hues (red/amber/green/gray/blue) are also separated by lightness and
by their always-present labels, so red–green confusion does not lose information.

## Pre-launch checklist (Component 17 executes)

- [ ] WCAG 2.1 AA verified with axe-core on a representative report.
- [ ] Keyboard-only navigation walked end to end (Tab/Enter/Space/Esc).
- [ ] Screen-reader pass with NVDA (Windows) or VoiceOver (macOS).
- [ ] Browser zoom to 200% with no loss of content or horizontal scroll.
- [ ] `prefers-reduced-motion: reduce` confirmed to suppress all transitions.
