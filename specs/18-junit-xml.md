# Component 18: JUnit XML Output

## Identity

- **Component number:** 18
- **Name:** JUnit XML output (CI integration format)
- **Module paths:**
  - `src/owlcompare/report/junit_report.py` — the renderer
- **Roadmap phase:** Phase 4 (final component — closes Phase 4)
- **Depends on components:** 14 (JSON schema — the data shape), 10 (severity — pass/fail mapping), 11/12 (rename consolidation), 12.5 (anonymous structure decoding)
- **Depended on by (planned):** 19 (GitHub Action — generates JUnit XML for automatic CI reporting), all CI integrations

## Purpose

Produce a JUnit XML report of a `DiffResult` for upload to CI systems (GitHub Actions, GitLab CI, Jenkins, CircleCI, etc.) where it renders as a native test-results dashboard. Each Change becomes a `testcase`; breaking changes become `<failure>` elements; non-breaking, additive, info, and rename changes pass. The result: any CI system with a JUnit reporter (i.e., all of them) shows ontology diffs as standard test results.

What would break if we removed it: every CI integration would have to either parse the JSON output and reimplement test-dashboard rendering, or post raw text/Markdown to PR comments. The "drop in three lines, get a dashboard" workflow wouldn't exist.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Diff result | `DiffResult` | Orchestrator output | Final, severity-refined, rename-consolidated, anonymous-structure-decoded |
| Snapshot metadata | from `result.a`, `result.b` | Source identification | Used in test suite name |
| Options | `JUnitOptions` | Optional | Suite name, timestamps, etc. |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| JUnit XML document | `str` | CLI stdout / `--out` file | UTF-8, valid against JUnit XML schema |

## Public API

```python
# src/owlcompare/report/junit_report.py

from dataclasses import dataclass
from .._common import DiffResult


@dataclass(frozen=True, slots=True)
class JUnitOptions:
    """Configuration for JUnit XML rendering."""
    suite_name: str | None = None       # Default: "owlcompare.diff"
    include_skipped: bool = False       # If True, info-severity changes become <skipped> instead of passing silently
    include_system_out: bool = True     # If True, embed the full text rendering as <system-out>
    timestamp: str | None = None        # ISO 8601; defaults to current time or SOURCE_DATE_EPOCH


def render(
    result: DiffResult,
    options: JUnitOptions | None = None,
) -> str:
    """Render a DiffResult as a JUnit XML document.

    Returns the full XML document as a string with XML declaration.
    Valid against the JUnit XML schema variant supported by GitHub Actions,
    GitLab CI, Jenkins, and the major CI systems.
    """
```

## CLI integration

Extend `--format` to include `junit`:

```
owlcompare diff [OPTIONS] ONTOLOGY_A ONTOLOGY_B

  --format [json|text|markdown|html|junit]    Output format
  --out PATH                                  Write output to file
  --junit-suite-name NAME                     Override the default testsuite name
  --junit-include-skipped                     Emit info-severity changes as <skipped>
```

A typical CI workflow:

```yaml
# .github/workflows/ontology-diff.yml
- run: owlcompare diff baseline.ttl pr-version.ttl --format junit --out junit.xml
- uses: dorny/test-reporter@v1
  with:
    name: Ontology Diff
    path: junit.xml
    reporter: java-junit
```

After this runs, the PR shows a native test-results dashboard with each ontology change as a discrete test case.

## Internal design

### Document structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="owlcompare" tests="{total}" failures="{breaking_count}" errors="0" skipped="{skipped_count}" time="0">
  <testsuite name="{suite_name}" tests="{total}" failures="{breaking_count}" errors="0" skipped="{skipped_count}" timestamp="{iso_timestamp}" time="0">
    {testcases}
    {if include_system_out}
    <system-out>{escaped_text_rendering}</system-out>
    {endif}
  </testsuite>
</testsuites>
```

The wrapping `<testsuites>` element is required by some consumers (Jenkins) and tolerated by others; we always emit it for maximum compatibility.

### Per-testcase rendering

Each Change becomes one `<testcase>`:

```xml
<testcase classname="{layer}.{kind}" name="{subject_or_summary_truncated}" time="0">
  {if severity == "breaking"}
  <failure type="{kind}" message="{summary}">{detailed_text}</failure>
  {elif severity == "info" and include_skipped}
  <skipped message="info-level change">{summary}</skipped>
  {endif}
  {if no failure/skipped}
  <!-- empty: this testcase passes -->
  {endif}
</testcase>
```

Where:

- `classname` follows JUnit convention `{module}.{class}` style. We use `{layer}.{kind}` so the CI dashboard groups by kind naturally (e.g., `structural.class_added` and `structural.class_removed` appear adjacent).
- `name` is the change's subject (entity IRI shortened) when present, otherwise a truncated form of `summary`. JUnit names should be ~60 chars max for dashboard readability; truncate longer names with `...`.
- `time` is always `0` — diff operations don't have meaningful per-change timing.
- `failure` element appears only for breaking severity. The `type` attribute is the kind; `message` is the one-line summary; the body is multi-line detailed text including the full IRI, before/after values, and (for renames) confidence/evidence.

### Severity → JUnit status mapping

| Severity | JUnit result | Reasoning |
|----------|--------------|-----------|
| `breaking` | `<failure>` | The diff has a breaking change; CI should mark the build as having found a problem |
| `non_breaking` | passes | The change is safe; no action needed |
| `additive` | passes | Pure addition; no action needed |
| `info` | passes (default) or `<skipped>` (with `--junit-include-skipped`) | Informational; user choice |
| (rename changes) | passes | A rename is by definition non-breaking |

This mapping aligns the JUnit dashboard's traffic light with the diff's actual safety status. A green build means "no breaking changes detected"; a red build means "at least one breaking change."

### Suite name resolution

The suite name appears as the dashboard's section header. Resolution order:

1. `options.suite_name` (programmatic)
2. CLI `--junit-suite-name` flag
3. Default: `"owlcompare.diff"` (a stable identifier that aggregates well across runs)

Source paths are *not* used in the suite name (they tend to be absolute paths or temp paths that make dashboards messy).

### Failure body content

The `<failure>` body should be useful in the CI dashboard's expandable view:

```
Breaking change detected: Object property removed
  Entity:    http://data.europa.eu/949/locatedOn
  Kind:      object_property_removed
  Label:     "located on"@en
  Severity:  breaking

Details:
  This property is removed in B. Consumers that referenced it will break.

  Subsumed Layer 0 triples:
    - era:locatedOn rdf:type owl:ObjectProperty
    - era:locatedOn rdfs:domain era:Track
    - era:locatedOn rdfs:range era:Station
    - era:locatedOn rdfs:label "located on"@en

Refer to the full owlcompare report for context.
```

The format is plain text (not XML inside the CDATA). It's readable in the dashboard's "view details" panel. The full Change.details is *not* dumped — that would be noisy; only the user-relevant fields.

### `<system-out>` integration

When `include_system_out` is True (the default), the entire text-format rendering of the diff is embedded as a `<system-out>` element on the testsuite:

```xml
<system-out><![CDATA[
... full text-format diff output here ...
]]></system-out>
```

This means the *entire diff*, not just failures, is captured in the JUnit XML. CI dashboards that display `<system-out>` (most do) will show the full rendering as a kind of "build log" alongside the per-change testcases.

The text rendering is the same as `--format text` output, with ANSI color codes stripped (rich's `console.export_text()` produces plain text).

### XML escaping

All user-supplied content (IRIs, labels, comments, evidence strings, source paths) is XML-escaped:
- `&` → `&amp;`
- `<` → `&lt;`
- `>` → `&gt;`
- `"` → `&quot;` (in attribute values)
- `'` → `&#39;` (in attribute values)

Within `<system-out><![CDATA[...]]></system-out>`, no escaping is needed for `<` or `>` inside the CDATA, but `]]>` sequences must be split (CDATA cannot contain `]]>`). The escape strategy: replace `]]>` with `]]]]><![CDATA[>` inside the CDATA content.

### Determinism

Like the HTML renderer, JUnit XML output is deterministic:
- Testcases are sorted by `(classname, name)` — same order across runs
- Timestamps honor `SOURCE_DATE_EPOCH` for reproducible builds
- Attribute order on elements is stable

### Validation

The output validates against the JUnit XML schema variants supported by:
- GitHub Actions (via `dorny/test-reporter`, `EnricoMi/publish-unit-test-result-action`)
- GitLab CI (built-in JUnit support)
- Jenkins (built-in JUnit plugin)
- CircleCI (`store_test_results`)

These all use roughly the same schema; our output is the intersection that all of them accept.

The full schema reference: https://github.com/testmoapp/junitxml — the de facto community-maintained reference.

We do NOT validate against a schema at runtime (no dependency on lxml or similar). The output is built from string templates and tested via integration with at least one real CI parser.

## Edge cases & failure modes

- **Empty diff (no changes):** emit a valid JUnit XML with one passing testcase named `"no-changes"`. CI dashboards expect at least one testcase; an empty `<testsuite>` is invalid in some parsers.
- **Changes with no `subject`** (rare, mostly Layer 0): use the change's `summary` field as the testcase name, truncated to 60 chars.
- **Very long IRIs:** truncate testcase `name` to 60 chars with ellipsis. Full IRI appears in the `<failure>` body.
- **Special XML characters in labels** (`<`, `>`, `&`): escaped via the standard XML escape function. Tested with malicious inputs.
- **Identical sources (user diffed a file against itself):** one passing testcase `"no-changes"`.
- **The diff has only `info`-severity changes:** all testcases pass (or are `<skipped>` with the flag). Suite still emits as a successful run.
- **A breaking change with no `summary` (defensive):** use `f"breaking change of kind {kind}"` as the failure message.
- **`<system-out>` would exceed CI parser limits:** some CI systems truncate `<system-out>` over 100KB. For very large diffs, the embedded text rendering might be truncated by the CI side; we don't preemptively truncate. Users with very large diffs can use `--no-junit-system-out` (out of scope; not implemented).

## Dependencies to add

None. Pure stdlib `xml.sax.saxutils.escape` for escaping; everything else is string templating.

## Acceptance tests

Located in `tests/unit/test_junit_report.py` (new), extensions to `tests/unit/test_cli_diff.py`, extensions to `tests/integration/test_diff_integration.py`.

### Fixtures to add (`tests/fixtures/junit/`)

Goldens — captured JUnit XML outputs, parsed and compared structurally (not byte-for-byte; XML allows attribute reordering). For simplicity, we use string-equality goldens with deterministic output (sorted attributes, fixed indentation, stable timestamps).

Fixtures:
- `empty.xml` — diff with no changes.
- `era_evolution.xml` — the canonical 5-change diff with mixed severities.
- `era_renames.xml` — rename-heavy diff.
- `breaking_only.xml` — all-breaking diff (every testcase fails).
- `non_breaking_only.xml` — no breaking changes (all pass).
- `escaping_specials.xml` — labels with `<`, `&`, etc.
- `with_info_skipped.xml` — `--junit-include-skipped` enabled.

### Test list

**`tests/unit/test_junit_report.py`:**

- [x] `test_render_returns_valid_xml_declaration`
- [x] `test_render_includes_testsuites_root_element`
- [x] `test_render_includes_testsuite_with_name`
- [x] `test_render_counts_total_tests_correctly`
- [x] `test_render_counts_failures_correctly` — breaking count
- [x] `test_render_counts_skipped_correctly` — when flag enabled
- [x] `test_render_breaking_change_emits_failure_element`
- [x] `test_render_non_breaking_change_no_failure`
- [x] `test_render_additive_change_no_failure`
- [x] `test_render_info_change_passes_by_default`
- [x] `test_render_info_change_skipped_when_flag_enabled`
- [x] `test_render_rename_change_passes`
- [x] `test_render_testcase_classname_format` — layer.kind
- [x] `test_render_testcase_name_uses_subject_when_available`
- [x] `test_render_testcase_name_truncates_long_iris`
- [x] `test_render_failure_type_is_kind`
- [x] `test_render_failure_message_is_summary`
- [x] `test_render_failure_body_includes_iri_and_details`
- [x] `test_render_failure_body_includes_subsumes_when_present`
- [x] `test_render_system_out_when_enabled`
- [x] `test_render_system_out_contains_text_rendering`
- [x] `test_render_system_out_omitted_when_disabled`
- [x] `test_render_system_out_escapes_cdata_terminator`
- [x] `test_render_suite_name_default`
- [x] `test_render_suite_name_override`
- [x] `test_render_xml_escapes_special_chars_in_labels`
- [x] `test_render_xml_escapes_quotes_in_attributes`
- [x] `test_render_xml_escapes_ampersand_in_iris`
- [x] `test_render_testcases_sorted_by_classname_then_name`
- [x] `test_render_timestamp_honors_source_date_epoch`
- [x] `test_render_output_is_deterministic`
- [x] `test_render_empty_diff_emits_no_changes_testcase`
- [x] `test_render_change_without_subject_uses_summary_as_name`
- [x] `test_render_xml_validates_against_jenkins_schema` — basic well-formedness via xml.etree.ElementTree.parse
- [x] `test_render_golden_era_evolution`
- [x] `test_render_golden_era_renames`
- [x] `test_render_golden_breaking_only`
- [x] `test_render_golden_escaping_specials`
- [x] `test_render_golden_with_info_skipped`
- [x] `test_render_golden_empty`

**`tests/unit/test_cli_diff.py` extensions:**

- [x] `test_cli_diff_format_junit_writes_to_stdout`
- [x] `test_cli_diff_format_junit_writes_to_out_file`
- [x] `test_cli_diff_junit_suite_name_flag_overrides_default`
- [x] `test_cli_diff_junit_include_skipped_flag_emits_skipped_elements`
- [x] `test_cli_diff_format_junit_exit_code_matches_severity` — JUnit rendering doesn't affect exit code

**`tests/integration/test_diff_integration.py` extensions:**

- [x] `test_era_evolution_junit_output_matches_golden`
- [x] `test_era_renames_junit_output_matches_golden`
- [x] `test_junit_output_parseable_by_etree` — round-trip through `xml.etree.ElementTree`

## Manual verification

Beyond automated tests:

- [ ] Render `era_evolution` to JUnit XML, upload as artifact in a GitHub Actions workflow, verify the test-reporter action renders it correctly
- [ ] Same with GitLab CI (if you have a GitLab account handy)
- [ ] Parse the output through `xmllint --noout junit.xml` — no errors

The GitHub Actions verification is the most important manual step. The Component 19 (GitHub Action wrapper) will codify this, but for Component 18, eyeball verification that the output renders correctly in at least one CI dashboard.

## Out of scope (deliberately)

- A "rich" XML format that captures more than JUnit can represent. The strength of JUnit XML is its universal CI support; richer formats lose that.
- TeamCity-specific service messages (a competing format with TeamCity-only support). Out of scope.
- A "JUnit JSON" variant (some niche CI tools accept it). Out of scope.
- Validation against a formal XML schema (XSD) at build time. The integration tests verify well-formedness; that's sufficient.
- Per-testcase timing (`time="0.123"`). Diff operations don't have meaningful per-change timing.
- `<properties>` element with diff metadata. Could be useful but adds complexity; skip for v1.
- Attaching the JSON output as a `<system-err>` element. Redundant with `--format json` output.
- Configurable failure thresholds (e.g., "treat additive as failures"). Out of scope; users wanting different mapping can post-process.

## Open questions

- [x] **Q1:** Should the suite name include source identifiers (e.g., `"owlcompare.diff: a.ttl vs b.ttl"`)? Or stay generic (`"owlcompare.diff"`)?
  **Resolved (as proposed):** Stay generic — the default `testsuite` name is `"owlcompare.diff"`, with no source paths. Users override via `--junit-suite-name` / `JUnitOptions.suite_name`.

- [x] **Q2:** Should `<system-out>` include the full text rendering or a condensed summary?
  **Resolved (as proposed):** Full text rendering. `_render_system_out` embeds the complete `diff_text_plain` output (Component 05) in a CDATA section. `include_system_out` (default `True`) toggles it off programmatically; the `--no-junit-system-out` CLI flag remains out of scope.

- [x] **Q3:** Should we emit `<system-err>` for warnings (e.g., "user mapping references stale IRI" log lines)? Or skip stderr capture?
  **Resolved (as proposed):** Skip. No `<system-err>` is emitted; runtime warnings stay on the process's actual stderr.

**Implementation deviations from the sketch (all minor):**
- The `<failure>` body shows the **full** entity IRI on the `Entity:` line (per § Failure body content, which prints the full IRI), while the testcase `name` uses the compact prefixed form (`era:locatedOn`) for dashboard readability. `subsumes` is rendered as the subsumed Layer 0 *change ids* (what the array actually carries), under a "Subsumed Layer 0 changes:" heading.
- The empty-diff "no-changes" testcase uses `classname="owlcompare.diff"`.
- The seven golden fixtures are `empty.xml`, `era_evolution.xml`, `era_renames.xml`, `breaking_only.xml`, `non_breaking_only.xml`, `escaping_specials.xml` (the `<script>`/`&`/quote label, which lands in `<system-out>` CDATA), and `with_info_skipped.xml`. `escaping_specials` reuses `tests/fixtures/diff/html_escaping_*.ttl`; `non_breaking_only` reuses `widened_range_*.ttl`. Goldens are locked byte-for-byte (the spec's "structural comparison" allowance is unused — deterministic output makes exact equality simpler).

## References

- JUnit XML format reference: https://github.com/testmoapp/junitxml
- GitHub Actions test reporters:
  - https://github.com/dorny/test-reporter
  - https://github.com/EnricoMi/publish-unit-test-result-action
- DD-005 (self-contained outputs), DD-008 (severity), DD-019 (JSON schema versioning)
- `docs/schema/diff-result.schema.json` — the data shape we render from
- `src/owlcompare/report/markdown_report.py` — the precedent renderer pattern
