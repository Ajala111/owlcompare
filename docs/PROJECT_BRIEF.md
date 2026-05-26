# Project Brief: owlcompare

## One-line description

A modern semantic ontology diff tool that helps engineers understand what *actually* changed between two versions of an ontology — and what will break because of it.

## The problem

Ontologies evolve. Domain experts add classes, refactor hierarchies, tighten cardinalities, deprecate properties. But the people downstream — the data engineers running SPARQL queries, the QA team running SHACL validations, the developers consuming the ontology in code — have no easy way to answer "what changed, and does it affect me?"

The existing tools answer the wrong question. ROBOT's `diff` and `owl-diff` operate at the **axiom level**: they list every added and removed axiom. A simple refactor (move a class, rename a property) produces hundreds or thousands of axiom-level changes, none of which tell you whether the *semantics* changed. You drown in noise.

Protégé's compare view is interactive but tied to the IDE, not designed for code review, and not exportable.

What people actually need:

- A reviewable artifact they can attach to a pull request.
- An answer to "did this change break my queries?" not just "what axioms moved?"
- A view that distinguishes a *semantic* change from a *cosmetic* refactor.
- Something that works in CI and fails the build on breaking changes.

## Who this is for

**Primary audience: ontology engineers in regulated, evolving domains.** Railway (ERA, ERJU), healthcare (SNOMED, FHIR), finance (FIBO), life sciences (OBO Foundry). People who maintain ontologies that have downstream consumers and can't afford silent semantic regressions.

**Secondary audience: data engineers and SPARQL/SHACL users** who consume third-party ontologies and need to understand the impact of an upstream version bump on their pipelines.

**Tertiary audience: ontology newcomers** who want to compare two versions of a public ontology to understand how it has evolved.

## What success looks like

### For v1 (first public release)

- A single command (`owlcompare a.ttl b.ttl`) produces a self-contained HTML report in under 10 seconds on a medium ontology (~10k axioms).
- The report can be opened offline, attached to an email, or committed to a PR.
- A GitHub Action wrapper exists and produces PR comments.
- The tool handles all common RDF serializations (Turtle, RDF/XML, OWL/XML, JSON-LD, N-Triples).
- The flagship demo is a real ERA ontology version comparison.
- Installation is `uv tool install owlcompare` or `pipx install owlcompare` — single command, no config.

### For v2+ (post-launch)

- SHACL shape impact analysis.
- SPARQL query impact analysis.
- Reasoner integration (HermiT/ELK) for inferential diff.
- Inline rename detection with confidence scores.
- VS Code extension.

## What this is *not*

- Not an ontology editor.
- Not a reasoner. We *use* reasoners; we don't build one.
- Not a SHACL validator. We *consume* SHACL output; we don't validate.
- Not a graph visualization tool. We render diffs, not the ontology itself.
- Not a server / hosted service in v1. CLI + library + static HTML reports. Hosted UX is a separate future product.

## Why now

Three converging trends make this the right moment:

1. **Knowledge graphs in regulated industry are scaling.** Railway, automotive, healthcare, finance all have multi-year programs producing large ontologies with real downstream consumers.
2. **Tooling expectations have caught up.** Engineers expect git-diff-quality UX. The ontology space has not.
3. **The Python semantic web stack is mature enough.** `rdflib`, `owlready2`, `pyshacl`, `owlrl` are stable and well-maintained.

## Differentiation

| Tool | Layer 0 axioms | Structural | Inferential | Impact | Modern UX |
|------|----------------|------------|-------------|--------|-----------|
| ROBOT diff | ✓ | partial | ✗ | ✗ | ✗ |
| owl-diff | ✓ | ✗ | ✗ | ✗ | ✗ |
| Protégé compare | ✓ | ✓ | ✗ | ✗ | partial (in-IDE) |
| **owlcompare** | **✓** | **✓** | **✓ (v2)** | **✓ (v2)** | **✓** |

The UX axis is the moat. We can match the technical depth of existing tools; the differentiator is being *pleasant to use* in a domain where nothing is.

## Non-negotiables

1. **The HTML report has to be beautiful and fast.** This is the user's first impression. It must look like it was made in 2026, not 2009.
2. **Zero-config default path.** `owlcompare a.ttl b.ttl` must work with no flags, no config file, on the first try.
3. **Honest output.** When the tool isn't sure (e.g., rename detection), it shows confidence, not certainty.
4. **CI-friendly.** Exit codes, JUnit-XML output, GitHub Action — first-class, not afterthoughts.
