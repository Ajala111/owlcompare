# Component 10: Severity Classifier

## Identity

- **Component number:** 10
- **Name:** Severity classifier (Phase 2 polish pass)
- **Module paths:**
  - `src/owlcompare/diff/severity.py` — the classifier
  - `src/owlcompare/diff/_severity_rules.py` — the rules registry (built-in and user-defined)
  - `src/owlcompare/severity_config.py` — config file loading (TOML)
- **Roadmap phase:** Phase 2 (final component)
- **Depends on components:** 02 (model), 05–09 (everything that emits Change records), the orchestrator
- **Depended on by (planned):** 14–17 (renderers — they consume the refined severities), 18 (JUnit XML output — exit-code-driven), 19 (GitHub Action)

## Purpose

Refine and finalize severity classifications on `DiffResult.changes` with cross-cutting context that no single Layer 1 slice has. Accept user-supplied severity overrides via a config file or CLI flag. Return a new `DiffResult` with the same changes but refined severities, ready for rendering and exit-code computation.

What would break if we removed it: severity would remain per-slice and inconsistent. Cross-cutting cases (annotation changes on deprecated entities, consequential restriction removals after property removal, etc.) would get the same severity as standalone cases, misrepresenting their importance. Users would have no escape hatch for project-specific severity conventions.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Diff result | `DiffResult` | Orchestrator output | All Layer 0 + Layer 1 changes with default severities |
| Severity config | `SeverityConfig` | Optional, from file or programmatic | User-supplied overrides |
| Options | `DiffOptions` | Optional | Currently unused; future knobs |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| Refined `DiffResult` | dataclass | Renderers + exit code | Same `changes`, severities possibly different; refinement audit trail in metadata |

## Public API

```python
# src/owlcompare/diff/severity.py

from dataclasses import dataclass
from .._common import Change, DiffResult, DiffOptions, Severity
from ..severity_config import SeverityConfig


@dataclass(frozen=True, slots=True)
class SeverityRefinement:
    """A record of one severity change made by Component 10.

    Useful for debugging and for --explain-severity output (future).
    """
    change_id: str
    original_severity: Severity
    refined_severity: Severity
    rule_id: str               # e.g., 'annotation-on-deprecated', 'user-override'
    rationale: str             # short human description


def refine(
    result: DiffResult,
    config: SeverityConfig | None = None,
    options: DiffOptions | None = None,
) -> DiffResult:
    """Apply cross-cutting severity rules and user overrides to a DiffResult.

    Returns a new DiffResult with the same changes (in the same order) but
    possibly different severities. The list of refinements made is recorded
    in result.metadata['severity_refinements'].

    The original DiffResult is not mutated.
    """
```

```python
# src/owlcompare/severity_config.py

from dataclasses import dataclass, field
from pathlib import Path
from .diff._common import Severity


@dataclass(frozen=True, slots=True)
class SeverityOverride:
    """A user-supplied rule to force a specific severity for matching changes."""
    kind_pattern: str          # e.g., 'annotation_changed' or 'annotation_*' (glob)
    layer: str | None = None   # optional filter: 'syntactic' or 'structural'
    subject_pattern: str | None = None  # optional glob on subject IRI
    severity: Severity = "info"


@dataclass(frozen=True, slots=True)
class SeverityConfig:
    """Top-level severity config loaded from TOML."""
    overrides: tuple[SeverityOverride, ...] = ()
    schema_version: int = 1


def load(path: Path) -> SeverityConfig:
    """Load a TOML severity config. Raises SeverityConfigError on malformed input."""


def empty() -> SeverityConfig:
    """Return an empty config (no overrides). The default."""
```

## Built-in cross-cutting rules

The classifier runs these in order. Each rule is a pure function `(Change, DiffResult, Registry) → SeverityRefinement | None`. The first rule that returns a non-None refinement wins; subsequent rules don't run for that change.

Order matters: user overrides come first (they win over built-in rules), then built-in rules.

### Rule 1 — User overrides

If the change matches any `SeverityOverride` from the config, apply that severity. Rule_id = `user-override`. Rationale = the override's kind_pattern.

### Rule 2 — Annotation on deprecated entity

If the change is an `annotation_changed`, `annotation_added`, or `annotation_removed`, AND the same entity has an `entity_deprecated` change in the same diff, demote severity to `info` regardless of original. Rule_id = `annotation-on-deprecated`. Rationale: "editorial change on entity being deprecated; reduced significance."

### Rule 3 — Restriction consequential to property removal

If the change is a `restriction_removed`, AND the restriction's `on_property` is the subject of a `*_property_removed` change in the same diff, downgrade severity from `non_breaking` to `info`. Rule_id = `restriction-consequential-property-removed`. Rationale: "restriction removal is consequence of property removal."

(The restriction removal isn't *additionally* breaking — the property removal already is. So the restriction's `non_breaking` becomes informational.)

### Rule 4 — Domain/range narrowing detection upgrade

If the change is a `domain_changed` or `range_changed` that defaulted to `breaking` because Component 08 couldn't determine narrowing/widening, AND Component 07's hierarchy index (now visible alongside all other changes) clearly shows the new domain/range is an ancestor of the old, downgrade to `non_breaking`. Rule_id = `dr-widening-detected-late`. Rationale: "domain/range widened (asserted-hierarchy check after all Layer 1 changes applied)."

Note: this is the *only* rule that re-examines a defaulted-to-breaking case. The hierarchy may have changed during the diff (Component 07 added a new edge), and that new edge can affect the comparison.

### Rule 5 — Hierarchy reparent + restriction added on same entity

If the change is a `class_reparented` (severity may be `breaking` for lateral/specialization), AND there's a `restriction_added` for the same entity in the same diff, upgrade `class_reparented` severity from `non_breaking` to `breaking`. Rule_id = `reparent-with-new-restriction`. Rationale: "class moved with new constraints; combined breaking change."

(This is the inverse of Rule 3 — sometimes context *upgrades* severity.)

### Rule 6 — Subsumed Layer 0 changes get severity `info`

Any Layer 0 change that's already subsumed (per `result.metadata["subsumption_registry"]`) gets severity `info`. This is mostly cosmetic — subsumed Layer 0 changes don't appear in default text output anyway, but a JSON consumer sorting by severity will see them as low-priority noise rather than mixed with truly informational events. Rule_id = `subsumed-layer0-info`. Rationale: "Layer 0 change subsumed by a Layer 1 change."

The complete list is short on purpose. The point isn't to have many rules — it's to encode the *cross-cutting* judgments that single-slice classification can't make.

## CLI integration

Add a flag to the `diff` subcommand:

```
owlcompare diff [OPTIONS] ONTOLOGY_A ONTOLOGY_B

  --severity-config PATH        Path to a TOML severity config file (optional)
  --no-severity-refinement      Skip cross-cutting refinement (debug/verification)
  --explain-severity            For each refined change, print the rule that decided.
                                (Default: refinements are recorded silently in JSON output)
```

When `--severity-config` is provided, load it. Validate. On error, raise `SeverityConfigError` with exit code 6 (a new code for "config invalid"). Add to the exit code table.

When `--no-severity-refinement` is set, skip Component 10 entirely (orchestrator returns its raw DiffResult). Useful for debugging which rule changed what.

When `--explain-severity` is set, after rendering the normal diff output, append an "Explanations" panel listing every refinement with its rule_id and rationale.

JSON output **always** includes `severity_refinements` in the top-level metadata block (an array of `SeverityRefinement` dicts). This is part of the v1 JSON schema.

## Severity config file format

Format: TOML, deliberately simple, easy to commit alongside the ontology repo.

Example `.owlcompare-severity.toml`:

```toml
schema_version = 1

# Force all annotation changes to info
[[overrides]]
kind_pattern = "annotation_*"
severity = "info"

# Treat label changes on deprecated entities as fully ignorable in our project
[[overrides]]
kind_pattern = "annotation_*"
subject_pattern = "*deprecated*"   # this is just illustrative
severity = "info"

# Our project considers class reparenting (any kind) to be breaking, no nuance
[[overrides]]
kind_pattern = "class_reparented"
severity = "breaking"

# A specific entity is being deprecated gradually; ignore its restriction changes
[[overrides]]
kind_pattern = "restriction_*"
subject_pattern = "http://data.europa.eu/949/LegacyTrack"
severity = "info"
```

Pattern matching:
- `kind_pattern` and `subject_pattern` use shell-glob style: `*` matches any chars, `?` matches one char.
- `layer` is exact-match (literal value `"syntactic"` or `"structural"`).
- All conditions in an override must match for it to apply.

The schema is versioned (`schema_version = 1`). Loaders reject unknown versions with `SeverityConfigError`.

## Internal design

### `refine()` algorithm

```python
def refine(result, config=None, options=None):
    config = config or empty()
    refinements: list[SeverityRefinement] = []
    new_changes: list[Change] = []

    for change in result.changes:
        original = change.severity
        refined = original
        rule_id = None
        rationale = None

        # Try user overrides first
        for override in config.overrides:
            if matches(change, override):
                refined = override.severity
                rule_id = "user-override"
                rationale = f"matched pattern '{override.kind_pattern}'"
                break

        # Then built-in rules
        if rule_id is None:
            for rule in BUILTIN_RULES:
                ref = rule(change, result)
                if ref is not None:
                    refined = ref.refined_severity
                    rule_id = ref.rule_id
                    rationale = ref.rationale
                    break

        if refined != original:
            refinements.append(SeverityRefinement(
                change_id=change.details["change_id"],
                original_severity=original,
                refined_severity=refined,
                rule_id=rule_id,
                rationale=rationale,
            ))
            change = replace(change, severity=refined)

        new_changes.append(change)

    new_metadata = dict(result.metadata)
    new_metadata["severity_refinements"] = tuple(refinements)
    return replace(result, changes=tuple(new_changes), metadata=new_metadata)
```

### Pattern matching with globs

Use `fnmatch.fnmatch` from stdlib. No regex (regex in user config is a footgun). Glob is sufficient and well-understood.

### Exit code unchanged

The exit code policy from Component 05 stays: if any change has severity `breaking` after refinement, exit code 10. If only `non_breaking`, `additive`, or `info`, exit code 0.

This means user overrides *can* affect exit codes. A user choosing to downgrade everything to `info` would always get exit 0 — that's correct; they've explicitly said "nothing here breaks us." Document this clearly in the help text and the docs.

### Audit trail in metadata

Renderers can inspect `result.metadata["severity_refinements"]` to show "this severity was changed from X to Y by rule Z." The HTML report (Component 17) is the most likely consumer.

## Edge cases & failure modes

- **Config file missing on disk:** raise `SeverityConfigError` with exit code 2 (usage error — path is wrong).
- **Config file malformed (TOML parse error):** raise `SeverityConfigError` with exit code 6.
- **Config has unknown schema_version:** raise `SeverityConfigError` mentioning what we support.
- **Config has unknown severity value** (e.g., `severity = "blocking"`): raise `SeverityConfigError` listing valid values.
- **No config supplied:** built-in rules apply only. Default behavior.
- **`--no-severity-refinement` set:** skip the whole component. `result` unchanged. Metadata adds `severity_refinements = []`.
- **An override matches multiple changes:** apply to all of them. That's the point.
- **An override has no `kind_pattern`:** raise on load. Pattern is required.
- **An override's pattern matches no changes:** silently ignored. No warning. Users iterate.
- **Built-in rules conflict** (rare; carefully ordered to prevent this): the first to match wins. Tests assert ordering.
- **A change without a `change_id` in details** (would be a bug in earlier components): treat as if change_id is the empty string. Refinement still applies. Log at DEBUG.
- **User config tries to upgrade severity to `breaking`** for a kind that the project's defaults treat as `info`: allow it. User knows their project.
- **Rule 6 fires whenever subsumption happens** — i.e. on almost every real-world diff, since every Layer 1 change subsumes the Layer 0 triples it explains. Refinement lists are therefore routinely long, but the overwhelming majority of entries are `subsumed-layer0-info` (a cosmetic normalization of already-hidden noise). This is by design: Rule 6 is universal, not a "cross-cutting special case." Tests that want to assert "nothing meaningful changed" must assert *which* rules fired (only `subsumed-layer0-info`) and that no structural / unsubsumed-Layer-0 change was touched — not that the refinement list is empty.

## Dependencies to add

None. `tomllib` is stdlib (3.11+). `fnmatch` is stdlib.

## Acceptance tests

Located in `tests/unit/test_severity.py`, `tests/unit/test_severity_config.py`, extensions to `tests/unit/test_cli_diff.py`, and extensions to `tests/integration/test_diff_integration.py`.

### Fixtures to add (`tests/fixtures/severity/`)

- `valid_config.toml` — a TOML config exercising all override kinds.
- `unknown_version.toml` — `schema_version = 99`.
- `malformed.toml` — broken TOML syntax.
- `unknown_severity.toml` — `severity = "blocking"`.
- `missing_kind.toml` — override without `kind_pattern`.

For the cross-cutting rule tests, reuse existing diff fixtures and add a few focused pairs:
- `tests/fixtures/severity/annotation_on_deprecated_v1.ttl` / `_v2.ttl` exercises Rule 2 (the `entity_deprecated` case combined with `annotation_changed` on the *same* entity — `era_annotations` deprecates `era:Signal` but edits labels on `era:Track`, so it does not combine them on one entity).
- `tests/fixtures/diff/era_evolution_v1.ttl` / `_v2.ttl` exercises *only* Rule 6 (subsumed Layer 0 changes) — a useful regression test that no other cross-cutting rule misfires on a realistic diff.
- Create `tests/fixtures/severity/reparent_with_restriction_v1.ttl` / `_v2.ttl` for Rule 5.
- Create `tests/fixtures/severity/restriction_after_property_removed_v1.ttl` / `_v2.ttl` for Rule 3.
- Create `tests/fixtures/severity/domain_widening_late_v1.ttl` / `_v2.ttl` for Rule 4 (a domain swap whose widening is only decidable once v2's new `subClassOf` edge is in view).

### Test list

**`tests/unit/test_severity_config.py`:**
- [x] `test_load_valid_config_returns_parsed_overrides`
- [x] `test_load_missing_file_raises_severity_config_error_exit_code_2`
- [x] `test_load_malformed_toml_raises_severity_config_error_exit_code_6`
- [x] `test_load_unknown_schema_version_raises`
- [x] `test_load_unknown_severity_value_raises`
- [x] `test_load_missing_kind_pattern_raises`
- [x] `test_empty_config_has_no_overrides`
- [x] `test_override_pattern_matching_glob_kind_only`
- [x] `test_override_pattern_matching_glob_subject_too`
- [x] `test_override_pattern_matching_layer_filter`
- [x] `test_override_pattern_no_match_returns_false`

**`tests/unit/test_severity.py`:**
- [x] `test_refine_no_config_no_changes_returns_same_severities`
- [x] `test_refine_does_not_mutate_input`
- [x] `test_refine_records_refinement_in_metadata`
- [x] `test_refine_no_refinements_metadata_has_empty_tuple`
- [x] `test_rule_user_override_wins_over_builtin`
- [x] `test_rule_user_override_applied_to_matching_kind`
- [x] `test_rule_user_override_with_subject_pattern_applied`
- [x] `test_rule_user_override_does_not_apply_when_kind_doesnt_match`
- [x] `test_rule_annotation_on_deprecated_demotes_to_info`
- [x] `test_rule_annotation_on_deprecated_only_applies_if_entity_deprecated_in_same_diff`
- [x] `test_rule_restriction_consequential_to_property_removed_demoted_to_info`
- [x] `test_rule_reparent_with_restriction_added_upgraded_to_breaking`
- [x] `test_rule_subsumed_layer0_changes_severity_info`
- [x] `test_rule_domain_widening_late_detection_demotes_to_non_breaking` — Rule 4, the hardest.
- [x] `test_rule_order_user_override_then_builtin`
- [x] `test_rule_first_match_wins_no_double_refinement`
- [x] `test_explain_severity_refinement_carries_rule_id_and_rationale`
- [x] `test_refined_diffresult_changes_tuple_not_list_preserves_order`
- [x] `test_breaking_remains_breaking_when_no_rule_applies`
- [x] `test_exit_code_reflects_refined_severities_not_originals` — user override demotes the only breaking change to info → exit code 0.

**`tests/unit/test_cli_diff.py` (extensions):**
- [x] `test_cli_diff_severity_config_flag_loads_config`
- [x] `test_cli_diff_severity_config_missing_file_exits_2`
- [x] `test_cli_diff_severity_config_malformed_exits_6`
- [x] `test_cli_diff_no_severity_refinement_flag_skips_classifier`
- [x] `test_cli_diff_explain_severity_flag_prints_refinement_panel`
- [x] `test_cli_diff_json_includes_severity_refinements_in_metadata`
- [x] `test_cli_diff_exit_code_respects_user_override` — config demotes the breaking change → exit 0.

**`tests/integration/test_diff_integration.py` (extensions):**
- [x] `test_era_evolution_severity_refinement_only_affects_subsumed_layer0` — Rule 6 is universal and *does* fire on era_evolution's subsumed Layer 0 triples (the original "refinements should be empty" framing was wrong — it overlooked that Rule 6 always runs when subsumption happens). The tightened invariant: every refinement is `subsumed-layer0-info`, no structural change was refined, no *unsubsumed* Layer 0 change was refined, and the exit code is unchanged (still 10 — `era:locatedOn`'s `object_property_removed` stays breaking).
- [x] `test_era_annotations_label_change_on_deprecated_entity_demoted` — Rule 2: a dedicated fixture deprecates `era:Track` while changing its French label. Because Component 09 already emits annotation changes as `info`, the demotion is a recorded *no-op* in the standard pipeline (Q3), so the test asserts the end-state (`info`) and verifies Rule 2 is the controlling rule by re-running it on a forced non-info copy.
- [x] `test_reparent_with_new_restriction_fixture_upgrades_severity` — Rule 5 in action.

## Out of scope (deliberately)

- Per-namespace rules (e.g., "all changes in the `era:` namespace are critical"). Future Phase 5 polish.
- "Suggest a rule" output ("you've consistently downgraded X; want to add it to the config?"). Useful but premature.
- A built-in rule library users can opt into selectively. The six rules above are universal enough to apply always; opt-in would mean defending which subset.
- Programmatic API for adding rules from user code. Sufficient for v1 to expose `refine(...)` and let users post-process if they really need to.
- Severity inheritance (parent class breaking → children also breaking). Adjacent topic; out of scope.
- Project-wide severity profiles (e.g., "OBO Foundry style," "FIBO style"). Could be implemented as named TOML configs in v2.

## Open questions

- [x] **Q1 (resolved — adopted proposed):** Should the `subject_pattern` in user overrides match against the full IRI or the prefixed form?
  **Decision:** Full IRI only. Prefixed-form matching is ambiguous (what if the user's `era:` doesn't match what we resolved?). Implemented in `severity_config.matches` (matches `change.subject`, the full IRI; a `subject_pattern` on a subjectless change never matches).

- [x] **Q2 (resolved — adopted proposed):** Should Rule 6 (subsumed Layer 0 → info) be a built-in rule (always applied) or a default the user can disable?
  **Decision:** Built-in, always applied. Subsumed Layer 0 changes are by definition not the primary expression of what changed; downgrading their severity is a correctness improvement, not a policy choice. `--no-severity-refinement` disables the whole component for debugging. (Consequence: Rule 6 fires on virtually every real diff — see Edge cases.)

- [x] **Q3 (resolved — adopted proposed):** When an override (or built-in rule) matches a change but its target severity equals the original, should we record a no-op refinement or skip?
  **Decision:** Skip recording — `refine()` only appends to the audit trail when `refined != original`. A matching *override* still wins over the built-ins (it is consulted first and short-circuits them) even when its result is a no-op; it simply is not written to the trail. This applies uniformly to built-in rules too, which is why Rule 2's demotion of an already-`info` annotation change is a recorded no-op in the standard pipeline.

All three open questions were resolved by adopting the proposed answers during implementation.

## References

- `docs/ARCHITECTURE.md` § Diff Engine (Severity)
- `docs/DESIGN_DECISIONS.md` § DD-008 (severity)
- `docs/GLOSSARY.md` § Severity
- Components 05–09 specs for the severity defaults this refines.
