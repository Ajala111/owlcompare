# Wireframe C — Narrative ("blog post style")

Severity-grouped prose. Each change is a sentence or two of near-readable English,
not a structured row or card. Technical detail (IRIs, rules) drops to footnote
style. No filters, no expansion — everything is already prose on the page.

## Mockup — main view

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                        │
│              Diff: era-3.1.0.ttl → era-3.2.0.ttl                       │
│              One breaking change. Five changes in total.   [⤓] [◐]     │
│                                                                        │
│  ────────────────────────────────────────────────────────────────     │
│                                                                        │
│  ## One thing was renamed                                              │
│                                                                        │
│  The class **Track** was renamed to **RailwayTrack** — we're confident │
│  (it kept the label "Track" and the parent Infrastructure).¹           │
│                                                                        │
│  ## One breaking change                                                │
│                                                                        │
│  **Platform** now permits at most **two** maximum-speed values, where  │
│  it previously allowed only one. Because downstream shapes rely on the │
│  single-value assumption, this is breaking.²                           │
│                                                                        │
│  ## Four smaller changes                                               │
│                                                                        │
│  A new class **ChargingStation** was added. The label on **Signal**    │
│  was capitalised ("signal" → "Signal"). A comment was added to         │
│  **Platform**. …                                                       │
│                                                                        │
│  ────────────────────────────────────────────────────────────────     │
│  ¹ era:Track → era:RailwayTrack · class_renamed · high                 │
│  ² era:Platform · era:hasMaxSpeed max 1 → max 2 · rule:                │
│    cardinality-tightened · info → breaking                             │
│                                                                        │
│  ▸ Unexplained Layer 0 changes (3)                                     │
└──────────────────────────────────────────────────────────────────────┘
```

## Strengths

- **Story 1 (skim):** the single best for "is this safe?" — the answer is the
  first sentence, in plain English.
- **Story 3 (historian):** reads as intent; the evolution narrative is the whole
  design. Ages well as an archived artifact.
- Lowest visual weight; pleasant, "made in 2026" first impression.

## Weaknesses

- **Story 2 (deep-dive):** prose hides structure; finding *every* property change
  means reading, not scanning. Worst of the three here.
- **Story 5 (audit):** no density, no counts-by-kind; pattern-spotting is poor.
- Prose templating per kind is the most content-engineering work and the most
  brittle for unknown/forward-compat kinds (which have only a raw `summary`).
- Does not scale: 200 changes as paragraphs is unreadable.

## Implementation cost (Component 17)

**High — ~14–20 h**, but front-loaded in *content* not *code*: a hand-written
English template per change kind, graceful fallback for unknown kinds, and
footnote anchoring. Little interactivity, so the JS surface is small.
