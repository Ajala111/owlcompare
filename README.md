# owlcompare

> Modern semantic ontology diff. See what *actually* changed.

[![PyPI version](https://img.shields.io/pypi/v/owlcompare.svg)](https://pypi.org/project/owlcompare/)
[![Python versions](https://img.shields.io/pypi/pyversions/owlcompare.svg)](https://pypi.org/project/owlcompare/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/Ajala111/owlcompare/actions/workflows/ci.yml/badge.svg)](https://github.com/Ajala111/owlcompare/actions/workflows/ci.yml)

`owlcompare` compares two OWL/RDF ontologies and produces an interactive HTML report (plus JSON, Markdown, and CI-friendly outputs) that surfaces meaningful changes — not just raw axiom additions.

## Status

**owlcompare v0.1.0 is live on PyPI.** See the [CHANGELOG](https://github.com/Ajala111/owlcompare/blob/main/CHANGELOG.md) for what shipped.

## Why

Existing ontology diff tools (ROBOT, owl-diff, Protégé compare) operate at the axiom level. A simple refactor produces hundreds of axiom-level changes that don't tell you whether the *semantics* actually changed. `owlcompare` diffs at multiple semantic layers and presents the result in a UX built for humans reviewing pull requests.

v0.1.0 implements full Layer 0 (syntactic) and Layer 1 (structural) diffs. Layer 2 (inferential, via reasoner) and Layer 3 (impact, via downstream consumer analysis) are planned for v2.

## Quick start

```bash
pip install owlcompare
```

Or, with the [uv](https://docs.astral.sh/uv/) tool installer:

```bash
uv tool install owlcompare
```

Then diff two ontologies:

```bash
owlcompare diff old.ttl new.ttl --out report.html
```

## See it in action

The [FIBO flagship demo](https://ajala111.github.io/owlcompare/showcase/fibo/) diffs two published quarterly releases of the FIBO Business Entities module (2023Q3 → 2024Q3). owlcompare distills 214 raw triple changes into 41 structured events and surfaces the single coordinated vocabulary migration behind most of them — cross-validated against the EDM Council's own release notes. It's the most credible showcase of what the tool does on real-world ontologies.

## Use with GitHub Actions

Diff your ontology on every pull request in three lines:

```yaml
- uses: actions/checkout@v4
- uses: Ajala111/owlcompare@v1
  with:
    ontology-path: ontology/my-ontology.ttl
```

You get a PR comment with the diff, the HTML and JUnit reports uploaded as
artifacts, and a check that fails on breaking changes. See
[`docs/github-action.md`](https://github.com/Ajala111/owlcompare/blob/main/docs/github-action.md)
for the full reference — inputs, outputs, baseline detection, and more examples.

## Documentation

- **[Documentation site](https://ajala111.github.io/owlcompare/)** — the primary entry point: installation, your first diff, understanding the output, CI integration, and the CLI reference.
- [CHANGELOG](https://github.com/Ajala111/owlcompare/blob/main/CHANGELOG.md) — release history.

### Project internals

For contributors and anyone who wants the design rationale:

- [Project brief](https://github.com/Ajala111/owlcompare/blob/main/docs/PROJECT_BRIEF.md) — vision, audience, success criteria
- [Architecture](https://github.com/Ajala111/owlcompare/blob/main/docs/ARCHITECTURE.md) — components, data flow, public surfaces
- [Roadmap](https://github.com/Ajala111/owlcompare/blob/main/docs/ROADMAP.md) — phased delivery plan
- [Design decisions](https://github.com/Ajala111/owlcompare/blob/main/docs/DESIGN_DECISIONS.md) — why we chose what we chose
- [Conventions](https://github.com/Ajala111/owlcompare/blob/main/docs/CONVENTIONS.md) — code style and project standards
- [Glossary](https://github.com/Ajala111/owlcompare/blob/main/docs/GLOSSARY.md) — terminology used consistently

## License

MIT — see [LICENSE](https://github.com/Ajala111/owlcompare/blob/main/LICENSE).
</content>
</invoke>
