# Contributing

owlcompare is built component-by-component against written specifications. This
page gets you a working development environment, shows you how to run the checks,
and explains the spec-driven workflow the project follows.

## Set up the dev environment

owlcompare uses [uv](https://docs.astral.sh/uv/) for everything — dependencies,
virtual environments, and running tools. Install uv first if you don't have it,
then:

```bash
git clone https://github.com/Ajala111/owlcompare.git
cd owlcompare
uv sync          # create the venv and install runtime + dev dependencies
```

`uv sync` does **not** install the documentation toolchain — those live in an
optional group. Add them only when you're working on the site:

```bash
uv sync --group docs
```

Requirements: **Python 3.11+** (3.12 recommended). On Windows with Smart App
Control, install Python via `winget install Python.Python.3.11` and run
`uv python pin 3.11` to avoid intermittent interpreter blocks.

## Run the checks

owlcompare has four quality gates. All four must be green before a change lands:

```bash
uv run pytest                    # tests
uv run ruff check .              # lint
uv run ruff format --check .     # formatting
uv run mypy src/owlcompare       # type-checking (strict on the public API)
```

Run a single test file while iterating:

```bash
uv run pytest tests/unit/test_xyz.py
```

!!! tip "Windows invocation"
    If `uv run owlcompare ...` is blocked by Smart App Control, use
    `uv run python -m owlcompare ...` instead — it routes through the trusted
    interpreter and behaves identically.

## Build the docs locally

```bash
uv sync --group docs
uv run mkdocs serve              # live preview at http://127.0.0.1:8000/
uv run mkdocs build --strict     # production build; --strict fails on broken links
```

The custom landing page (`site_src/index.html`) is **not** built by MkDocs — it's
copied over the generated `site/index.html` by the publish workflow. To preview
it, open `site_src/index.html` directly in a browser after a build.

## The spec-driven workflow

Every component starts as a spec in `specs/NN-*.md` and is built to that contract.
The required reading order each session is in `CLAUDE.md`, but in short:

1. Read `docs/ROADMAP.md` to see what's done and what's next.
2. Read the relevant `specs/NN-*.md` for the component you're building.
3. Follow `docs/CONVENTIONS.md` for code style.
4. Check `docs/DESIGN_DECISIONS.md` before introducing any new dependency or
   pattern.

A few operating principles the project holds to:

- **Stay in scope.** Build what the spec describes. Out-of-scope problems go in
  the roadmap's Backlog, not into the current change.
- **Stop and ask, don't guess.** One clarifying question beats a wrong
  implementation.
- **Write tests as you go.** Every spec includes acceptance tests; they're not
  optional.
- **One component per pull request.** Reference the spec file in the PR
  description.

## Adding a new diff slice

The structural diff is organized as independent *slices* under
`src/owlcompare/diff/` (entities, hierarchy, restrictions, annotations). To add a
new kind of structural analysis:

1. Write the spec first, or extend the existing one.
2. Add the slice module and have it emit `Change` records with the correct
   `kind`, `severity`, and `subsumes` set.
3. Register it in the orchestrator pipeline.
4. Add small, hand-crafted Turtle fixtures under `tests/fixtures/` that exercise
   the new behavior, plus golden output where applicable.
5. If you add a new `Change` kind, document it in
   [Change kinds](reference/change-kinds.md) — and remember that adding a kind is
   forward-compatible with the JSON schema (it isn't an enum).

## Regenerating the screenshots

The landing-page screenshots are captured from real owlcompare output, not
committed as generated artifacts. When the HTML or Markdown rendering changes
materially, regenerate them — the instructions live in
`site_src/docs/assets/README.md`. There's no automated drift detection, so this
is a manual step at review time.

## Publishing the docs

The site deploys automatically: a push to `main` triggers
`.github/workflows/docs.yml`, which builds with `mkdocs build --strict`, copies
the custom landing page over the generated index, and deploys to GitHub Pages. If
a deploy fails, check **Settings → Pages → Source: GitHub Actions** is enabled on
the repository.

## License

owlcompare is MIT licensed. By contributing, you agree your contributions are
licensed under the same terms.
