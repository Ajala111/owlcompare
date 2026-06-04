# UI Primitives

The reusable building blocks of the report, described semantically. No CSS — that
is Component 17. Each primitive lists what it looks like, what it means, and which
JSON data it consumes. Class names are suggestions Component 17 may adopt.

## `Badge` — `.oc-badge`

A small inline pill carrying a single label. Two uses: a **severity** badge
(`breaking`, `non-breaking`, `additive`, `info`) and a **kind** badge
(`class added`, `restriction changed`). Always shows a *text* label, never colour
alone. Background is the severity hue at a light tint; text is `--text`.

```
[ ● BREAKING ]   [ class added ]
```

**Consumes:** `change.severity`, a humanised `change.kind`.

## `Card` — `.oc-card`

A bordered container, 16px padding, 6px radius, with a 4px left **severity
stripe** in the hue. Holds exactly one change: a header row (`Badge` + kind noun +
subject `IRIChip` + expand chevron) and an expandable body. Built on
`<details>`/`<summary>` so it opens with no JS.

```
▌ [BREAKING] Restriction changed on era:Platform        (v)
▌ era:hasMaxSpeed  max 1 → max 2
▌ why breaking: …
```

**Consumes:** the whole `Change` (severity, kind, subject, summary, details,
before/after).

## `CollapsibleSection` — `.oc-section`

A heading with a chevron; clicking toggles its children. Used for the severity
groups and the "Unexplained Layer 0" block. Native `<details>`; expanded state is
DOM, not JS. The chevron rotates under `prefers-reduced-motion` only by snapping,
not animating.

```
▸ Unexplained Layer 0 changes (3)
▾ Breaking changes (1)
```

**Consumes:** a section title and its child change count.

## `IRIChip` — `.oc-iri`

A monospace inline element showing an IRI, prefixed where a binding exists
(`era:Platform`), full otherwise. The full IRI is always in a `title` tooltip and
is selectable plain text so `Ctrl-F` finds it (story 2). Never an image or
pseudo-element.

```
`era:Platform`   (title="http://data.europa.eu/949/Platform")
```

**Consumes:** any `*_iri` field plus the merged prefix map from `a`/`b`.

## `ArrowChange` — `.oc-arrow`

The `before → after` notation for cardinality, label, domain/range, and reparent
changes. The arrow `→` is decorative (`aria-hidden`); the relationship is also
conveyed by the surrounding text ("changed from … to …") for screen readers.

```
max 1  →  max 2
"signal"  →  "Signal"
```

**Consumes:** `details.before`/`details.after`, or decoded
`RestrictionDecoded`/`AnnotationValue` pairs.

## `EvidenceList` — `.oc-evidence`

A compact bulleted list under a rename, one bullet per evidence string, prefixed
by the confidence. Renders honesty: confidence is shown, never hidden (Project
Brief non-negotiable #3).

```
high confidence
 · matching label "Track"@en
 · shared parent era:Infrastructure
```

**Consumes:** `RenameDetails.confidence`, `.score`, `.evidence[]`.

## `StatusBadge` — `.oc-status`

The page-level verdict in the header: a large pill, red "N breaking changes" or
green "No breaking changes." The single most important pixel for story 1. Colour
plus an explicit count and word.

```
┏━━━━━━━━━━━━━━━━━┓     ┏━━━━━━━━━━━━━━━━━━━┓
┃ ● 1 breaking    ┃ or  ┃ ✓ No breaking     ┃
┗━━━━━━━━━━━━━━━━━┛     ┗━━━━━━━━━━━━━━━━━━━┛
```

**Consumes:** `summary.breaking`, `summary.total`.

## `Toolbar` — `.oc-toolbar`

The top-right button cluster: **Download JSON** (a data-URI link, works without
JS), **Copy link** (JS-enhanced; degrades to a plain anchor), **theme toggle**
(JS-enhanced; `prefers-color-scheme` already gives a sensible default without it).

```
[ ⤓ JSON ]  [ 🔗 Copy ]  [ ◐ Theme ]
```

**Consumes:** nothing from the diff; operates on the document itself.
