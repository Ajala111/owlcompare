# Changelog

All notable changes to owlcompare are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and owlcompare aims to follow
[Semantic Versioning](https://semver.org/) once it reaches a public release.

The two versioned contracts — the [CLI](reference/cli.md) and the
[JSON output schema](reference/json-schema.md) — evolve under the
compatibility policy described in their respective reference pages.

## [Unreleased]

The first public release is being prepared. The development tree already
includes everything listed under v0.0.1 below; this section collects anything
landing on top of it before the release is tagged.

### Pending for the first PyPI release

- Publishing owlcompare to PyPI so `pip install owlcompare` and
  `uv tool install owlcompare` work out of the box.
- A flagship demo comparing two real ERA ontology versions.

## [0.0.1] — initial release

The first end-to-end owlcompare: load two ontologies, diff them at the syntactic
and structural layers, classify severity, detect renames, and render the result
in five formats.

### Added

- **`owlcompare diff`** — compare two ontologies and report the delta. Exits `10`
  on breaking changes, `0` otherwise.
- **`owlcompare load`** — load one ontology and print a summary.
- **`owlcompare canonicalize`** — emit the normalized form of an ontology.
- **Layer 0 (syntactic) diff** — the raw triple delta, with subsumed triples
  hidden by default.
- **Layer 1 (structural) diff** — entities, hierarchy, restrictions, and
  annotations, each rolled up from the triples that caused it.
- **Severity classification** — `breaking`, `non_breaking`, `additive`, `info`,
  with six built-in cross-cutting refinement rules and TOML user overrides.
- **Rename detection** — three confidence tiers (certain / high / medium), with
  cascade consolidation and a `--export-rename-mapping` workflow.
- **Five output formats** — terminal text, self-contained HTML report,
  PR-comment Markdown, schema-locked JSON, and JUnit XML.
- **GitHub Action** — a composite action wrapping the CLI: baseline detection,
  PR comments, artifact upload, and breaking-change gating.
- **Published JSON Schema** — a versioned, machine-readable contract for the JSON
  output, with a documented forward-compatibility policy.

### Known limitations

- Layers 2 (inferential) and 3 (impact) are not yet implemented.
- `owl:imports` closures are not resolved; named-graph / quad sources are
  rejected.
- owlcompare is not yet on PyPI — install a pinned commit until the release lands
  (see [Installation](getting-started/installation.md)).

---

!!! info "How this page is maintained"
    Release entries are written by hand from the merged work, and the version
    numbers track git tags. When a release is tagged, its `[Unreleased]` items
    move down into a new dated section.
