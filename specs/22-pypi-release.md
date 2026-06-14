# Component 22: PyPI Release Pipeline

> **Provenance note.** This spec was written *retroactively*, after the component
> was built. No `specs/22-*.md` existed during implementation; Component 22 was
> built to a detailed operator brief delivered in the planning conversation. This
> document records the design **as actually shipped** (including the deviations
> that surfaced during the build), so the authoritative source for *why* is the
> implementing commit(s) and the build summary, not a pre-written contract.

## Identity

- **Component number:** 22
- **Name:** PyPI release pipeline
- **Module paths:**
  - `pyproject.toml` — packaging metadata + wheel/sdist build configuration
  - `src/owlcompare/_version.py` — the single source of truth for the version (DD-013)
  - `CHANGELOG.md` (repo root) — Keep a Changelog history
  - `.github/workflows/release.yml` — tag-triggered publish to PyPI
  - `.github/workflows/release-test.yml` — tag-triggered staging publish to TestPyPI
  - `site_src/docs/contributing.md` — the human release runbook
  - `tests/unit/test_release.py` — static + build validation
- **Roadmap phase:** Phase 5 (final component)
- **Depends on components:** 01–21 (the whole package being released; Component 14
  for the bundled JSON schema that the wheel ships).
- **Depended on by:** the GitHub Action (Component 19) `owlcompare-version: latest`
  path, which can only `pip install owlcompare` once the package is on PyPI.

## Purpose

Turn the repository into an installable, published Python package so
`pip install owlcompare` / `uv tool install owlcompare` works from PyPI. It owns
the packaging metadata, the version-bump-to-publish workflow, and the safety rails
(tag/version agreement, metadata validation, TestPyPI staging) that keep a release
from going out wrong. Without it, the only install path is a pinned git commit and
the v1 exit criterion ("`uv tool install owlcompare` works from PyPI") cannot be met.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| `src/owlcompare/_version.py` `__version__` | str | maintainer edit | Single source of truth; pyproject reads it dynamically via Hatchling (DD-013). |
| Git tag `vX.Y.Z` | ref | maintainer `git push` | Triggers `release.yml`. Must equal `__version__`. |
| Git tag `pre/...` | ref | maintainer `git push` | Triggers `release.yml` (TestPyPI). |
| `CHANGELOG.md` `## [X.Y.Z]` section | markdown | maintainer edit | Becomes the GitHub Release body. |
| PyPI/TestPyPI Trusted Publisher config | OIDC | PyPI project settings | Keyed on workflow filename + environment name; no API token in the repo. |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `owlcompare-X.Y.Z-py3-none-any.whl` | wheel | PyPI / `pip` | Excludes `examples/fibo_demo/`; ships the bundled JSON schema. |
| `owlcompare-X.Y.Z.tar.gz` | sdist | PyPI / `pip` | Complete source incl. `examples/fibo_demo/`, specs, tests, docs. |
| PyPI release | package | end users | Published via OIDC Trusted Publishing. |
| GitHub Release | release | humans | Artifacts attached; body = the matching CHANGELOG section. |

## Public API

This component exposes no Python API. Its "surface" is the packaging metadata and
the two workflows. The one programmatic invariant: `owlcompare.__version__` (and
`owlcompare --version`) equal the published package version, all sourced from
`_version.py`.

## Internal design

- **Versioning (DD-013).** `pyproject.toml` declares `dynamic = ["version"]` and
  `[tool.hatch.version] path = "src/owlcompare/_version.py"`. There is **no**
  static `version =` field — a single source of truth, by design. Both workflows
  read the version back out of `_version.py` for the tag-match check.
- **Wheel vs. sdist split.** `[tool.hatch.build.targets.wheel]` sets
  `packages = ["src/owlcompare"]` and explicitly `exclude`s `examples/fibo_demo`
  (~3 MB of showcase data that is documentation, not importable code).
  `[tool.hatch.build.targets.sdist]` `include`s the full project — package, docs,
  specs, tests, and `examples/fibo_demo` — for a complete, reproducible tarball.
  The Component 14 JSON schema is mapped into the wheel via `force-include`.
- **`release.yml` (PyPI).** Trigger: tags `v*.*.*`. `permissions: { contents:
  write, id-token: write }`. Environment `pypi`. Steps: (1) reject any tag that
  isn't a strict `^v[0-9]+\.[0-9]+\.[0-9]+$` final release — the glob is coarse
  and still matches e.g. `v0.1.0a1`, so this is the real gate; (2) verify
  `tag − "v"` equals `_version.py`'s `__version__`; (3) `python -m build`;
  (4) `twine check dist/*`; (5) extract this version's CHANGELOG section with a
  literal `index()`-based awk match into `release-notes.md`; (6) publish via
  `pypa/gh-action-pypi-publish@release/v1` (OIDC, no token); (7) create a GitHub
  Release with `softprops/action-gh-release@v2`, body = `release-notes.md`,
  artifacts attached.
- **`release-test.yml` (TestPyPI).** Trigger: tags `pre/*`. `permissions:
  { contents: read, id-token: write }`. Environment `testpypi`. Same build +
  `twine check`, with a **base-version** tag/version check: a pre-release tag
  stages the *upcoming* release, so `_version.py` stays at the final version (e.g.
  `0.1.0`) while `pre/v0.1.0-rc1`, `-rc2`, … are cut. The check compares
  `Version.base_version` (dropping the rc/pre/post/dev suffix) and additionally
  requires the tag to actually *be* a pre-release (a final-release tag pushed here
  is rejected with a pointer to `release.yml`). Then publishes with
  `repository-url: https://test.pypi.org/legacy/`. **No** GitHub Release.
- **`scripts/validate_release_tag.py`.** The tag/version agreement logic is
  extracted here as two validators — `validate_final_tag` (exact match, for
  `release.yml`) and `validate_pre_tag` (base-version + pre-release, for
  `release-test.yml`) — so it is unit-tested rather than buried in workflow shell.
  `release-test.yml` calls it (`--mode pre`); `release.yml` keeps its strict inline
  guard unchanged.
- **Runbook.** `site_src/docs/contributing.md` documents bump → changelog →
  commit → tag → push, the TestPyPI staging dry run, the semver policy, and
  yank/recovery.

## Edge cases & failure modes

- Tag ≠ package version → workflow fails at the verify step (never publishes).
- Pre-release tag pushed to `release.yml` (e.g. `v0.1.0rc1`) → rejected with a
  pointer to `release-test.yml`.
- Re-tag of an already-published version → PyPI rejects the immutable upload;
  recovery is **yank + bump to the next patch**, documented in the runbook.
- Missing CHANGELOG section for the tag → release body falls back to a generic
  `owlcompare X.Y.Z` note rather than failing the release.
- A `## [version]` heading containing `[` would break a naive regex extraction →
  avoided by using a literal `index()` match, not a regex character class.

## Acceptance tests

Implemented in `tests/unit/test_release.py` (27 tests). Representative names:

- [x] `test_pyproject_has_required_pypi_fields`
- [x] `test_pyproject_has_project_urls`
- [x] `test_entry_point_targets_cli_main`
- [x] `test_version_is_dynamic_and_single_sourced`
- [x] `test_module_version_matches_runtime_export`
- [x] `test_wheel_excludes_fibo_demo` / `test_sdist_includes_fibo_demo`
- [x] `test_release_build` — builds real wheel + sdist and asserts the data split
- [x] `test_changelog_exists_and_is_keepachangelog`
- [x] `test_changelog_has_entry_for_current_version`
- [x] `test_release_yml_has_oidc_and_release_permissions`
- [x] `test_release_test_yml_has_oidc_permission`
- [x] `test_release_yml_publishes_to_pypi_not_testpypi`
- [x] `test_release_test_yml_publishes_to_testpypi`
- [x] `test_release_test_yml_does_not_create_github_release`
- [x] `test_workflow_actions_are_pinned` (no `@main` / `@master`)
- [x] `test_release_yml_validates_tag_against_version`

Manual gates (captured in the build summary): `python -m build` produces clean
artifacts, `twine check dist/*` PASSES for both, and the wheel installs and runs
in a fresh venv (`python -m owlcompare --version` → the released version).

## Out of scope

- Conda / system-package distribution.
- Signing artifacts (sigstore) — Trusted Publishing covers provenance for v1.
- Automated version bumping / release-please style automation; the bump is manual.
- Publishing the docs site (Component 20 owns `docs.yml`).
- Multi-package / monorepo publishing.

## Open questions

Resolved during the build (recorded as deviations in the build summary):

- [x] Static vs. dynamic version → **dynamic**, single-sourced in `_version.py`
      (DD-013); no static `version =` in pyproject.
- [x] Author email → **omitted** (name only) at the maintainer's request; PyPI
      requires only a name.
- [x] `examples/fibo_demo/` placement → **sdist yes, wheel no**.
- [x] Development Status classifier → **`3 - Alpha`**, consistent with the README.

## References

- `docs/DESIGN_DECISIONS.md` § DD-013 (Hatchling backend + dynamic version)
- `docs/ROADMAP.md` § Phase 5 (Component 22 entry, v0.1.0 planned tag)
- `CHANGELOG.md` — the v0.1.0 entry this pipeline publishes
- External: [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/),
  [Keep a Changelog](https://keepachangelog.com/), [PEP 440](https://peps.python.org/pep-0440/)
