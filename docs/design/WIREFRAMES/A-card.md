# Wireframe A — Card-based ("Notion style")

Each change is a self-contained card with a left-edge severity stripe. Generous
whitespace; the headline is readable closed, full detail appears on expansion.

## Mockup — main view

```
┌──────────────────────────────────────────────────────────────────────┐
│ owlcompare        Diff: era-3.1.0.ttl → era-3.2.0.ttl                  │
│                   ┏━━━━━━━━━━━━━━━━━━┓   [Download JSON] [Copy] [◐]     │
│                   ┃ ● 1 breaking     ┃                                  │
│                   ┗━━━━━━━━━━━━━━━━━━┛                                  │
├──────────────────────────────────────────────────────────────────────┤
│  Breaking 1 · Non-breaking 1 · Additive 1 · Info 2 · Renames 1   (▲)   │  ← sticky
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Renames (1)                                                           │
│  ┃━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
│  ┃▌ [RENAME]  Class renamed                                    (v) ┃ │
│  ┃▌ era:Track  →  era:RailwayTrack          high confidence       ┃ │
│  ┃▌   · matching label "Track"@en                                 ┃ │
│  ┃▌   · shared parent era:Infrastructure                          ┃ │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ │
│                                                                        │
│  Breaking changes (1)                                                  │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
│  ┃▌ [BREAKING]  Restriction changed on  era:Platform        (v)  ┃ │  ← red stripe
│  ┃▌ era:hasMaxSpeed  max 1  →  max 2                              ┃ │
│  ┃▌ ── why breaking ─────────────────────────────────────────    ┃ │
│  ┃▌ Cardinality tightened on a referenced property.              ┃ │
│  ┃▌ info → breaking   rule: cardinality-tightened                ┃ │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ │
│                                                                        │
│  Other changes (4)                                                     │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
│  ┃▌ [ADDITIVE]  Class added  era:ChargingStation  "Charging…"(>) ┃ │  ← collapsed
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │
│  ┃▌ [INFO]  Label changed on  era:Signal  "signal"→"Signal"  (>) ┃ │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ │
│                                                                        │
│  ▸ Unexplained Layer 0 changes (3)                                     │  ← collapsed
└──────────────────────────────────────────────────────────────────────┘
```

## Strengths

- **Story 1 (skim):** breaking cards stand out by stripe + badge; scannable.
- **Story 4 (CI debugger):** the "why breaking" block lives *inside* the card.
- **Story 3 (historian):** renames lead with their evidence in a calm layout.
- Closed cards keep a 200-change diff visually manageable.

## Weaknesses

- **Story 2 (deep-dive):** no sort/scan-by-column; the reader relies on `Ctrl-F`.
- **Story 5 (audit):** no tabular density to eyeball recurring kinds quickly.
- Vertical cost: each card is tall, so big diffs scroll a lot.

## Implementation cost (Component 17)

**Moderate — ~10–14 h.** One card template with a severity modifier, a
`<details>`/`<summary>` expansion per card (works with no JS), the sticky strip,
and the theme toggle. No table virtualisation, no column sort.
