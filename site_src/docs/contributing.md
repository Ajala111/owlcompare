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

The landing page (`site_src/index.html`) is overlaid onto the built site via the
`overlay_landing_page` hook. Local `mkdocs serve` shows the same landing page as
the deployed site.

We pin to mkdocs 1.x and mkdocs-material 9.x. The MkDocs ecosystem may evolve
significantly in 2026–2027; revisit pinning when migrating.

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
`.github/workflows/docs.yml`, which builds with `mkdocs build --strict` (the
`overlay_landing_page` hook drops the custom landing page over the generated
index during that build) and deploys to GitHub Pages. If a deploy fails, check
**Settings → Pages → Source: GitHub Actions** is enabled on the repository.

## Cutting a release

owlcompare publishes to [PyPI](https://pypi.org/project/owlcompare/) through a
tag-triggered GitHub Actions workflow using
[OIDC Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — there is no
API token stored in the repository.

### The version is single-sourced

The version lives in **one** place: `src/owlcompare/_version.py`
(`__version__ = "X.Y.Z"`). `pyproject.toml` reads it dynamically via Hatchling
(DD-013), so you never edit the version in two files. The release workflow
refuses to publish if the pushed tag doesn't match `__version__`.

### Steps to release X.Y.Z

1. **Bump the version.** Edit `src/owlcompare/_version.py` to the new version.
2. **Update the changelog.** Move the relevant `## [Unreleased]` notes into a new
   `## [X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md` (Keep a Changelog format).
   Add the `compare`/`tag` link references at the bottom.
3. **Commit** both on `main` (via PR): `Release X.Y.Z`.
4. **Tag and push:**
   ```bash
   git tag -a vX.Y.Z -m "owlcompare vX.Y.Z"
   git push origin vX.Y.Z
   ```

Pushing the `vX.Y.Z` tag triggers `.github/workflows/release.yml`, which:

- rejects the tag unless it's a clean final release (`vMAJOR.MINOR.PATCH`);
- verifies the tag matches `_version.py`;
- builds the sdist + wheel with `python -m build`;
- runs `twine check dist/*`;
- publishes to PyPI via `pypa/gh-action-pypi-publish` (OIDC, environment `pypi`);
- creates a GitHub Release whose body is this version's `CHANGELOG.md` section,
  with the build artifacts attached.

### Stage on TestPyPI first

For a dry run, bump `_version.py` to a pre-release (e.g. `0.1.0rc1`) and push a
`pre/...` tag:

```bash
git tag pre/v0.1.0-rc1
git push origin pre/v0.1.0-rc1
```

That triggers `.github/workflows/release-test.yml`, which runs the same build and
checks but publishes to [TestPyPI](https://test.pypi.org/) (environment
`testpypi`) and does **not** cut a GitHub Release. Install the staged build to
verify it:

```bash
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ owlcompare==0.1.0rc1
```

### Versioning policy

owlcompare follows [Semantic Versioning](https://semver.org/) with a pre-1.0
caveat:

- **`0.x`:** minor bumps (`0.1` → `0.2`) **may break** the CLI surface or JSON
  schema; patch bumps (`0.1.0` → `0.1.1`) are bug-fix only.
- **`1.0` onward:** the CLI and JSON schema become a stability commitment;
  breaking changes bump the major version.

### Recovering from a bad release

PyPI release artifacts are **immutable** — you cannot re-upload the same version.
If a published release is broken:

1. **Yank it** on PyPI (Manage → Release → Options → Yank). Yanking hides the
   version from new installs but keeps it resolvable for anyone who pinned it —
   it is not a delete.
2. **Fix** the metadata/code on `main`.
3. **Bump to the next patch** (`0.1.0` → `0.1.1`) in `_version.py` and add a
   `CHANGELOG.md` entry — never reuse a version number.
4. **Delete the bad tag** if it never published successfully
   (`git push --delete origin vX.Y.Z`), then retag the fix. If it *did* publish,
   leave the tag and move forward with the new patch version.

A good habit is to stage on TestPyPI first (above), which catches metadata
problems (`twine check`, missing long-description rendering) before they reach the
real index.

## License

owlcompare is MIT licensed. By contributing, you agree your contributions are
licensed under the same terms.
