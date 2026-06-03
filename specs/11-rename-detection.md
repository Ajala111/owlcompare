# Component 11: Rename Detection

## Identity

- **Component number:** 11
- **Name:** Rename detection (Phase 3, first component)
- **Module paths:**
  - `src/owlcompare/diff/rename.py` — the detector and the cascade consolidator
  - `src/owlcompare/diff/_rename_evidence.py` — fingerprinting helpers (label index, structural fingerprint)
  - `src/owlcompare/rename_mapping.py` — user-supplied mapping file loader (TOML)
- **Roadmap phase:** Phase 3 (first component)
- **Depends on components:** 02 (model), 05–09 (the slices that emit `*_added`/`*_removed` Change records), the orchestrator, 10 (severity classifier — renames run before refinement)
- **Depended on by (planned):** 14–17 (renderers — they show renames specially), 19 (GitHub Action)

## Purpose

Detect entity renames in a diff (a `class_removed` paired with a `class_added` representing the same logical entity under a new IRI) and consolidate the pair plus all cascade consequences into a single `class_renamed` Change. Support three confidence tiers — `certain` (user-supplied), `high` (label-matched), `medium` (structural fingerprint match) — and let users opt into lower tiers via flag.

After this component, a rename like `era:Track → era:RailwayTrack` produces a single line of diff output rather than the dozen `remove + add` pairs the rename actually generated at the triple level.

What would break if we removed it: every ontology refactoring that involves renaming would appear as a catastrophic set of unrelated removals and additions, misrepresenting safe refactors as breaking changes.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Diff result | `DiffResult` | Orchestrator output (post-Layer-1, **pre-severity**) | Must contain `*_added`/`*_removed` changes |
| Mapping | `RenameMapping` | Optional, from user config file | Hard constraints to honor before heuristics |
| Confidence threshold | `RenameConfidence` (enum) | CLI flag or programmatic | Minimum tier to accept |
| Options | `DiffOptions` | Optional | Future knobs |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `DiffResult` (new) | dataclass | Severity classifier (next), then renderers | Renames replace paired add/remove changes; cascade consequences subsumed |

## Public API

```python
# src/owlcompare/diff/rename.py

from dataclasses import dataclass, field
from typing import Literal
from .._common import Change, DiffResult, DiffOptions
from ..rename_mapping import RenameMapping


RenameConfidence = Literal["certain", "high", "medium", "low"]


@dataclass(frozen=True, slots=True)
class RenameCandidate:
    """An inferred or asserted rename pairing."""
    removed_iri: str            # IRI in A
    added_iri: str              # IRI in B
    entity_kind: str            # 'class', 'object_property', 'data_property', 'annotation_property'
    confidence: RenameConfidence
    evidence: tuple[str, ...]   # human-readable rationale lines, e.g.
                                #   ("matching label 'Track'@en", "shared parent era:Asset", "3 incoming refs renamed")
    score: float                # 0.0–1.0, normalized fingerprint match score


def detect(
    result: DiffResult,
    mapping: RenameMapping | None = None,
    min_confidence: RenameConfidence = "high",
    options: DiffOptions | None = None,
) -> DiffResult:
    """Detect renames in a DiffResult and consolidate them with their cascades.

    Returns a new DiffResult where each accepted rename:
      - Removes the corresponding *_removed and *_added Change records
      - Adds a single *_renamed Change record
      - Subsumes cascade consequences (restriction changes, hierarchy changes,
        domain/range changes that referenced the renamed entity) where those
        consequences are now explained by the rename itself

    Args:
        result: A DiffResult with *_added and *_removed changes to pair.
        mapping: A user-supplied mapping (highest priority, certain confidence).
        min_confidence: Minimum confidence to accept. 'high' by default.
            Lower thresholds find more pairings but risk false positives.

    Returns:
        A new DiffResult with renames consolidated. Metadata includes
        'rename_candidates': all considered candidates (accepted + rejected),
        and 'renames_applied': only the accepted ones.

    The original DiffResult is not mutated.
    """
```

```python
# src/owlcompare/rename_mapping.py

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RenameMapping:
    """User-supplied IRI rename map."""
    classes: tuple[tuple[str, str], ...] = ()          # (old_iri, new_iri)
    object_properties: tuple[tuple[str, str], ...] = ()
    data_properties: tuple[tuple[str, str], ...] = ()
    annotation_properties: tuple[tuple[str, str], ...] = ()
    schema_version: int = 1


def load(path: Path) -> RenameMapping:
    """Load a TOML rename mapping file. Raises RenameMappingError on malformed input."""


def empty() -> RenameMapping:
    """Return an empty mapping (no user-supplied renames). The default."""
```

```python
# Add to src/owlcompare/exceptions.py
class RenameMappingError(OwlCompareError):
    """Malformed rename mapping config."""
    exit_code: int = 6  # shares the config-error exit code with severity config
```

## CLI integration

Add two flags to the `diff` subcommand:

```
owlcompare diff [OPTIONS] ONTOLOGY_A ONTOLOGY_B

  --rename-mapping PATH         Path to a TOML rename mapping file (optional)
  --rename-confidence LEVEL     One of: certain | high | medium | none.
                                'certain' means user-supplied renames only;
                                'high' uses label matching (default);
                                'medium' adds structural fingerprint matching;
                                'none' disables rename detection entirely.
```

Behavior:

- Default is `--rename-confidence high`. Most common case: detect label-matched renames silently.
- `--rename-confidence none` skips Component 11 entirely. Useful for debugging.
- `--rename-confidence medium` accepts structural-fingerprint matches in addition to label matches. Riskier but catches renames that also changed the label.
- `--rename-confidence certain` rejects all inferred pairings; only the user mapping applies.

The order of operations in the orchestrator is:

1. Canonicalize
2. Layer 0 (syntactic)
3. Layer 1: entities → hierarchy → restrictions → annotations
4. **Rename detection (Component 11)** — runs on the Layer 1 result, consolidates
5. Severity classification (Component 10) — runs *after* renames so refinements see the consolidated result

This order matters: severity rules see fewer total changes (no duplicate breaking removed + additive added) and can produce more accurate cross-cutting refinements.

## Rename mapping file format

TOML, deliberately simple:

```toml
schema_version = 1

[[classes]]
old = "http://data.europa.eu/949/Track"
new = "http://data.europa.eu/949/RailwayTrack"

[[classes]]
old = "http://data.europa.eu/949/Signal"
new = "http://data.europa.eu/949/RailwaySignal"

[[object_properties]]
old = "http://data.europa.eu/949/locatedOn"
new = "http://data.europa.eu/949/hasLocation"
```

Each section ([[classes]], [[object_properties]], etc.) is an array-of-tables. Each entry has `old` and `new` fields with full IRI strings.

Constraints:
- The `old` IRI must appear as the subject of a `*_removed` change in the diff.
- The `new` IRI must appear as the subject of a `*_added` change in the diff.
- If either constraint is violated, the entry is silently ignored and logged at INFO. (Rationale: a stale mapping shouldn't block the diff; the user iterates.)

Schema version 1 only for v1.

## Internal design

### Step 1 — Index the candidate space

Build two index structures from the input `DiffResult`:

```python
@dataclass(frozen=True, slots=True)
class CandidateIndex:
    """Inverted index over the diff's *_added/*_removed changes."""
    removed_by_kind: dict[str, list[Change]]   # kind -> list of *_removed changes
    added_by_kind: dict[str, list[Change]]     # kind -> list of *_added changes
```

For each entity kind (`class`, `object_property`, `data_property`, `annotation_property`), gather the `*_removed` and `*_added` changes into separate buckets. We only consider pairings within the same kind — a class can't be renamed to a property.

### Step 2 — Build fingerprints

For each removed-side and added-side candidate, build a fingerprint structure:

```python
@dataclass(frozen=True, slots=True)
class EntityFingerprint:
    """Structural fingerprint of an entity for rename matching."""
    iri: str
    kind: str
    labels: tuple[tuple[str, str], ...]    # ((lang, text), ...) sorted
    parents: tuple[str, ...]               # direct rdfs:subClassOf parents (canonical, sorted)
    children: tuple[str, ...]              # direct subclass children (computed from index)
    incoming_predicates: tuple[str, ...]   # predicates of triples where this entity is object
    outgoing_predicates: tuple[str, ...]   # predicates of triples where this entity is subject
    attached_restrictions: tuple[str, ...] # restriction URNs attached via subClassOf
```

Built by querying the appropriate snapshot (the removed-side from A's canonical graph, added-side from B's). Skip the entity's own IRI in incoming/outgoing — we want the *shape* not the identity.

### Step 3 — Apply user mapping first (highest priority)

For each entry in `mapping.classes` (and the other kinds):
1. Find the matching `class_removed` for the `old` IRI and `class_added` for the `new` IRI.
2. If both exist: build a `RenameCandidate` with `confidence="certain"`, evidence = `("user-supplied mapping",)`, `score=1.0`. Mark accepted.
3. If either is missing: log INFO and skip.

Tracked candidates are removed from the candidate index — they don't enter heuristic matching.

### Step 4 — Apply label-matching heuristic (high confidence)

For each remaining removed-side candidate:

1. Get its labels: `{(lang, text) | label triple exists in A for this entity}`.
2. For each remaining added-side candidate of the same kind:
3.   Compute label overlap: shared `(lang, text)` pairs.
4.   If at least one label matches AND no other added-side candidate matches the same set of labels: emit `RenameCandidate(confidence="high", score=1.0)` with evidence = label overlap description.

If multiple added-side candidates share the same label set with the removed-side candidate, this is ambiguous — skip and let structural fingerprint matching decide (next step). Don't emit at `high` confidence.

The asymmetry matters: a high-confidence rename must be *unique*. If both `era:Track1` and `era:Track2` are added with the label "Track", we don't pair either with `era:Track` removed — it's not safe.

### Step 5 — Apply structural fingerprint matching (medium confidence)

Only runs when `min_confidence` is `medium` or lower.

For each still-unpaired removed-side candidate:

1. For each still-unpaired added-side candidate of the same kind, compute a similarity score:
   - Label overlap: `+0.3` per shared `(lang, text)`, max `+0.5`
   - Shared parent IRIs (post-canonicalization): `+0.2` per match, max `+0.4`
   - Shared incoming predicates: `+0.1` per match, max `+0.3`
   - Shared outgoing predicates: `+0.05` per match, max `+0.2`
2. If the best match has score ≥ 0.6 AND is at least 0.2 higher than the second-best match: emit `RenameCandidate(confidence="medium", score=match_score)` with evidence listing what matched.
3. Otherwise: no rename, leave the changes alone.

The "0.2 higher than second-best" requirement prevents accidental pairing when multiple added entities are similarly plausible matches. It's a separation criterion.

### Step 6 — Cascade consolidation

For each accepted `RenameCandidate(removed_iri, added_iri, kind)`:

1. Remove the matching `class_removed`/`*_property_removed` Change from the result.
2. Remove the matching `class_added`/`*_property_added` Change from the result.
3. Add a single `class_renamed`/`*_property_renamed` Change with `subject = added_iri` (the new IRI), `details = {before: removed_iri, after: added_iri, confidence, evidence, ...}`.
4. **Cascade:** scan the remaining changes for ones that referenced the renamed entity in their `subject`, `details.parent_iri`, `details.entity_iri`, `details.other_iri`, `details.before.filler`, `details.after.filler`, etc. For each such reference:
   - If the *only* difference between an `*_added` and `*_removed` pair is the renamed IRI (i.e., the structure is otherwise identical), consolidate the pair as subsumed under the rename.
   - If the change describes something genuinely new (e.g., a restriction added on the renamed entity that didn't exist before), leave it alone.

Cascade consolidation requires careful pairing. Implementation:
- Walk the remaining `*_added`/`*_removed` pairs.
- For each pair, compute a "structural fingerprint with IRI substituted" — what would each change look like if we replaced the renamed entity's old IRI with the new one (or vice versa) and then compared?
- If after substitution the changes match, treat the pair as a cascade consequence and subsume.

A cleaner phrasing: a cascade consequence is a removed change for which there is a corresponding added change that *only* differs by the substitution. Anything else stays as an independent change.

### Severity for renamed changes

| Kind | Severity |
|------|----------|
| `class_renamed` | `info` (rename without semantic change — by definition) |
| `object_property_renamed`, `data_property_renamed`, `annotation_property_renamed` | `info` |

If a rename is detected *and* the structural shape changed (e.g., the entity also gained a new parent or restriction), the rename's severity stays `info` but the *new* structural changes appear as independent Layer 1 changes with their own severities. The rename only captures the IRI substitution, not the structural delta.

### Subject and summary

`Change.subject` = the new IRI (post-rename).

`Change.summary` patterns:

- `"Class renamed: era:Track → era:RailwayTrack (certain)"` — user-supplied
- `"Class renamed: era:Track → era:RailwayTrack (high confidence; matching label \"Track\"@en)"` — heuristic
- `"Class renamed: era:Track → era:RailwayTrack (medium confidence; 3 shared parents, 5 shared incoming references)"` — fingerprint
- `"Object property renamed: era:locatedOn → era:hasLocation (high)"` 

The confidence is part of the visible summary because it tells the user how much to trust the inference.

### Details dictionary

```python
details = {
    "change_id": "rename:class_renamed:...",
    "before_iri": "http://...Track",
    "after_iri": "http://...RailwayTrack",
    "entity_kind": "class",
    "confidence": "high",
    "score": 1.0,
    "evidence": ["matching label 'Track'@en", "shared parent era:Asset"],
    "cascade_subsumes": [<change_ids of consolidated cascade pairs>],
    "subsumes": [<change_ids of the original *_removed and *_added pair>],
}
```

### Ordering

Renamed changes appear in the structural section sorted by `before_iri`. They typically sort to the top alphabetically by chance, but the *visual* prominence comes from being few in number after consolidation.

## Edge cases & failure modes

- **No changes to pair:** return result unchanged, empty `renames_applied`.
- **User mapping references non-existent IRIs:** log INFO per entry, skip silently.
- **User mapping cycle** (`A → B` AND `B → A`): nonsensical; log WARNING, skip both.
- **One removed candidate, multiple added candidates with the same label:** ambiguous, no high-confidence rename emitted. Falls through to fingerprint matching if enabled.
- **Renames that *also* change semantics** (rename + new parent + new restriction): the rename is detected but the new structural changes remain as independent changes. Tested.
- **Renaming a class to an existing class IRI:** impossible to detect cleanly — the `added` change doesn't exist (the IRI was already there). We can't handle this; document as known limitation.
- **Renaming + entity kind change:** out of scope. Component 06 already emits `entity_kind_changed` for an IRI moving between kinds. We don't pair across kinds.
- **Cascade subsumption with cycles** (A renamed to B, B's references include something that was also renamed): cascade handles each rename independently; consequences are subsumed in order of acceptance. No special cycle handling needed.
- **Synthetic IRIs (`urn:owlcompare:restriction:*`):** never rename candidates. Skip.
- **Performance:** O(N×M) per kind where N is removed count, M is added count. For large diffs (thousands of removals/additions per kind), this could be slow. v1 acceptable; v2 might use prefix-based indexing.

## Dependencies to add

None. `tomllib` is stdlib (3.11+), `fnmatch` already in use.

## Acceptance tests

Located in `tests/unit/test_rename.py`, `tests/unit/test_rename_mapping.py`, `tests/unit/test_rename_fingerprint.py`, extensions to `tests/unit/test_cli_diff.py`, and extensions to `tests/integration/test_diff_integration.py`.

### Fixtures to add (`tests/fixtures/rename/`)

- `simple_class_rename_v1.ttl` / `_v2.ttl` — one class renamed, label preserved, simple structure (the label-match case).
- `class_rename_with_new_restriction_v1.ttl` / `_v2.ttl` — class renamed AND a restriction added. Rename detected; restriction change remains independent.
- `ambiguous_label_match_v1.ttl` / `_v2.ttl` — one removed class with label "Asset" and TWO added classes both with label "Asset". Ambiguous; high-confidence rename should not fire.
- `fingerprint_rename_v1.ttl` / `_v2.ttl` — class renamed; label *also* changed (so label matching can't see it); but structural fingerprint matches (same parents, same restrictions). Medium-confidence case.
- `property_rename_v1.ttl` / `_v2.ttl` — object property renamed.
- `cascade_simple_v1.ttl` / `_v2.ttl` — class renamed; another class has a `subClassOf` referencing the renamed class. After cascade, both changes consolidate.
- `no_rename_just_replacement_v1.ttl` / `_v2.ttl` — one class removed and one added with no label or structural overlap. Should NOT be detected as a rename.
- `class_rename_with_label_change_v1.ttl` / `_v2.ttl` — class renamed *and* its label changed in the same diff. Without fingerprint matching, no rename detected. With fingerprint matching, detected.
- `valid_mapping.toml` — a TOML mapping for use in CLI tests.
- `mapping_with_stale_iri.toml` — references an IRI not in the diff.
- `mapping_malformed.toml` — broken TOML.
- `mapping_unknown_version.toml` — `schema_version = 99`.
- `era_renames_v1.ttl` / `era_renames_v2.ttl` — flagship: realistic ERA rename scenario where 2 classes and 1 property are renamed, with cascade consequences on restrictions and hierarchy.

### Test list

**`tests/unit/test_rename_mapping.py`:**
- [ ] `test_load_valid_mapping_returns_parsed_entries`
- [ ] `test_load_missing_file_raises_rename_mapping_error_exit_code_2`
- [ ] `test_load_malformed_toml_raises_exit_code_6`
- [ ] `test_load_unknown_schema_version_raises`
- [ ] `test_empty_mapping_has_no_entries`
- [ ] `test_load_handles_multiple_classes`
- [ ] `test_load_handles_multiple_kinds`

**`tests/unit/test_rename_fingerprint.py`:**
- [ ] `test_build_fingerprint_captures_labels`
- [ ] `test_build_fingerprint_captures_parents`
- [ ] `test_build_fingerprint_captures_incoming_predicates`
- [ ] `test_build_fingerprint_captures_outgoing_predicates`
- [ ] `test_build_fingerprint_elides_entity_own_iri`
- [ ] `test_build_fingerprint_captures_attached_restrictions`
- [ ] `test_fingerprint_score_perfect_match_is_1`
- [ ] `test_fingerprint_score_no_overlap_is_0`
- [ ] `test_fingerprint_score_partial_label_match_below_threshold`

**`tests/unit/test_rename.py`:**
- [ ] `test_detect_no_changes_returns_unchanged`
- [ ] `test_detect_does_not_mutate_input`
- [ ] `test_detect_user_mapping_certain_confidence`
- [ ] `test_detect_user_mapping_stale_iri_logged_silently`
- [ ] `test_detect_label_match_high_confidence`
- [ ] `test_detect_label_match_ambiguous_no_rename_emitted`
- [ ] `test_detect_fingerprint_match_medium_confidence`
- [ ] `test_detect_fingerprint_match_score_threshold_not_met_no_rename`
- [ ] `test_detect_fingerprint_match_separation_threshold_enforced`
- [ ] `test_detect_min_confidence_certain_rejects_label_matches`
- [ ] `test_detect_min_confidence_high_default_accepts_user_and_label`
- [ ] `test_detect_min_confidence_medium_accepts_fingerprint`
- [ ] `test_detect_min_confidence_none_skips_detection`
- [ ] `test_rename_emits_class_renamed_change`
- [ ] `test_rename_emits_property_renamed_change`
- [ ] `test_rename_subsumes_original_added_and_removed_changes`
- [ ] `test_rename_severity_is_info`
- [ ] `test_rename_summary_includes_confidence`
- [ ] `test_rename_details_includes_before_iri_after_iri_evidence`
- [ ] `test_cascade_consolidates_referencing_subclass_pair`
- [ ] `test_cascade_consolidates_referencing_domain_range_pair`
- [ ] `test_cascade_preserves_independent_changes` — a restriction added that's genuinely new stays as a change.
- [ ] `test_rename_does_not_pair_across_kinds`
- [ ] `test_rename_skips_restriction_urn_subjects`
- [ ] `test_user_mapping_overrides_heuristic_pairing` — user maps A→C; heuristic would have paired A→B. User wins.
- [ ] `test_rename_metadata_includes_candidates_and_applied`

**`tests/unit/test_cli_diff.py` (extensions):**
- [ ] `test_cli_diff_rename_mapping_flag_loads_mapping`
- [ ] `test_cli_diff_rename_mapping_missing_file_exits_2`
- [ ] `test_cli_diff_rename_mapping_malformed_exits_6`
- [ ] `test_cli_diff_rename_confidence_none_disables_detection`
- [ ] `test_cli_diff_rename_confidence_certain_requires_mapping`
- [ ] `test_cli_diff_rename_confidence_medium_enables_fingerprint`
- [ ] `test_cli_diff_text_output_shows_renames_specially`
- [ ] `test_cli_diff_json_includes_rename_evidence_and_confidence`

**`tests/integration/test_diff_integration.py` (extensions):**
- [ ] `test_simple_rename_fixture_produces_one_renamed_change` — fixture with one renamed class produces exactly 1 `class_renamed`, 0 `class_removed`, 0 `class_added`.
- [ ] `test_cascade_fixture_consolidates_referencing_changes`
- [ ] `test_era_renames_fixture_produces_expected_counts` — flagship: 2 class renames + 1 property rename + 0 unexplained Layer 0.
- [ ] `test_era_evolution_fixture_unchanged_after_rename_detection` — regression: era_evolution has no renames, output identical to pre-Component-11.
- [ ] `test_severity_classifier_runs_after_renames` — confirm pipeline order: renames consolidate first, then severity refines the consolidated result.

## Known limitations

- **Structural additions on the renamed entity itself are absorbed by the rename.**
  When a class (or property) is renamed *and* simultaneously gains new structural
  axioms in v2 — a new restriction, a new parent edge, a new domain/range, a new
  annotation — those additions are first deferred by Components 08/09 into the
  entity's `*_added` change (a wholly-added entity's axioms ride along with it),
  and then absorbed when Component 11 consolidates the `*_added` + `*_removed`
  pair into a single `*_renamed` change. The net effect is that the rename hides
  the additions from the diff narrative: a user who renamed `era:Track` to
  `era:RailwayTrack` *and* added a new max-cardinality restriction sees one
  rename row, not "renamed" **and** "new constraint" as two separate facts.

  This is distinct from the cascade-on-*other*-entities behaviour, which is
  intentional and tested: a restriction/hierarchy/domain-range change on a
  **persisting** entity that merely *references* the renamed IRI is correctly
  preserved as an independent change unless it is a pure IRI substitution. Only
  additions on the renamed entity *itself* are absorbed.

  **Test workaround:** because additions on the renamed entity are invisible, the
  `class_rename_with_new_restriction_*` fixtures place the genuinely-new
  restriction on a *persisting* class (`era:Platform`), not on the renamed class,
  so `test_cascade_preserves_independent_changes` can assert the
  cascade-preserves-independence behaviour without tripping over this limitation.

  **Deferred fix (v2):** after rename detection consolidates a pair, re-run a
  delta pass on the renamed entity's axioms (after substituting the old IRI for
  the new one) and surface any remaining structural additions as independent
  Layer 1 changes. Recorded in `docs/DESIGN_DECISIONS.md` (DD-018) and the
  roadmap backlog.

## Out of scope (deliberately)

- Individual (instance-level) renames — out of scope.
- Datatype renames — out of scope.
- Detection of class splits (one class → two classes) — semantically a refactor, not a rename.
- Detection of class merges (two classes → one) — symmetric, deferred.
- ML/embedding-based similarity — out of scope; would require new dependencies.
- Rename detection across two ontologies that don't share a common ancestor — not the use case.
- Suggesting renames the user might want to confirm interactively — interactive flow is out of scope; v1 is batch.

## Open questions

- [x] **Q1 (resolved — adopted proposed):** For the label-match heuristic, require *exact* match (same lang, same text). A single matching `(lang, text)` pair is sufficient for "high confidence". Implemented in `rename._apply_label`, which intersects the two entities' `(lang, text)` label sets and additionally requires the pairing to be *unique on both sides* (mutual uniqueness) before emitting at high confidence.

- [x] **Q2 (resolved — adopted proposed):** Fingerprint acceptance threshold `0.6` and separation requirement `0.2`. Pinned as `ACCEPT_THRESHOLD` / `SEPARATION_THRESHOLD` in `diff/_rename_evidence.py` and asserted in `tests/unit/test_rename_fingerprint.py`. The four scoring weights (`0.3/0.2/0.1/0.05`) and caps (`0.5/0.4/0.3/0.2`) are likewise pinned; the raw sum is clamped to `1.0`.

- [x] **Q3 (resolved — adopted proposed):** Cascade consequences are subsumed entirely (no placeholder change). The consolidated change ids are recorded in `details.cascade_subsumes` of the rename change as the audit trail. Implemented in `rename._cascade`, which handles both single before/after changes that collapse to a no-op after substitution and removed/added pairs that differ only by the substitution.

All three open questions were resolved by adopting the proposed answers during implementation.

## References

- `docs/ARCHITECTURE.md` § Rename Detector (this fills the empty section)
- `docs/DESIGN_DECISIONS.md` § DD-006 (frozen), § DD-008 (severity)
- `docs/GLOSSARY.md` § Rename, § Fingerprint, § Confidence
- Components 06–09 specs for the `*_added`/`*_removed` change kinds this consumes
- Component 10 spec for pipeline ordering (renames before severity refinement)
