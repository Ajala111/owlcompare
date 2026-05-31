# CLAUDE.md

This file is the entry point for any AI assistant working on this codebase. **Read this first, every session.**

## What is owlcompare?

`owlcompare` is a modern semantic ontology diff tool. It compares two OWL/RDF ontologies and produces an interactive HTML report (plus JSON / Markdown / CI-friendly outputs) that surfaces *meaningful* changes at multiple semantic layers, not just raw axiom additions and removals.

**The differentiator vs. existing tools (ROBOT diff, owl-diff, Protégé compare):** we diff at four layers — syntactic, structural, inferential, and impact — and the UX is built for humans reviewing pull requests, not for compilers.

For full vision and rationale, read `docs/PROJECT_BRIEF.md`.

## Project state

The roadmap and current phase are tracked in `docs/ROADMAP.md`. **Always check the roadmap before starting work** — it tells you what's done, what's next, and what's deferred.

Per-component specifications live in `specs/`. When asked to build component N, read `specs/NN-*.md` for the contract.

## How to work on this project

### 1. Required reading order, every session

1. This file (`CLAUDE.md`)
2. `docs/ROADMAP.md` — where are we?
3. `specs/NN-*.md` — what specifically am I building right now?
4. `docs/CONVENTIONS.md` — how do I write the code?
5. `docs/ARCHITECTURE.md` — only if the task touches cross-component concerns
6. `docs/DESIGN_DECISIONS.md` — only if you're tempted to introduce a new dependency or pattern

### 2. Operating principles

- **Stay in scope.** Build exactly what the current spec describes. If you find a problem outside scope, add it to `docs/ROADMAP.md` under "Backlog" — don't fix it.
- **Stop and ask, don't guess.** If a spec is ambiguous, ask the user before writing code. One clarifying question beats a wrong implementation.
- **Prefer existing patterns.** If a component already exists in the codebase, mirror its structure. Consistency matters more than micro-optimizations.
- **Write tests as you go.** Every component spec includes acceptance tests; they are not optional.
- **Document decisions, not code.** Don't write comments that restate the code. Do write comments that explain *why* a non-obvious choice was made — and if the decision is project-wide, add it to `docs/DESIGN_DECISIONS.md` instead.
- **Update docs when behavior changes.** If you change a CLI flag, output format, or public API, update the relevant spec and the roadmap in the same change.

### 3. Tooling

- **Package manager:** `uv`. Never use `pip` directly; use `uv add`, `uv sync`, `uv run`.
- **Python version:** 3.11+ (target 3.11 as minimum; 3.12 preferred for development).
- **Testing:** `pytest` via `uv run pytest`.
- **Linting / formatting:** `ruff` (configured in `pyproject.toml`).
- **Type checking:** `mypy` in strict mode for the public API; permissive for internal modules.

### 4. Code layout (canonical)

```
owlcompare/
├── src/owlcompare/
│   ├── __init__.py
│   ├── cli.py              # Typer-based CLI entry point
│   ├── loader.py           # Ontology loading & normalization
│   ├── model.py            # Internal data model (dataclasses)
│   ├── diff/
│   │   ├── __init__.py
│   │   ├── syntactic.py    # Layer 0
│   │   ├── structural.py   # Layer 1
│   │   ├── inferential.py  # Layer 2
│   │   └── impact.py       # Layer 3
│   ├── rename.py           # Rename detection
│   ├── report/
│   │   ├── __init__.py
│   │   ├── json_report.py
│   │   ├── markdown_report.py
│   │   └── html_report.py
│   └── reasoner.py         # Reasoner adapters
├── tests/
│   ├── fixtures/           # Small ontology pairs for testing
│   ├── unit/
│   └── integration/
├── docs/
├── specs/
└── pyproject.toml
```

### 5. Anti-patterns to avoid

- **Don't introduce new top-level dependencies without consulting `DESIGN_DECISIONS.md`.** Each dependency is a long-term commitment.
- **Don't optimize prematurely.** A clear, correct implementation first; profile, then optimize if needed.
- **Don't write giant functions.** If a function exceeds ~50 lines or has more than two levels of nesting, decompose it.
- **Don't hide errors.** Catch exceptions at boundaries (CLI, report generation); let them propagate inside the library so tests catch them.
- **Don't break public API silently.** The CLI surface and the JSON output schema are versioned (see `docs/ARCHITECTURE.md`).

## Quick command reference

```bash
uv sync                                       # Install dependencies
uv run pytest                                 # Run tests
uv run pytest tests/unit/test_x.py            # Run one test file
uv run ruff check .                           # Lint
uv run ruff format .                          # Format
uv run mypy src/owlcompare                    # Type-check
uv run python -m owlcompare --help            # Run the CLI (SAC-safe on Windows; see DD-016)
```

## When in doubt

Ask the user. A 30-second clarification beats a 30-minute wrong path.
