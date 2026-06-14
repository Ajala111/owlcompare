# Changelog

All notable changes to **owlcompare** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While owlcompare is in the `0.x` series, the public surface (CLI flags and the
JSON output schema) may change between minor versions. See
[Versioning](#versioning) below.

## [Unreleased]

_Nothing yet._

## [0.1.0] - 2026-06-14

First public release. owlcompare compares two OWL/RDF ontologies and surfaces
*meaningful* changes — not just raw triple additions and removals — across the
syntactic and structural layers, then renders the result in formats built for
humans reviewing pull requests and for CI.

### Added

- **CLI** (`owlcompare`) with `diff`, `load`, `canonicalize`, and `version`
  commands, built on Typer. `owlcompare diff a.ttl b.ttl` is the headline entry
  point.
- **Ontology loader** that reads Turtle, RDF/XML, N3, N-Triples, JSON-LD, and
  TriG from a file path or URL into a fully-typed internal snapshot.
- **Canonicalization** so two byte-different but semantically equivalent inputs
  produce an identical normalized form (blank-node labelling, restriction
  reification, list collapsing, triple sorting).
- **Layer 0 — syntactic diff:** raw added/removed axioms, with the noise that
  higher layers explain hidden by default.
- **Layer 1 — structural diff:** entities, class/property hierarchy,
  restrictions, anonymous class expressions (union/intersection sets and
  datatype facets), and annotations, surfaced as typed `Change` records.
- **Severity classification:** every change is graded `breaking`,
  `non_breaking`, `additive`, or `info` by six built-in cross-cutting refinement
  rules, overridable via a TOML config (`--severity-config`); the refinement
  audit trail is recorded in the JSON metadata.
- **Rename detection** at three confidence tiers (label match, structural
  fingerprint, and user-supplied mapping), consolidating an add+remove pair into
  a single rename plus its cascade consequences, with post-rename re-diffing so a
  rename that *also* adds structure surfaces both facts. Detected renames can be
  exported (`--export-rename-mapping`) and replayed (`--rename-mapping`).
- **Report renderers:** `--format` `text` (default), `json`, `markdown`, `html`,
  and `junit`.
  - The **HTML report** is a self-contained, offline-viewable single file
    (all CSS/JS inlined, `file://`-openable) with light/dark/auto themes.
  - The **JSON output** is a published, versioned [JSON Schema 2020-12 contract]
    (docs/schema/diff-result.schema.json), bundled with the package and
    validatable via `--validate-schema`.
  - The **Markdown report** is PR-comment ready; the **JUnit XML** report drops
    into CI test-results dashboards.
  - All renderers are byte-deterministic (honouring `SOURCE_DATE_EPOCH`).
- **CI signal:** `owlcompare diff` exits `10` when at least one breaking change
  is found, `0` otherwise.
- **GitHub Action** (`Ajala111/owlcompare@v1`) — a composite action that diffs an
  ontology on every pull request, posts an update-in-place PR comment, and
  uploads HTML/JUnit reports as artifacts.
- **Documentation site** built with MkDocs Material, including a flagship
  showcase that diffs two published quarterly releases of FIBO Business Entities.

### Known limitations

- **Only Layer 0 (syntactic) and Layer 1 (structural) are implemented.** The
  Layer 2 (inferential, reasoner-backed) and Layer 3 (impact, SHACL/SPARQL)
  diffs described in the project brief are not in this release; requesting them
  (`--layers inferential` / `impact`) is a clean "not implemented yet" error.
- **Single-graph only.** Named graphs / quad stores are rejected with a clear
  error rather than silently merged.
- The JSON output is versioned but, per the `0.x` policy, may still evolve before
  `1.0`.

[Unreleased]: https://github.com/Ajala111/owlcompare/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ajala111/owlcompare/releases/tag/v0.1.0
[JSON Schema 2020-12 contract]: https://github.com/Ajala111/owlcompare/blob/main/docs/schema/diff-result.schema.json

## Versioning

owlcompare follows Semantic Versioning with one caveat for the pre-1.0 series:

- **`0.x` (now):** minor version bumps (`0.1` → `0.2`) may include breaking
  changes to the CLI surface or JSON schema. Patch bumps (`0.1.0` → `0.1.1`) are
  bug-fix only.
- **`1.0` onward:** the CLI and JSON schema become a stability commitment; breaking
  changes will bump the major version.
