# First Paint

The report must be *readable with JavaScript disabled*. This is a hard
requirement, not a nicety: corporate mail gateways and some browsers strip or
block JS in HTML attachments, and an archived `report.html` opened years later
must still render. JS only ever *enhances*; it never *enables* reading.

## In the DOM before any JS runs

- The `<header>`: wordmark, title (`source_A → source_B`), and the `StatusBadge`.
- The sticky summary strip with all severity counts.
- Every section heading (`Renames`, `Breaking`, `Other`, `Unexplained Layer 0`).
- The first **5 changes in each section**, fully rendered with their headline and
  subject. (Sections cap at 50 rendered changes total; "…and N more" is static
  text, not a JS-loaded continuation.)
- Each card's expandable body is present in the DOM and openable via native
  `<details>` — no JS needed to read detail.
- The `<footer>`.

## May wait for JS (graceful enhancement)

- **Copy link** button — degrades to a plain anchor / no-op label without JS.
- **Theme toggle** — `prefers-color-scheme` already picks light/dark with no JS;
  the button only adds manual override.
- **Collapse/expand animation** — `<details>` toggles structurally without JS; JS
  only adds the smooth transition and "expand all."
- **Hover tooltips beyond the native `title`** — the `title` attribute works with
  no JS.
- **Filter/search** — deferred to v1.1 anyway (Q2).

## Why `<details>` is the backbone

Native `<details>`/`<summary>` gives collapse/expand, keyboard operation, and
screen-reader semantics for free, with zero JS. Building expansion on it (rather
than JS click handlers over `display:none`) is what makes the no-JS fallback
*readable rather than broken* — the spec's stated bar. The fallback is not a
degraded mode to apologise for; it is the baseline the enhanced experience is
layered onto.

## Performance intent

"Beautiful and fast" (Project Brief non-negotiable #1) means the inlined CSS and
the static DOM paint immediately; there is no render-blocking script, no web font,
and no network request (see `BROWSER_SUPPORT.md`). First meaningful paint is
bounded by parse time of a single self-contained file, not by any fetch.
