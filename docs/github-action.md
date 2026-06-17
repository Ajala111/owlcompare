# owlcompare GitHub Action

Diff your OWL/RDF ontologies on every pull request, with severity-classified
changes, rename detection, an interactive HTML report, and a JUnit dashboard —
all from a three-line workflow step.

This page is the complete reference for the Action. If you just want to get
going, jump to [Quick start](#quick-start). For the design rationale, see
[`specs/19-github-action.md`](../specs/19-github-action.md).

---

## Contents

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Inputs](#inputs)
- [Outputs](#outputs)
- [Baseline detection](#baseline-detection)
- [Examples](#examples)
  - [1. Diff an ontology on every pull request](#1-diff-an-ontology-on-every-pull-request)
  - [2. Pin a baseline branch and a version](#2-pin-a-baseline-branch-and-a-version)
  - [3. Use the Action's outputs in later steps](#3-use-the-actions-outputs-in-later-steps)
  - [4. Diff several ontologies in one repo](#4-diff-several-ontologies-in-one-repo)
  - [5. Scheduled drift check against main](#5-scheduled-drift-check-against-main)
- [Installation modes](#installation-modes)
- [Permissions](#permissions)
- [Troubleshooting](#troubleshooting)
- [Compatibility](#compatibility)
- [Known limitations](#known-limitations)
- [Versioning](#versioning)

---

## Quick start

Add this to `.github/workflows/ontology-diff.yml`:

```yaml
name: Ontology diff

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write   # required for the PR comment

jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Ajala111/owlcompare@v1
        with:
          ontology-path: ontology/my-ontology.ttl
```

On the next pull request you get:

- a **PR comment** with the Markdown diff (updated in place on each push, never
  duplicated),
- the **HTML report** and **JUnit XML** uploaded as a downloadable artifact, and
- a **check status** that turns red if there are breaking changes.

That's it. Everything below is optional tuning.

---

## How it works

The Action is a [composite action](https://docs.github.com/en/actions/creating-actions/creating-a-composite-action):
pure YAML plus a little bash, gluing together first-party `actions/*` building
blocks. There is no Docker image to pull and no Node.js bundle to build. Each run
performs these steps:

1. **Set up Python** (`actions/setup-python`) at the requested version.
2. **Install owlcompare** (see [Installation modes](#installation-modes)).
3. **Detect the baseline** and check it out into a throwaway `git worktree` at
   `_baseline_owlcompare/`, so both the baseline and head versions of your
   ontology sit on disk at once.
4. **Run `owlcompare diff`** once per requested format. The JSON run is the
   authoritative one — it produces the change counts and the exit code.
5. **Upload artifacts** (`actions/upload-artifact`) — the HTML, JUnit XML,
   Markdown, and JSON reports.
6. **Post (or update) a PR comment** (`actions/github-script`) with the Markdown
   report, found by a hidden marker so the same comment is edited rather than
   re-posted.
7. **Set the build status** — fail the job if breaking changes were found and
   `fail-on-breaking` is `true`.
8. **Clean up** the baseline worktree.

The order matters: commenting and artifact upload happen *before* the build is
failed, so a red build always comes with a usable report rather than a bare
failure.

---

## Inputs

| Name | Description | Required | Default |
|------|-------------|----------|---------|
| `ontology-path` | Path to the ontology file, relative to the repo root. | **yes** | — |
| `baseline-ref` | Git ref to diff against. `auto` resolves per the [baseline-detection algorithm](#baseline-detection). | no | `auto` |
| `formats` | Comma-separated output formats: `junit`, `html`, `markdown`, `json`. | no | `junit,html,markdown` |
| `python-version` | Python version for `actions/setup-python`. | no | `3.11` |
| `owlcompare-version` | `latest`, `local`, or an exact version (see [Installation modes](#installation-modes)). | no | `latest` |
| `fail-on-breaking` | Fail the build when breaking changes are detected. | no | `true` |
| `post-pr-comment` | Post the Markdown report as a PR comment (no-op outside a PR). | no | `true` |
| `upload-artifacts` | Upload HTML/JUnit/Markdown/JSON reports as a workflow artifact. | no | `true` |
| `severity-config` | Path to a TOML severity-override config (empty = built-in rules). | no | `''` |
| `rename-mapping` | Path to a TOML rename-mapping file (empty = automatic detection). | no | `''` |
| `rename-confidence` | Lowest rename confidence to accept: `certain`, `high`, `medium`, `none`. | no | `high` |
| `comment-marker` | Hidden marker identifying this Action's PR comment, for update-in-place. | no | `<!-- owlcompare-diff -->` |

### Notes on specific inputs

- **`ontology-path`** is a single file. To diff several ontologies, run the
  Action once per file — see [Example 4](#4-diff-several-ontologies-in-one-repo).
- **`formats`** controls which reports are generated. The Markdown report is
  always available for the PR comment even if you omit it here; listing it just
  ensures it's also uploaded as an artifact.
- **`severity-config`** and **`rename-mapping`** are paths *within your repo*
  (the head checkout). Leave them empty to use owlcompare's defaults.
- **`rename-confidence: none`** disables rename detection entirely; add+remove
  pairs are then reported as separate changes.

---

## Outputs

| Name | Description |
|------|-------------|
| `breaking-count` | Number of breaking changes detected. |
| `total-changes` | Total number of changes (all severities). |
| `report-html-path` | Filesystem path to the HTML report (empty if not generated). |
| `report-junit-path` | Filesystem path to the JUnit XML (empty if not generated). |
| `report-markdown` | The Markdown report content, for use in later steps. |
| `exit-code` | The owlcompare exit code: `0` (no breaking changes) or `10` (breaking). |

Reference these from a later step via `steps.<id>.outputs.<name>` — see
[Example 3](#3-use-the-actions-outputs-in-later-steps).

---

## Baseline detection

The Action needs a *baseline* version of your ontology to diff the current
("head") version against. With `baseline-ref: auto` (the default), it resolves
the baseline from the workflow event:

| Trigger | Baseline used |
|---------|---------------|
| `pull_request` / `pull_request_target` | The PR's **target (base) branch** (`github.event.pull_request.base.ref`). |
| `push` to a branch (e.g. `main`) | The **previous commit**, `HEAD~1`. |
| `push` to a tag | The **previous tag** reachable from the pushed tag. |
| `workflow_dispatch` | **None** — the run fails fast and asks for an explicit `baseline-ref`. |
| anything else | Falls back to **`main`** with a warning. |

Set `baseline-ref` explicitly (a branch, tag, or commit SHA) to override this
entirely. An explicit ref is always honoured verbatim.

### Checkout depth

Auto-detection that reaches *back* in history needs that history present:

- **`HEAD~1`** (branch push) requires at least two commits of history. The Action
  runs `git fetch --deepen=1`, which is enough in most cases, but for safety set
  `fetch-depth: 2` (or `0`) on `actions/checkout`.
- **Previous tag** detection requires tags. The Action fetches them, but a full
  history (`fetch-depth: 0`) is the most reliable.

For the common `pull_request` case, the default shallow checkout is fine — the
Action fetches the base branch on demand.

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0   # needed for push/tag baseline detection
```

### New or deleted ontology files

- If the ontology **doesn't exist at the baseline** (a brand-new file), there's
  nothing to diff. The Action posts a "new ontology file" comment, reports zero
  changes, and succeeds.
- If the ontology **was deleted** in the change, the Action posts a warning
  comment ("every consumer that imports this ontology will break") and succeeds —
  there's no head version to diff.

---

## Examples

### 1. Diff an ontology on every pull request

The canonical setup. Comments on the PR, uploads reports, fails on breaking
changes.

```yaml
name: Ontology diff
on:
  pull_request:
permissions:
  contents: read
  pull-requests: write
jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Ajala111/owlcompare@v1
        with:
          ontology-path: ontology/era.ttl
```

### 2. Pin a baseline branch and a version

Diff against a fixed `release` branch instead of the PR base, pin a specific
owlcompare version for reproducibility, and only generate the HTML report.

```yaml
- uses: Ajala111/owlcompare@v1
  with:
    ontology-path: ontology/era.ttl
    baseline-ref: release
    owlcompare-version: "1.0.0"
    formats: html
    fail-on-breaking: "false"   # report, but never block the merge
```

### 3. Use the Action's outputs in later steps

Capture the diff results and act on them — for example, fail only when there are
"too many" breaking changes, or feed the counts into a notification.

```yaml
- id: ontology
  uses: Ajala111/owlcompare@v1
  with:
    ontology-path: ontology/era.ttl
    fail-on-breaking: "false"   # we'll decide ourselves below

- name: Gate on breaking-change budget
  shell: bash
  env:
    BREAKING: ${{ steps.ontology.outputs.breaking-count }}
    TOTAL: ${{ steps.ontology.outputs.total-changes }}
  run: |
    echo "owlcompare found $TOTAL changes, $BREAKING breaking."
    if [ "$BREAKING" -gt 3 ]; then
      echo "::error::more than 3 breaking changes ($BREAKING) — blocking."
      exit 1
    fi
```

The Markdown report is also available as `steps.ontology.outputs.report-markdown`
if you want to forward it to Slack, an issue body, etc.

### 4. Diff several ontologies in one repo

The Action diffs one file per invocation. Use a matrix to fan out across several.

```yaml
jobs:
  diff:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        ontology:
          - ontology/era.ttl
          - ontology/vehicles.ttl
          - ontology/infrastructure.ttl
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: Ajala111/owlcompare@v1
        with:
          ontology-path: ${{ matrix.ontology }}
          # A distinct marker per file keeps each ontology's PR comment separate.
          comment-marker: "<!-- owlcompare-diff:${{ matrix.ontology }} -->"
```

### 5. Scheduled drift check against main

Run nightly against `main` to catch drift, and post results to the run summary
rather than a PR.

```yaml
on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:
    inputs:
      baseline:
        description: Baseline ref
        default: main
jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - id: ontology
        uses: Ajala111/owlcompare@v1
        with:
          ontology-path: ontology/era.ttl
          # scheduled/dispatch runs have no PR base, so name the baseline.
          baseline-ref: ${{ github.event.inputs.baseline || 'main' }}
          post-pr-comment: "false"
      - name: Summarise
        shell: bash
        run: |
          echo "${{ steps.ontology.outputs.report-markdown }}" >> "$GITHUB_STEP_SUMMARY"
```

---

## Installation modes

The `owlcompare-version` input selects how the CLI is installed:

| Value | Behaviour |
|-------|-----------|
| `latest` *(default)* | `pip install owlcompare` from PyPI. If that fails, falls back to a git install of the exact commit — see the note below. |
| `local` | `pip install -e .` against the checked-out repository. Used to self-test the Action against live code (the smoke-test workflow uses this). |
| *exact version* (e.g. `1.0.0`) | `pip install owlcompare==1.0.0`. |

**Installing from source (development workflows within the owlcompare repo):**

- You can install a pinned commit directly in a shell step *before* the Action,
  then set `owlcompare-version` to that installed version. This is useful for
  testing an unreleased commit; most users should just use `latest` (PyPI).

  ```yaml
  - run: pip install "git+https://github.com/Ajala111/owlcompare.git@v1.0.0"
  ```

- The built-in **git fallback** in `latest` mode installs from
  `github.com/${{ github.repository }}@${{ github.sha }}`. That only resolves to
  owlcompare when the workflow runs *inside the owlcompare repository itself*
  (i.e. during development / the smoke test). It is **not** a general install
  path for external repos — for those, the canonical path is `latest` (PyPI) or
  an explicit version.

---

## Permissions

The Action needs:

```yaml
permissions:
  contents: read          # check out the baseline
  pull-requests: write    # post/update the PR comment
```

If you set `post-pr-comment: false`, `pull-requests: write` is not required.

GitHub workflows triggered by `pull_request` from a **fork** run with a read-only
`GITHUB_TOKEN`; the comment step will fail to write and the Action **warns
instead of failing** — artifacts and the check status still report the result.
See [Known limitations](#known-limitations).

---

## Troubleshooting

**The PR comment never appears.**
Check that the job grants `pull-requests: write` and that the trigger is
`pull_request`. For forked PRs, the comment is skipped by design (read-only
token). Look for a `Could not post the PR comment` warning in the run log.

**`could not resolve HEAD~1`.**
You're on a push to a branch with a shallow checkout and only one commit of
history available. Add `fetch-depth: 2` (or `0`) to `actions/checkout`.

**`failed to fetch baseline ref '<x>'`.**
The `baseline-ref` you supplied doesn't exist on the remote. Check the branch/tag
name, or use a commit SHA. For a brand-new repo with no `main` yet, set
`baseline-ref` explicitly.

**`workflow_dispatch runs require an explicit 'baseline-ref' input`.**
Manual runs can't guess a baseline. Pass `baseline-ref` (e.g. `main`) — see
[Example 5](#5-scheduled-drift-check-against-main).

**`ontology file '<path>' was not found`.**
The `ontology-path` is wrong, or the file doesn't exist at *either* version.
Paths are relative to the repo root. In a monorepo, point straight at the file
(e.g. `packages/ont/era.ttl`).

**`owlcompare diff failed with exit code 4`.**
A loader error — the ontology couldn't be parsed (malformed Turtle/RDF, an
unsupported feature like named graphs, etc.). Run `owlcompare diff` locally on
the same files to see the full message.

**The install step fails for an external repo.**
owlcompare isn't on PyPI yet — see [Installation modes](#installation-modes).

**Git LFS-stored ontology isn't found.**
Enable LFS on checkout: `actions/checkout@v4` with `lfs: true`.

---

## Compatibility

- **Runners:** Linux (`ubuntu-latest`), macOS (`macos-latest`), and Windows
  (`windows-latest`). The Action's `run:` steps use `shell: bash`, which is
  available on all three GitHub-hosted runners (via Git Bash on Windows).
- **Python:** 3.11+ (owlcompare's minimum). Set `python-version` to pick.
- **Dependency actions:** `actions/setup-python@v5`, `actions/upload-artifact@v4`,
  `actions/github-script@v7` — all first-party.
- **CI consumers of the JUnit XML:** the JUnit report is the broad-compatibility
  variant accepted by GitHub test reporters (`dorny/test-reporter`,
  `EnricoMi/publish-unit-test-result-action`), GitLab CI, Jenkins, and CircleCI.

---

## Known limitations

- **Forked PRs can't be commented on.** The read-only token on fork PRs means the
  comment step warns and skips. For trusted forks you *can* use the
  `pull_request_target` event (which runs with the base repo's token) — but only
  do so if you understand the [security
  implications](https://securitylab.github.com/research/github-actions-preventing-pwn-requests/),
  since it runs with write access against PR-controlled content.
- **One ontology per invocation.** Use a matrix for multiple files
  ([Example 4](#4-diff-several-ontologies-in-one-repo)).
- **Multiple diff invocations.** The Action runs `owlcompare diff` once per
  requested format. A future CLI enhancement (one run, many outputs) will collapse
  this; it's tracked in [`docs/ROADMAP.md`](ROADMAP.md). The cost is small —
  runtime is dominated by parsing, not process startup.

---

## Versioning

The Action follows GitHub Actions conventions:

- `Ajala111/owlcompare@v1` — the floating major tag (moves on minor/patch releases).
- `Ajala111/owlcompare@v1.0.0` — an immutable pin.
- `main` is the development branch; don't depend on it in production.
- Breaking changes to the input/output schema bump the major tag to `v2`.

`action.yml` lives at the repo root because that's where GitHub looks when a user
references `owner/repo@ref`. owlcompare is *also* a Python package; the Action is
exposed by tagging releases of the same source tree.

---

## See also

- [`specs/19-github-action.md`](../specs/19-github-action.md) — the component spec.
- [`specs/15-markdown-report.md`](../specs/15-markdown-report.md) — the Markdown
  posted as the PR comment.
- [`specs/18-junit-xml.md`](../specs/18-junit-xml.md) — the JUnit XML uploaded as
  an artifact.
- The smoke-test workflow:
  [`.github/workflows/action-smoke-test.yml`](../.github/workflows/action-smoke-test.yml).
