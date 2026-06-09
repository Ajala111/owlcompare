# Frequently asked questions

## How is owlcompare different from ROBOT diff?

[ROBOT](http://robot.obolibrary.org/)'s `diff` (and `owl-diff`, and Protégé's
compare view) operate at the **axiom level**: they list every added and removed
axiom. That's correct and complete, but it answers the wrong question. A single
human-meaningful edit — moving a class, renaming a property — produces dozens or
hundreds of axiom-level changes, none of which tell you whether the *semantics*
actually changed. You read all of them to find the one that matters.

owlcompare answers a different question: **"what changed, and does it break me?"**
It rolls raw triples up into structural events (entity added, restriction
loosened, class reparented), classifies each by **severity**, detects **renames**
so an add+remove pair becomes one event, and renders the result in a UX built for
pull-request review — a self-contained HTML report, a PR comment, a CI status.

The two tools also have different centers of gravity. ROBOT is a comprehensive
ontology-engineering toolkit (it does conversion, reasoning, extraction,
templating, and much more); diff is one subcommand. owlcompare does one thing —
*review-grade semantic diff* — and invests entirely in making that pleasant. If
you need a full ontology pipeline, reach for ROBOT. If you need to know what a PR
changes and whether to block it, reach for owlcompare.

## Does owlcompare support OWL 2 reasoning?

Not in v1. owlcompare ships **Layers 0 (syntactic) and 1 (structural)** fully
implemented. The **inferential layer** (Layer 2) — diffing the set of *entailed*
facts using a reasoner like HermiT or ELK — is designed but planned for v2. v1
deliberately ships without it because structural diff alone covers the
overwhelming majority of real review work, and shipping early lets the UX prove
itself before heavier reasoner dependencies are added. See
[Diff layers](architecture/diff-layers.md).

## Can I diff ontologies that import each other?

v1 diffs the two files you give it, as given. It does **not** resolve
`owl:imports` and pull in the imports closure — so imported axioms aren't part of
the comparison unless they're physically present in the files. Imports-closure
resolution is on the roadmap. If you need it today, merge the closure yourself
(for example with ROBOT's `merge`) before diffing.

Named graphs / quad formats (TriG, N-Quads) are also out of scope for v1: a quad
source with non-default named graphs is rejected with a canonicalization error.

## What's the performance ceiling?

owlcompare is built for the medium-ontology, pull-request-review case. The HTML
report is engineered to stay responsive at **2000 changes under 5 MB**, with
performance coming from native browser scrolling and lazy-rendered detail
sections rather than from capping what's shown. For very large ontologies, the
cost is dominated by parsing and canonicalization, not the diff itself. See
[Working with large ontologies](guides/working-with-large-ontologies.md).

## Is owlcompare a stable v1 API?

Two surfaces are **versioned contracts** and safe to build on: the **CLI** (flags
and exit codes) and the **JSON output**, which is formalized by a published
[JSON Schema](reference/json-schema.md) with an explicit forward-compatibility
policy. The Python **library** API is not yet frozen — it'll firm up after v1.
Pin a version if you depend on the library directly.

## Which RDF formats can owlcompare read?

Everything `rdflib` parses: Turtle, RDF/XML, OWL/XML, JSON-LD, N-Triples, and
more. The format is auto-detected from the file, or you can hint it with
`--format`. The two ontologies in a diff don't have to be in the same
serialization — owlcompare canonicalizes both before comparing, so a Turtle file
diffs cleanly against an RDF/XML one.

## Does it phone home? Any tracking?

No. owlcompare runs entirely locally, makes no network calls except to fetch
ontologies from URLs you explicitly pass it, and the documentation site and HTML
reports carry no analytics or trackers. The HTML report is a single
self-contained file with no external resources.

## How do I contribute?

owlcompare is built component-by-component against written specs. See
[Contributing](contributing.md) for the dev-environment setup, how to run the
tests, and the spec-driven workflow.
