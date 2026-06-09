# Understanding the output

owlcompare's output has two organizing ideas: **layers** (how deep the analysis
goes) and **severity** (how much each change should worry you). Understand these
two and you understand every report owlcompare produces, in every format.

## The four-layer model

A naïve ontology diff lists added and removed *triples*. The problem is that one
human-meaningful edit — say, moving a class in the hierarchy — can touch dozens
or hundreds of triples. You drown in noise. owlcompare analyzes the same change
at increasing levels of meaning:

| Layer | Name | The question it answers | v1 |
|-------|------|-------------------------|----|
| **0** | Syntactic | Which raw triples were added or removed? | ✅ |
| **1** | Structural | Which entities, hierarchy edges, restrictions, and annotations changed? | ✅ |
| **2** | Inferential | Did the set of *entailed* (reasoner-derived) facts change? | 🔭 v2 |
| **3** | Impact | Which downstream SHACL shapes or SPARQL queries would break? | 🔭 v2 |

**Layer 0 (syntactic)** is the ground truth — the literal triple delta. It's
always computed, but in normal output it's *hidden* when a higher layer already
explains it. You'll see a line like `Layer 0 — Syntactic (0 unexplained)`: the
zero means every raw change was accounted for by a structural event. Pass
`--show-syntactic` to see the raw triples regardless.

**Layer 1 (structural)** is where owlcompare earns its keep in v1. It recognizes
the *shapes* of change that ontology engineers actually think in:

- **Entities** — classes and properties added, removed, or deprecated.
- **Hierarchy** — `subClassOf` / `subPropertyOf` edges added, removed, or
  reparented.
- **Restrictions** — cardinalities, `someValuesFrom`, `allValuesFrom`, domains,
  ranges tightened or loosened.
- **Annotations** — labels, comments, and other metadata.

Each Layer 1 event *subsumes* the Layer 0 triples that caused it, which is why
the noisy raw delta collapses into a short, readable list.

**Layers 2 and 3** are planned for v2. v1 deliberately ships without them because
structural diff alone already covers the overwhelming majority of real review
work — and shipping early lets the UX prove itself before reasoner and
SHACL/SPARQL integration are added. See [Diff layers](../architecture/diff-layers.md)
for the full design.

## Severity: how much should you care?

Every change carries one of four severities. This is the single most important
concept in owlcompare, because it's what turns a diff into a *decision*.

| Severity | Meaning | Example |
|----------|---------|---------|
| `breaking`{ data-severity="breaking" } | Downstream consumers may fail. | A class or property is removed; a cardinality is tightened; a range is narrowed. |
| `non_breaking`{ data-severity="non-breaking" } | Semantics changed, but valid existing usage still works. | A range is widened; a cardinality is relaxed. |
| `additive`{ data-severity="additive" } | A pure addition that constrains nothing existing. | A new class or property appears. |
| `info`{ data-severity="info" } | Editorial or metadata change. | A label or comment edit; a version bump. |

The dividing line is **"will this break someone downstream?"** A removed property
breaks every query that named it — `breaking`. A *loosened* cardinality cannot
break data that already satisfied the stricter rule — `non_breaking`. A brand-new
class can't break anything that predates it — `additive`. A typo fix in a label
changes no semantics — `info`.

### Severity drives the exit code

If a diff contains **any** breaking change, owlcompare exits with code **10**.
Otherwise it exits `0`. That single rule is what lets a CI job fail a pull
request the moment a breaking ontology change is introduced — see
[Exit codes](../reference/exit-codes.md).

### Severity is refined with cross-cutting context

Most severities are decided by the slice that detects the change. But some
judgments need a wider view — for example, an annotation change on an entity
that's *also* being deprecated in the same diff is just editorial noise, so it's
demoted to `info`. A small set of built-in rules applies these cross-cutting
refinements after the per-slice pass, and you can override any of them with your
own project conventions. See [Severity rules](../reference/severity-rules.md) and
the [Severity overrides guide](../guides/severity-overrides.md).

## Renames: one event, not two

When an entity is renamed, a triple-level diff sees a *removal* of the old IRI and
an *addition* of the new one — two unrelated-looking changes, multiplied by every
axiom that referenced it. owlcompare detects the rename and reports it as a
single event, with a **confidence** level so you know how sure it is:

- **certain** — you asserted the rename in a mapping file.
- **high** — matched by a shared `rdfs:label`.
- **medium** — matched by structural fingerprint (same parents, same
  restrictions) when labels don't line up.

owlcompare shows confidence, not false certainty — honest output is a design
principle. The [Rename detection guide](../guides/rename-detection.md) covers the
tiers and when to lower the confidence floor.

## The same diff, five ways

owlcompare computes the diff once and can render it in five formats. They carry
the same information at different fidelities:

| Format | Flag | Best for |
|--------|------|----------|
| Terminal | *(default)* | A quick look while you work. |
| HTML | `--format html` | Review — share, attach, archive. A single self-contained file. |
| Markdown | `--format markdown` | PR comments. The GitHub Action posts this. |
| JSON | `--format json` | Automation. A [versioned schema](../reference/json-schema.md). |
| JUnit XML | `--format junit` | CI test-results dashboards. |

## Next steps

- [Next steps](next-steps.md) — where to go from here.
- [Reading the HTML report](../guides/reading-html-report.md) — a guided tour.
- [Change kinds](../reference/change-kinds.md) — every event owlcompare can emit.
