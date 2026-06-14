# owlcompare

> Modern semantic ontology diff. See what *actually* changed.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`owlcompare` compares two OWL/RDF ontologies and produces an interactive HTML report (plus JSON, Markdown, and CI-friendly outputs) that surfaces meaningful changes — not just raw axiom additions.

## Status

**Pre-alpha.** Under active development. See [`docs/ROADMAP.md`](https://github.com/Ajala111/owlcompare/blob/main/docs/ROADMAP.md) for progress.

## Why

Existing ontology diff tools (ROBOT, owl-diff, Protégé compare) operate at the axiom level. A simple refactor produces hundreds of axiom-level changes that don't tell you whether the *semantics* actually changed. `owlcompare` diffs at four semantic layers — syntactic, structural, inferential, and impact — and presents the result in a UX built for humans reviewing pull requests.

## Quick start (planned)

```bash
uv tool install owlcompare
owlcompare diff old.ttl new.ttl --out report.html
```

## Use with GitHub Actions

Diff your ontology on every pull request in three lines:

```yaml
- uses: actions/checkout@v4
- uses: phelz/owlcompare@v1
  with:
    ontology-path: ontology/my-ontology.ttl
```

You get a PR comment with the diff, the HTML and JUnit reports uploaded as
artifacts, and a check that fails on breaking changes. See
[`docs/github-action.md`](https://github.com/Ajala111/owlcompare/blob/main/docs/github-action.md)
for the full reference — inputs, outputs, baseline detection, and more examples.

## Documentation

- [Project brief](https://github.com/Ajala111/owlcompare/blob/main/docs/PROJECT_BRIEF.md) — vision, audience, success criteria
- [Architecture](https://github.com/Ajala111/owlcompare/blob/main/docs/ARCHITECTURE.md) — components, data flow, public surfaces
- [Roadmap](https://github.com/Ajala111/owlcompare/blob/main/docs/ROADMAP.md) — phased delivery plan
- [Design decisions](https://github.com/Ajala111/owlcompare/blob/main/docs/DESIGN_DECISIONS.md) — why we chose what we chose
- [Conventions](https://github.com/Ajala111/owlcompare/blob/main/docs/CONVENTIONS.md) — code style and project standards
- [Glossary](https://github.com/Ajala111/owlcompare/blob/main/docs/GLOSSARY.md) — terminology used consistently

## License

MIT — see [LICENSE](https://github.com/Ajala111/owlcompare/blob/main/LICENSE).
