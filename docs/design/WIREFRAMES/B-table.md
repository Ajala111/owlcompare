# Wireframe B — Table-dense ("GitHub style")

One sortable table, one row per change. Severity is a coloured cell; clicking a
row expands an inline detail panel beneath it. Sticky header. Filters live in a
top toolbar, not a sidebar.

## Mockup — main view

```
┌──────────────────────────────────────────────────────────────────────┐
│ owlcompare   Diff: era-3.1.0.ttl → era-3.2.0.ttl   ● 1 breaking  [⤓][◐]│
├──────────────────────────────────────────────────────────────────────┤
│ [ all ▾ ] [ severity ▾ ] [ kind ▾ ]      🔍 filter…   5 changes shown  │
├──────────┬───────────────┬───────────────────────┬───────────────────┤
│ SEVERITY▼│ KIND          │ SUBJECT               │ SUMMARY           │  ← sticky header,
├──────────┼───────────────┼───────────────────────┼───────────────────┤     sortable
│ BREAKING │ restriction…  │ era:Platform          │ hasMaxSpeed max 1…│
│ ╞════════ expanded ═══════════════════════════════════════════════╡   │
│ │ era:hasMaxSpeed   max 1  →  max 2                                │   │
│ │ why breaking: cardinality tightened (info → breaking,            │   │
│ │               rule: cardinality-tightened)                       │   │
│ ╘══════════════════════════════════════════════════════════════════╛   │
│ RENAME   │ class_renamed │ era:Track→era:Railway…│ high confidence   │
│ ADDITIVE │ class_added   │ era:ChargingStation   │ "Charging Station"│
│ INFO     │ annotation…   │ era:Signal            │ "signal"→"Signal" │
│ INFO     │ annotation…   │ era:Platform          │ comment added     │
├──────────┴───────────────┴───────────────────────┴───────────────────┤
│ ▸ Unexplained Layer 0 changes (3)                                     │
└──────────────────────────────────────────────────────────────────────┘
```

## Strengths

- **Story 2 (deep-dive):** sort by kind/subject, scan a column, find every
  property change fast.
- **Story 5 (audit):** density makes recurring kinds visible at a glance — the
  best of the three for pattern-spotting.
- Compact: 200 changes fit in far less vertical space than cards.

## Weaknesses

- **Story 1 (skim):** a breaking row looks like every other row except for one
  coloured cell; "is this safe?" is harder to answer in 5 s.
- **Story 3 (historian):** a table reads like a spreadsheet, not a narrative;
  rename evidence is cramped.
- Restriction/annotation `before → after` forms get truncated in a fixed column.
- Sortable columns need JS; the no-JS fallback is a static, unsortable table.

## Implementation cost (Component 17)

**High — ~16–22 h.** Column sort, inline row expansion that reflows the table,
truncation/overflow handling per column, and the top filter toolbar (which would
otherwise be the deferred v1.1 sidebar) all add JS and CSS surface.
