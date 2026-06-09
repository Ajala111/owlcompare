# owlcompare documentation

`owlcompare` is a modern semantic diff for OWL/RDF ontologies. It compares two
versions of an ontology and tells you **what actually changed** — renames,
restriction changes, hierarchy moves, severity-classified breaking changes — not
just which raw triples were added and removed.

This is the documentation hub. If you landed here from a "Docs" link, you're in
the right place; pick a path below.

!!! tip "New to owlcompare?"
    Start with [Installation](getting-started/installation.md), then walk through
    [Your first diff](getting-started/first-diff.md). It takes about ten minutes.

## Choose your path

- **Evaluating owlcompare?** Read [Understanding the output](getting-started/understanding-output.md)
  to see how the four-layer model turns axiom noise into a short list of meaningful
  events, then open a [live example report](examples/era_evolution.html).
- **Integrating it into CI?** The [CI integration guide](guides/ci-integration.md)
  gets you a three-line GitHub Action that comments on every pull request.
- **Going deep?** The [CLI reference](reference/cli.md) documents every command and
  flag, and the [Architecture](architecture/overview.md) section explains how the
  diff engine works under the hood.

## What owlcompare is (and isn't)

owlcompare is a **command-line tool and Python library** that emits diff reports
in five formats: a rich terminal view, a self-contained interactive HTML report,
PR-comment-ready Markdown, machine-readable JSON, and JUnit XML for CI dashboards.

It is **not** an ontology editor, a reasoner, or a SHACL validator. It reads two
ontologies and reports the delta — nothing it produces ever modifies your source
files.

## The four layers at a glance

| Layer | Name | What it answers | Status in v1 |
|-------|------|-----------------|--------------|
| 0 | Syntactic | Which raw triples changed? | ✅ Implemented |
| 1 | Structural | Which entities, hierarchies, restrictions, and annotations changed? | ✅ Implemented |
| 2 | Inferential | Did the set of *entailed* facts change? | 🔭 Planned (v2) |
| 3 | Impact | Which downstream SHACL shapes / SPARQL queries break? | 🔭 Planned (v2) |

v1 ships Layers 0 and 1 fully implemented — which already covers the vast
majority of real ontology review. See [Diff layers](architecture/diff-layers.md)
for the detail.
