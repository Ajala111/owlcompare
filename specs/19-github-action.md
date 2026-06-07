# Component 19: GitHub Action Wrapper

## Identity

- **Component number:** 19
- **Name:** GitHub Action wrapper
- **Module paths:**
  - `action.yml` (at repo root) — the Action metadata file (where GitHub looks for it)
  - `.github/actions/owlcompare/action.yml` — could alternatively live here for organizational tidiness; spec uses repo-root location for compatibility
  - `docs/github-action.md` — user-facing documentation for the Action
- **Roadmap phase:** Phase 5 (first component)
- **Depends on components:** 01–18 (the entire CLI). The Action is a thin wrapper; all logic lives in `owlcompare diff`.
- **Depended on by:** 21 (flagship ERA demo — uses the Action in its showcase repo)

## Purpose

Make owlcompare invocable as a three-line GitHub Actions workflow step. Handle the workflow-specific concerns (baseline detection, artifact upload, PR comment posting, build-status setting) so users don't have to. After this component, integrating owlcompare into a project's CI is a YAML edit, not a Python project.

What would break if we removed it: every CI integration would require users to script the workflow themselves — install Python, install owlcompare, figure out baseline checkout, manually upload artifacts, manually post comments. The adoption barrier rises from "three lines" to "an hour of YAML." Most users would skip the integration.

## Inputs

The Action accepts these inputs (declared in `action.yml`'s `inputs:` section):

| Name | Description | Required | Default |
|------|-------------|----------|---------|
| `ontology-path` | Path to the ontology file (relative to repo root) | yes | none |
| `baseline-ref` | Git ref to compare against (branch, tag, commit) | no | `${{ github.event.pull_request.base.ref }}` (auto: PR base) or `main` |
| `formats` | Comma-separated list of output formats to generate | no | `junit,html,markdown` |
| `python-version` | Python version to use | no | `3.11` |
| `owlcompare-version` | Specific owlcompare version (defaults to latest) | no | `latest` |
| `fail-on-breaking` | Whether to fail the CI build when breaking changes detected | no | `true` |
| `post-pr-comment` | Whether to post the Markdown report as a PR comment | no | `true` |
| `upload-artifacts` | Whether to upload HTML/JUnit reports as artifacts | no | `true` |
| `severity-config` | Path to a TOML severity config file | no | `''` (empty = no override) |
| `rename-mapping` | Path to a TOML rename mapping file | no | `''` |
| `rename-confidence` | Rename detection confidence threshold | no | `high` |
| `comment-marker` | Unique string identifying this Action's PR comments (for update-in-place) | no | `<!-- owlcompare-diff -->` |

## Outputs

The Action sets these outputs (accessible via `${{ steps.owlcompare.outputs.* }}`):

| Name | Description |
|------|-------------|
| `breaking-count` | Number of breaking changes |
| `total-changes` | Total number of changes |
| `report-html-path` | Path to the generated HTML report (in the runner's filesystem) |
| `report-junit-path` | Path to the JUnit XML |
| `report-markdown` | The Markdown content (escaped for use in subsequent steps) |
| `exit-code` | The owlcompare exit code (0, 10, etc.) |

## Public API

The `action.yml` file at the repo root declares the Action. Its structure (composite Action format):

```yaml
name: 'owlcompare ontology diff'
description: 'Diff OWL/RDF ontologies in CI with severity classification and rename detection'
author: 'phelz'
branding:
  icon: 'git-pull-request'
  color: 'blue'

inputs:
  # ...as declared above

outputs:
  breaking-count:
    description: 'Number of breaking changes detected'
    value: ${{ steps.diff.outputs.breaking-count }}
  # ...etc

runs:
  using: 'composite'
  steps:
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}

    - name: Install owlcompare
      shell: bash
      run: |
        if [ "${{ inputs.owlcompare-version }}" = "latest" ]; then
          pip install owlcompare
        else
          pip install "owlcompare==${{ inputs.owlcompare-version }}"
        fi

    - name: Check out baseline
      shell: bash
      run: |
        # ...detect baseline ref and check out into _baseline/
        git fetch origin ${{ inputs.baseline-ref }}
        git worktree add _baseline_owlcompare origin/${{ inputs.baseline-ref }}

    - name: Verify both ontology files exist
      shell: bash
      run: |
        # ...exit early if baseline file doesn't exist (new ontology, no diff possible)

    - name: Run owlcompare diff
      id: diff
      shell: bash
      run: |
        # ...build the command from inputs, capture outputs
        ...

    - name: Upload artifacts
      if: inputs.upload-artifacts == 'true' && steps.diff.outputs.has-artifacts == 'true'
      uses: actions/upload-artifact@v4
      with:
        name: owlcompare-diff-${{ github.run_id }}
        path: |
          owlcompare-report.html
          owlcompare-report.xml

    - name: Post PR comment
      if: inputs.post-pr-comment == 'true' && github.event_name == 'pull_request'
      uses: actions/github-script@v7
      with:
        script: |
          # ...read markdown report, find existing comment by marker, update or create

    - name: Set build status
      if: inputs.fail-on-breaking == 'true'
      shell: bash
      run: |
        if [ "${{ steps.diff.outputs.exit-code }}" = "10" ]; then
          echo "Breaking changes detected; failing build"
          exit 1
        fi
```

The exact YAML is fleshed out in implementation. The above is the structural outline.

## Internal design

### Baseline detection

The trickiest part of the Action. The `baseline-ref` input defaults to "auto," which means:

1. If running in a PR context (`github.event_name == 'pull_request'`): use `github.event.pull_request.base.ref` (the PR's target branch).
2. If running in a push to main: use the previous commit on the same branch (`HEAD~1`).
3. If running in a push to a tag: use the previous tag.
4. If running in a `workflow_dispatch` (manual trigger): require an explicit `baseline-ref` input.
5. Otherwise: default to `main` and warn that auto-detection couldn't determine the right baseline.

Each case is documented in the help text and tested manually.

### Baseline checkout

The Action uses `git worktree` to check out the baseline into a separate working directory (`_baseline_owlcompare/`), without disturbing the current checkout. This means:

- The PR's working tree stays at the PR commit
- The baseline working tree is at the baseline commit
- Both ontology files exist on disk simultaneously
- `owlcompare diff _baseline_owlcompare/path/to/ontology.ttl path/to/ontology.ttl` just works

The worktree is cleaned up at the end of the Action via `git worktree remove _baseline_owlcompare`.

### Edge case: ontology file doesn't exist at baseline

If the PR introduces a new ontology file (it doesn't exist on the baseline branch), there's no diff to compute. The Action:

1. Detects this case by checking `[ ! -f "_baseline_owlcompare/${{ inputs.ontology-path }}" ]`
2. Posts a PR comment saying "New ontology file detected; no diff to compute"
3. Exits successfully (no breaking changes, by definition)
4. Sets `outputs.breaking-count = 0` and `outputs.total-changes = 0`

Symmetric: if the PR deletes the ontology file, post a comment and exit (with an appropriate warning that all consumers will break).

### Running the diff

The Action constructs a command:

```bash
owlcompare diff \
  _baseline_owlcompare/${{ inputs.ontology-path }} \
  ${{ inputs.ontology-path }} \
  --format json \
  --out owlcompare-report.json
```

Then a second invocation for each requested format (JUnit, HTML, Markdown):

```bash
# For each format in formats:
owlcompare diff <baseline> <head> --format $format --out owlcompare-report.<ext>
```

The JSON output is parsed to extract the breaking count and total changes for the Action outputs.

Severity config and rename mapping flags are passed through if their inputs are set.

The exit code is captured but **not** propagated immediately — we want to do PR commenting and artifact upload *first*, then fail at the end if `fail-on-breaking` is true. This means a breaking change still results in a usable PR comment, not just a red build with no context.

### Artifact upload

Uses the standard `actions/upload-artifact@v4`. Artifact name includes `github.run_id` for uniqueness across multiple runs of the same PR.

Default artifacts: `owlcompare-report.html`, `owlcompare-report.xml`. The user can download the HTML report from the Action's run page.

### PR comment posting

Uses `actions/github-script@v7` with the GitHub API. The logic:

1. Read the Markdown report content from disk.
2. Construct the comment body: `{comment-marker}\n\n{markdown content}\n\n_Updated: {timestamp}_`.
3. List existing PR comments via the API.
4. Find any existing comment containing the `comment-marker`.
5. If found: update the existing comment (PATCH the API).
6. If not found: create a new comment (POST the API).

The comment-marker pattern lets the Action update the same comment across multiple pushes to the same PR, rather than spamming the PR with N comments.

If running outside a PR context (e.g., a push to main), this step is skipped.

### Build status

Standard GitHub behavior: if a step in a composite action calls `exit 1`, the overall step (and thus the workflow job) fails. The Action's final step checks `inputs.fail-on-breaking == 'true' && steps.diff.outputs.exit-code == '10'` and exits non-zero accordingly.

The check name in the PR appears as "owlcompare ontology diff" (taken from the Action's `name:`).

### Outputs

All the declared outputs are set via `echo "name=value" >> $GITHUB_OUTPUT` in the `Run owlcompare diff` step. They're available to subsequent workflow steps via `${{ steps.diff.outputs.* }}`.

The `report-markdown` output is escaped for use in workflow expressions. Multi-line Markdown is encoded via GitHub Actions' multi-line output syntax (using a unique delimiter).

## Versioning policy

The Action follows GitHub Actions versioning conventions:

- Users reference `phelz/owlcompare-action@v1` for the floating major-version tag (moved on minor/patch releases)
- Users reference `phelz/owlcompare-action@v1.0.0` for an immutable pin
- The `main` branch is the development branch; not for production use
- Breaking changes to the Action's input/output schema force a `v2` tag

The `action.yml` file lives at the repo root, but the project itself isn't *only* a GitHub Action — it's also a Python package. We expose the Action by tagging releases; the action.yml is part of the source tree.

## CLI integration

None. The Action *wraps* the CLI; the CLI itself is unchanged.

However: the Action surfaces a need for one minor CLI improvement worth noting in the spec for transparency:

**Observation:** the Action runs `owlcompare diff` multiple times (once per format) which is wasteful. A future enhancement (`--format A,B,C --out-template foo.{ext}`) would let one invocation produce multiple formats. This is a v1.1 improvement; the Action's design accommodates it via a future-compatible loop. Documented as a backlog item in `docs/ROADMAP.md`.

## Documentation

`docs/github-action.md` covers:

- **Quick start** — the three-line YAML snippet
- **Inputs reference** — every input documented
- **Outputs reference** — every output documented
- **Examples** — common scenarios (PR diff, scheduled diff, multi-ontology repo)
- **Troubleshooting** — common errors and fixes
- **Compatibility** — supported GitHub-hosted runners (Linux, macOS, Windows)

The doc is concise (~500 lines). It's the user-facing reference for anyone integrating owlcompare into their CI.

A "Quick start" excerpt should be added to the project README so users find the Action immediately.

## Edge cases & failure modes

- **Baseline ref doesn't exist** (e.g., `baseline-ref: nonexistent-branch`): the `git fetch` fails; log a clear error and exit 1.
- **Ontology file path is wrong**: the `owlcompare diff` invocation fails with exit code 4 (loader error). The Action propagates the error to the user.
- **Both ontology files identical** (no diff): the Action runs normally, exit code 0, "no changes" comment posted.
- **Action runs on a forked PR from an external contributor** (no write access to repo): the PR comment step fails silently because the fork can't write. The Action still uploads artifacts and reports status. Documented as a known limitation; suggest workaround via `pull_request_target` event for trusted PRs.
- **Multiple ontology files in one PR**: out of scope for v1. Users iterate the Action over multiple files in their workflow YAML.
- **The repo is a monorepo where owlcompare runs on a subdirectory**: use the `ontology-path` input pointing to the file; Action handles relative paths correctly.
- **The repo uses Git LFS for the ontology**: standard `actions/checkout` handles LFS via `lfs: true`; we document this in the Action's docs.
- **The owlcompare CLI version is incompatible** (older than what the Action assumes): pin a known-good version via `owlcompare-version` input. Default `latest` will track newest releases.
- **GitHub Actions runner doesn't have Python 3.11**: the `actions/setup-python` step installs it. Tested on `ubuntu-latest`, `macos-latest`, `windows-latest`.
- **Disk full / network timeout during pip install**: the Action fails clearly with the underlying error.

## Dependencies

The Action depends on these GitHub-marketplace actions:

- `actions/setup-python@v5` — Python installation
- `actions/upload-artifact@v4` — artifact upload
- `actions/github-script@v7` — PR comment posting

All are first-party (Actions org) or major-vendor (well-maintained). No third-party Action dependencies.

The owlcompare CLI itself is installed via `pip install owlcompare` (or the version pin). After Component 22 (PyPI release pipeline) ships, this works out of the box. **Prerequisite:** Component 22 must ship before Component 19 is fully usable by external users. For now, the Action works against a TestPyPI release or installs from this repo via `pip install git+https://github.com/phelz/owlcompare.git@v1.0.0`. Documented as a v1 limitation; the canonical install path becomes PyPI after Component 22.

## Acceptance tests

Located in `tests/unit/test_action_yml.py` (new), plus the manual CI smoke test.

### YAML structure tests

Static checks that `action.yml` is well-formed:

- [ ] `test_action_yml_is_valid_yaml` — parses without errors
- [ ] `test_action_yml_has_required_top_level_fields` — `name`, `description`, `runs`
- [ ] `test_action_yml_inputs_all_have_descriptions`
- [ ] `test_action_yml_outputs_all_have_descriptions`
- [ ] `test_action_yml_runs_using_is_composite`
- [ ] `test_action_yml_inputs_match_documented_set` — checks against `docs/github-action.md`'s listed inputs

These run via `pytest`; the YAML is parsed using stdlib `yaml` (already a transitive dependency through other tools; if not, add `PyYAML` as a dev dependency).

### Integration tests (manual)

These cannot be automated in pytest — they require an actual GitHub Actions runner.

The smoke test: create a test repo with two ontology files differing slightly, push it, configure the Action, open a PR, verify:

1. The Action runs to completion in <2 minutes
2. The Markdown PR comment appears on the PR
3. The HTML artifact is downloadable
4. The check status reflects breaking-change presence
5. Updating the PR (pushing a new commit) updates the existing comment in place
6. Re-running with the same setup produces a re-render of the existing comment (no spam)

Document the test repo URL in `docs/github-action.md` for transparency.

## Out of scope (deliberately)

- A Docker-based Action (composite is simpler and equally functional).
- A JavaScript-based Action (no Node.js code; composite is enough).
- Cross-repository diff (diff against an ontology in a different GitHub repo). Future feature.
- Slack/Teams/Email notification of results. Users can wire that themselves via subsequent workflow steps using the Action's outputs.
- A pre-built action for GitLab CI, Jenkins, etc. These can use the CLI directly; we document how. A "GitLab CI component" could be a future v1.1 addition.
- Caching of the Python environment between runs. The Action's runtime is dominated by ontology parsing, not pip install; caching is a 5-second optimization at most.
- A GitHub App that posts richer PR comments (with collapsible sections, inline annotations). Out of scope; the Markdown comment is sufficient.
- An automatic mode that detects which ontology files exist and runs the diff on all of them. Users specify the path; we don't guess.

## Open questions

- [ ] **Q1:** Should the Action support diffing against an arbitrary file outside the git history (e.g., a URL to a published ontology)?
  **Proposed:** No, not in v1. The use case is unclear and adds complexity. Users wanting this can run `owlcompare diff <url> <local>` directly in a shell step.

- [ ] **Q2:** Should the Action post the FULL Markdown report or just a summary on the PR comment? Real-world ontology diffs can have hundreds of changes.
  **Proposed:** Full Markdown. The Markdown renderer already truncates sections >50 changes with "...and N more." If users want a summary-only comment, they can pre-process the output. Most diffs are small enough that the full Markdown is fine.

- [ ] **Q3:** Should the comment-update logic try to *delete* the previous comment instead of editing it?
  **Proposed:** Edit, not delete-and-create. Edits preserve the comment's URL (other parts of the discussion may have linked to it). Updates appear inline on the PR ("edited 2 minutes ago"). Deletes lose context.

If you have a preference, override before implementing.

## References

- GitHub Actions documentation: https://docs.github.com/en/actions/creating-actions
- Composite actions reference: https://docs.github.com/en/actions/creating-actions/creating-a-composite-action
- `actions/setup-python`: https://github.com/actions/setup-python
- `actions/upload-artifact`: https://github.com/actions/upload-artifact
- `actions/github-script`: https://github.com/actions/github-script
- DD-005 (self-contained outputs make this Action trivial — we just upload the HTML/XML)
- Existing CI: `.github/workflows/ci.yml`
