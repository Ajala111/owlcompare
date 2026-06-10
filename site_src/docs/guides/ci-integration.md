# Use owlcompare in CI

The highest-leverage place to run owlcompare is your continuous-integration
pipeline: diff the ontology on every pull request, post the result where
reviewers will see it, and fail the build when a breaking change sneaks in. This
guide covers the GitHub Action first (the turnkey path), then GitLab CI and
Jenkins for everyone else.

## The three-line GitHub Action

Add `.github/workflows/ontology-diff.yml`:

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

On the next pull request you get three things:

- a **PR comment** with the Markdown diff, updated in place on each push (never
  duplicated),
- the **HTML report** and **JUnit XML** uploaded as a downloadable artifact, and
- a **check status** that turns red if there are breaking changes.

That's the whole setup. Everything below is optional tuning.

!!! note "Install path while owlcompare is pre-PyPI"
    Until owlcompare is published to PyPI, the `latest` install mode can only
    resolve inside the owlcompare repo itself. For your own repo, either wait for
    the PyPI release (after which `latest` just works) or pin a version once it's
    available. See the [Action's installation modes](https://github.com/Ajala111/owlcompare/blob/main/docs/github-action.md#installation-modes)
    for the details.

## How the Action works

It's a [composite action](https://docs.github.com/en/actions/creating-actions/creating-a-composite-action)
— pure YAML plus a little bash, gluing together first-party `actions/*` blocks.
No Docker image to pull, no Node bundle to build. Each run:

1. Sets up Python and installs owlcompare.
2. **Detects the baseline** to diff against and checks it out into a throwaway
   `git worktree`, so both versions of your ontology sit on disk at once.
3. Runs `owlcompare diff` and captures the change counts and exit code from the
   authoritative JSON run.
4. Uploads the HTML / JUnit / Markdown / JSON reports as an artifact.
5. Posts or updates the PR comment.
6. Fails the build if there were breaking changes and `fail-on-breaking` is on.

Commenting and artifact upload happen **before** the build is failed, so a red
build always comes with a usable report rather than a bare failure.

## Baseline detection

owlcompare needs a *baseline* version to diff your current ("head") ontology
against. With the default `baseline-ref: auto`, it picks the baseline from the
event:

| Trigger | Baseline used |
|---------|---------------|
| `pull_request` | The PR's **target branch**. |
| `push` to a branch | The **previous commit** (`HEAD~1`). |
| `push` to a tag | The **previous tag**. |
| `workflow_dispatch` | None — fails fast, asks for an explicit `baseline-ref`. |
| anything else | Falls back to `main` with a warning. |

Set `baseline-ref` explicitly (a branch, tag, or commit SHA) to override. If your
detection reaches back in history (`HEAD~1` or previous-tag), give `checkout`
enough history:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0   # needed for push/tag baseline detection
```

## Configuring `fail-on-breaking`

By default the Action fails the build on breaking changes. To **report without
blocking the merge**, turn it off:

```yaml
- uses: Ajala111/owlcompare@v1
  with:
    ontology-path: ontology/vehicles.ttl
    fail-on-breaking: "false"
```

To set your own policy — say, allow up to three breaking changes — disable the
built-in gate and act on the Action's outputs:

```yaml
- id: ontology
  uses: Ajala111/owlcompare@v1
  with:
    ontology-path: ontology/vehicles.ttl
    fail-on-breaking: "false"   # we'll decide ourselves

- name: Gate on a breaking-change budget
  shell: bash
  env:
    BREAKING: ${{ steps.ontology.outputs.breaking-count }}
  run: |
    echo "owlcompare found $BREAKING breaking changes."
    if [ "$BREAKING" -gt 3 ]; then
      echo "::error::more than 3 breaking changes — blocking."
      exit 1
    fi
```

The Action exposes `breaking-count`, `total-changes`, `report-html-path`,
`report-junit-path`, `report-markdown`, and `exit-code` as step outputs.

## Common inputs

| Input | Default | What it does |
|-------|---------|--------------|
| `ontology-path` | *(required)* | The file to diff, relative to the repo root. |
| `baseline-ref` | `auto` | What to diff against (see above). |
| `formats` | `junit,html,markdown` | Which reports to generate. |
| `fail-on-breaking` | `true` | Fail the build on breaking changes. |
| `post-pr-comment` | `true` | Post/update the Markdown comment. |
| `severity-config` | `''` | Path to a TOML severity-override file. |
| `rename-mapping` | `''` | Path to a TOML rename-mapping file. |
| `rename-confidence` | `high` | Lowest rename confidence to accept. |

The full reference — every input, output, and edge case — lives in the
[Action documentation on GitHub](https://github.com/Ajala111/owlcompare/blob/main/docs/github-action.md).

## Diffing several ontologies

The Action diffs one file per invocation. Use a matrix to fan out, with a
distinct comment marker per file so each ontology gets its own PR comment:

```yaml
jobs:
  diff:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        ontology: [ontology/vehicles.ttl, ontology/infrastructure.ttl]
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: Ajala111/owlcompare@v1
        with:
          ontology-path: ${{ matrix.ontology }}
          comment-marker: "<!-- owlcompare-diff:${{ matrix.ontology }} -->"
```

## GitLab CI

There's no owlcompare GitLab component yet, but the CLI is all you need. owlcompare
emits JUnit XML, which GitLab renders natively in the merge-request widget:

```yaml
ontology-diff:
  image: python:3.12-slim
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    - pip install owlcompare
    # Fetch the target branch's version of the ontology as the baseline.
    - git fetch origin "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
    - git show "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME:ontology/vehicles.ttl" > baseline.ttl
    - owlcompare diff baseline.ttl ontology/vehicles.ttl --format junit --out report.xml
  artifacts:
    when: always
    reports:
      junit: report.xml
```

The job's exit code (10 on breaking changes) fails the pipeline automatically. To
report without blocking, append `|| true` to the diff command and gate on the
JSON counts instead.

## Jenkins

In a declarative pipeline, generate the JUnit report and publish it with the
`junit` step:

```groovy
pipeline {
  agent { docker { image 'python:3.12-slim' } }
  stages {
    stage('Ontology diff') {
      steps {
        sh 'pip install owlcompare'
        sh 'git show origin/main:ontology/vehicles.ttl > baseline.ttl'
        // Don't let exit 10 abort the stage; we publish the report first.
        sh 'owlcompare diff baseline.ttl ontology/vehicles.ttl --format junit --out report.xml || true'
      }
    }
  }
  post {
    always {
      junit 'report.xml'
    }
  }
}
```

owlcompare's JUnit output is the broad-compatibility variant accepted by Jenkins,
GitLab, CircleCI, and the common GitHub test reporters, so the same `--format
junit` artifact works everywhere.

## Next steps

- [Severity overrides](severity-overrides.md) — tune what counts as breaking for
  your project.
- [Reading the HTML report](reading-html-report.md) — what reviewers see in the
  uploaded artifact.
- [Exit codes](../reference/exit-codes.md) — the contract CI relies on.
