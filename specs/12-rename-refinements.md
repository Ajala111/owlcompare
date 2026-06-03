# Component 12: Rename Refinements

## Identity

- **Component number:** 12
- **Name:** Rename refinements (DD-018 fix + `--export-rename-mapping`)
- **Module paths:**
  - `src/owlcompare/diff/rename.py` — extended with post-rename axiom re-diffing
  - `src/owlcompare/rename_mapping.py` — extended with `dump()` for export
- **Roadmap phase:** Phase 3 (second and final component of this phase)
- **Depends on components:** 11 (rename detection — extends it), 06 / 07 / 08 / 09 (Layer 1 diff slices — used for re-diffing post-rename), 10 (severity — runs after this)
- **Depended on by (planned):** 14–17 (renderers), 19 (GitHub Action — workflow loops use exported mappings)

## Purpose

Two finishing touches on the rename system:

**Part A — Post-rename axiom re-diffing (the DD-018 fix).** When Component 11 consolidates a rename pair, structural axioms that were *added* to the renamed entity in v2 — new restrictions, new parents, new annotations — are silently absorbed into the cascade. This component re-runs a targeted diff over the renamed entity's axioms (with IRIs substituted) and surfaces any genuinely new axioms as independent Layer 1 changes.

**Part B — Export rename mapping (`--export-rename-mapping FILE`).** Write the accepted renames from a diff as a TOML file in the same format `--rename-mapping` accepts. Lets users commit a mapping alongside their ontology and reuse it in future diffs, or feed it to other tooling.

What would break if we removed it: Part A's gap (DD-018) would persist — renames that *also* add structure would silently hide the additions. Part B's gap would mean every diff has to redo rename detection from scratch; teams wanting to stabilize their rename mapping over time would have no good workflow.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Diff result (post-rename, pre-severity) | `DiffResult` | Component 11's output | Renames already consolidated |
| Both snapshots | `OntologySnapshot` × 2 | Same as Component 11 | Needed for the targeted re-diff |
| Export path | `Path \| None` | CLI flag | If provided, dump the mapping |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `DiffResult` (extended) | dataclass | Severity classifier (next) | Independent additions on renamed entities now surface as their own Changes |
| Optional TOML file | file on disk | User / downstream tooling | Schema version 1, same as `--rename-mapping` |

## Public API

### Part A — Post-rename re-diffing

Add to `src/owlcompare/diff/rename.py`:

```python
def re_diff_renamed_entities(
    result: DiffResult,
    a: OntologySnapshot,
    b: OntologySnapshot,
) -> DiffResult:
    """For each rename in result.metadata['renames_applied'], re-diff the
    renamed entity's axioms (with IRIs substituted) and surface any new
    structural additions as independent Layer 1 Change records.

    This complements Component 11's cascade, which absorbs add+remove pairs
    that differ only by the renamed IRI. Anything that *can't* be matched
    that way — i.e., axioms that are genuinely new on the renamed entity
    in v2 — gets emitted here.

    Returns a new DiffResult. The original is not mutated.
    """
```

The detection loop in `detect(...)` is extended to call `re_diff_renamed_entities()` after the cascade pass, before returning. Callers using `detect()` get the fix automatically.

### Part B — Mapping export

Extend `src/owlcompare/rename_mapping.py`:

```python
def dump(mapping_or_diff_result, path: Path) -> None:
    """Write a RenameMapping or DiffResult to disk as TOML.

    Accepts either:
      - A RenameMapping directly (programmatic export)
      - A DiffResult; in this case, build a RenameMapping from
        result.metadata['renames_applied'] and write that

    The output is loadable by load().
    """
```

The DiffResult overload is the typical CLI path: detect renames, dump them as TOML, future diffs use them as `--rename-mapping`.

## CLI integration

Add one new flag to the `diff` subcommand:

```
owlcompare diff [OPTIONS] ONTOLOGY_A ONTOLOGY_B

  --export-rename-mapping PATH    Write detected renames to a TOML file
                                  loadable by --rename-mapping.
                                  Does not affect stdout/stderr output.
```

Behavior:
- When the flag is set, after rename detection runs, dump the result's `renames_applied` to the given path. Create the file if it doesn't exist; overwrite if it does.
- The flag is *additive* — it doesn't suppress other output. Users get the normal text/JSON diff AND the exported file.
- If no renames were detected, the file is still written but with an empty `classes`/`properties`/etc. structure plus `schema_version = 1`. (An empty mapping is meaningful: "we checked, found none.")
- On write failure (permission denied, path invalid): raise `RenameMappingError` exit code 5 (report generation error — consistent with other write failures).

## Internal design

### Part A — Re-diff algorithm

For each `RenameCandidate` in `result.metadata['renames_applied']` (processed in
`before_iri` order):

1. Get the `before_iri` (in A) and `after_iri` (in B).
2. Build a minimal one-entity *sub-snapshot* for each side, holding only the
   entity's **own axioms**:
   - All triples where the entity is the **subject** (`before_iri` in A,
     `after_iri` in B), **plus** the transitive closure of any synthetic
     restriction/list URNs (`urn:owlcompare:restriction:…` / `…:list:…`) those
     triples reference in object position — so a reified restriction attached to
     the entity is pulled in whole and can be decoded.
   - **Object-position triples that reference the entity from *other* entities are
     deliberately excluded.** Those are cascade territory: they were already
     consolidated by Component 11's `_cascade` (a referencing edge that is a pure
     IRI substitution collapses into the rename; anything else stays an
     independent change on the *referencing* entity). Leaving them out of the
     re-diff is exactly how the cascade is excluded — see Q1.
3. Substitute IRIs into A's sub-snapshot: every accepted rename's `old → new` is
   applied, so the entity (and any transitively-renamed references) reads as
   "what A would look like if the renames had already been applied." B's
   sub-snapshot needs no substitution (it already uses the new IRIs).
4. Re-run the Layer 1 slices — hierarchy (Component 07), restrictions
   (Component 08), annotations (Component 09) — over the A/B sub-snapshots, with a
   fresh `SubsumptionRegistry` and empty Layer 0 input. Because the entity exists
   on both sides (post-substitution), no slice's "wholly added/removed" deferral
   fires, so each genuine delta surfaces directly.
5. Emit whatever those slices produce as independent Layer 1 `Change` records. By
   construction `subject = after_iri` (A was substituted), with `kind` and
   severity assigned by the producing slice.

The clever bit: the re-diff doesn't reinvent the classification logic. It runs the
*actual* Layer 1 slices (which themselves call `_restriction_index.build`,
`_annotation_index.build`, `_hierarchy_index.build`) on minimal one-entity
sub-snapshot pairs. This keeps both classification *and* severity consistent with
the rest of the diff pipeline, with no parallel implementation to drift.

### Subsumption update

Any new Change emitted by the re-diff:
- Has its own fresh `change_id`.
- Is added to the result's `changes` tuple.
- Is added to the rename's `details.cascade_subsumes` list, so the audit trail shows the relationship: "this restriction-added was discovered via post-rename re-diff of the entity that was renamed from X to Y."

### Severity for re-diffed Changes

Same severity rules as the original Layer 1 slice would have applied if the change were detected normally. Component 12 doesn't introduce new severities — it just makes existing severity classifications reachable via a path Component 11 had short-circuited.

### Part A — Known limitations

- **Self-referential restriction filler on a renamed entity.** A restriction
  *attached to* a renamed entity whose *filler is that same renamed entity*
  (e.g. `era:Track rdfs:subClassOf [ owl:onProperty p ; owl:someValuesFrom era:Track ]`)
  is not exercised. Reified restriction URNs are content hashes minted by
  canonicalization, so when the renamed IRI is substituted into A the URN string
  does not change with it; an otherwise-identical restriction can then look like a
  changed restriction whose decoded `before`/`after` are equal, surfacing a no-op
  `restriction_changed` in such pathological cases. Real-world ontologies don't
  typically point a class's restriction filler back at the class itself, so this
  is left for a future iteration (consistent with the spec's general deferral of
  self-referential / pathological class-expression cases). The flagship and the
  per-kind fixtures all use non-self-referential fillers.

### Part B — Export format

The output TOML matches the existing `--rename-mapping` schema exactly:

```toml
schema_version = 1

[[classes]]
old = "http://data.europa.eu/949/Track"
new = "http://data.europa.eu/949/RailwayTrack"

[[object_properties]]
old = "http://data.europa.eu/949/locatedOn"
new = "http://data.europa.eu/949/hasLocation"
```

Constraints:
- Only `certain` and `high` confidence renames are exported by default. `medium` are excluded because they could be wrong; the user should review them first.
- Exception: if `--rename-confidence medium` was used to run the diff (explicit opt-in to medium), include them in the export.
- The export does NOT include confidence or evidence — those are derived; the TOML is meant for reuse as input, where everything is `certain` by construction.
- One `[[classes]]` entry per rename, sorted alphabetically by `old` IRI for stable diffs.

### CLI integration ordering

The `--export-rename-mapping` write happens *after* the orchestrator returns the final DiffResult and *before* rendering. This way:
- The export is computed from the final result (after severity refinement)
- A rendering or output failure doesn't prevent the export from being written

If `--no-severity-refinement` is set, the export still happens.

If `--rename-confidence none` is set (rename detection disabled), the export writes an empty mapping. Log INFO that the export is empty because detection was disabled.

## Edge cases & failure modes

**Part A:**

- **Renamed entity is a property whose domain/range references another renamed entity:** transitive. The re-diff sees the substituted IRI; both renames have already been applied at substitution time, so the comparison works correctly.
- **Renamed entity has only the bare rename axioms** (`rdf:type`, `rdfs:label`) and no structural additions: the symmetric difference is empty after substitution. Nothing to emit. Common case; no-op.
- **Renamed entity gained a property whose subject is the entity AND lost a property whose subject is the entity (e.g., a restriction was swapped):** the re-diff sees both. Each surfaces as its own Change. The user understands "restriction X removed, restriction Y added" alongside the rename.
- **A renamed entity is also the target of another rename's cascade:** the order matters. Process renames in deterministic order (alphabetical by `before_iri`); each rename's re-diff sees the world as if all *previously-processed* renames had been applied to A. This is the simplest model that works; pathological cases would need iterative re-diffing (deferred to v2 if it ever becomes an issue).
- **The renamed entity has *thousands* of associated triples** (a hub class in a large ontology): the re-diff is O(N) per rename in the size of the entity's axiom set. Acceptable for v1.

**Part B:**

- **Export path is a directory or unwritable:** `RenameMappingError` exit code 5 with a clear message.
- **Export when no renames were detected:** write an empty mapping (`schema_version = 1` with empty arrays) and log INFO. Don't error.
- **Export when `--rename-confidence none`:** same as above — empty mapping, INFO log.
- **Export overwrites existing file silently:** documented in `--help`. No prompt or backup.
- **Export of `medium` confidence renames without explicit opt-in:** they're skipped silently. The exported file has only certain + high renames. Test this carefully.

## Dependencies to add

None.

## Acceptance tests

Located in `tests/unit/test_rename_redidiff.py` (Part A), extensions to `tests/unit/test_rename_mapping.py` (Part B), extensions to `tests/unit/test_cli_diff.py`, extensions to `tests/integration/test_diff_integration.py`.

### Fixtures to add (`tests/fixtures/rename/redidiff/`)

- `rename_plus_new_restriction_v1.ttl` / `_v2.ttl` — class renamed AND a new max-cardinality restriction added on it. Re-diff should emit one `restriction_added` independently.
- `rename_plus_removed_annotation_v1.ttl` / `_v2.ttl` — class renamed AND a French label removed from it. Re-diff should emit one `annotation_removed`.
- `rename_plus_new_parent_v1.ttl` / `_v2.ttl` — class renamed AND a new `subClassOf` edge added. Re-diff should emit one `class_parent_added`.
- `rename_plus_swapped_restriction_v1.ttl` / `_v2.ttl` — class renamed AND restriction kind changed (`someValuesFrom` → `allValuesFrom`). Re-diff should emit one `restriction_changed`.
- `rename_pure_no_structural_change_v1.ttl` / `_v2.ttl` — class renamed cleanly, no other structural change. Re-diff should emit zero new Changes (regression: don't accidentally emit phantom changes for pure renames).
- `era_rename_with_additions_v1.ttl` / `_v2.ttl` — flagship: 2 renames (Track and Signal) plus on Track a new restriction was added, on Signal an annotation was removed. Expected output: 2 renames + 1 restriction_added + 1 annotation_removed = 4 visible changes.

### Test list

**`tests/unit/test_rename_redidiff.py` (Part A):**

- [ ] `test_redidiff_pure_rename_emits_no_new_changes`
- [ ] `test_redidiff_rename_plus_restriction_emits_restriction_added`
- [ ] `test_redidiff_rename_plus_removed_annotation_emits_annotation_removed`
- [ ] `test_redidiff_rename_plus_new_parent_emits_class_parent_added`
- [ ] `test_redidiff_rename_plus_swapped_restriction_emits_restriction_changed`
- [ ] `test_redidiff_new_change_subject_is_after_iri_not_before`
- [ ] `test_redidiff_new_change_appears_in_rename_cascade_subsumes`
- [ ] `test_redidiff_new_change_has_fresh_change_id`
- [ ] `test_redidiff_new_change_severity_matches_layer1_slice_default` — e.g., `restriction_added` is `breaking`.
- [ ] `test_redidiff_multiple_renames_independent` — two renames each with independent additions; both sets of new changes surface.
- [ ] `test_redidiff_does_not_mutate_input_result`
- [ ] `test_redidiff_no_renames_returns_result_unchanged`

**`tests/unit/test_rename_mapping.py` extensions (Part B):**

- [ ] `test_dump_writes_valid_toml`
- [ ] `test_dump_empty_mapping_writes_schema_version_only`
- [ ] `test_dump_classes_sorted_by_old_iri`
- [ ] `test_dump_properties_sorted_by_old_iri`
- [ ] `test_dump_accepts_renamemapping_directly`
- [ ] `test_dump_accepts_diffresult_extracts_renames_applied`
- [ ] `test_dump_excludes_medium_confidence_by_default`
- [ ] `test_dump_includes_medium_confidence_when_user_opted_in` — via an optional `include_medium=True` parameter.
- [ ] `test_dump_round_trip` — write, then load; resulting RenameMapping equals the source.
- [ ] `test_dump_write_failure_raises_rename_mapping_error_exit_code_5`

**`tests/unit/test_cli_diff.py` extensions:**

- [ ] `test_cli_diff_export_rename_mapping_writes_file`
- [ ] `test_cli_diff_export_rename_mapping_with_no_renames_writes_empty_file`
- [ ] `test_cli_diff_export_rename_mapping_with_rename_confidence_none_writes_empty`
- [ ] `test_cli_diff_export_rename_mapping_round_trip` — export, then use as `--rename-mapping` in a second invocation against the same fixtures; second invocation reports `certain` confidence.
- [ ] `test_cli_diff_export_rename_mapping_unwritable_path_exits_5`
- [ ] `test_cli_diff_export_does_not_suppress_normal_output`

**`tests/integration/test_diff_integration.py` extensions:**

- [ ] `test_era_rename_with_additions_emits_expected_4_changes` — flagship.
- [ ] `test_era_renames_export_round_trip` — export from era_renames, re-run with the mapping, all renames now `certain`.
- [ ] `test_simple_rename_fixture_now_no_phantom_changes` — Component 12's re-diff doesn't introduce new Changes for the pure-rename fixture (regression).

## Out of scope (deliberately)

- The other refinements I'd originally sketched for Components 12 and 13:
  - Many-to-many disambiguation via secondary signals (medium priority backlog).
  - Confidence calibration with numeric scores beyond the three tiers (low priority).
  - Multi-language weighting (low priority).
  - Negative-evidence scoring (low priority).
  - `--list-renames` flag (use `--format json | jq ...` instead for now).
  - "Uncertain candidates" surfacing (low priority).
  - Reverse-mapping consistency check (low priority).
- Iterative re-diffing when renames cross-reference each other (only needed for pathological cases).
- An interactive "confirm each detected rename" mode (the project is batch-first).

These are all valid v2 enhancements, captured in the backlog.

## Open questions

- [x] **Q1 (resolved — adopted proposed, refined):** Cascade-accounted axioms must not be double-counted by the re-diff. **Implementation:** rather than building the symmetric difference over subject-*and*-object triples and subtracting a separate cascade set, `re_diff_renamed_entities` restricts each entity's axiom set to its *own* axioms — triples where the entity is the **subject**, plus the transitive closure of any synthetic restriction/list URNs they point at. Cascade triples (references to the entity from *other* entities) live in object position and are already consolidated by Component 11's `_cascade`, so they are structurally excluded. The `rename_pure_no_structural_change_*` canary (`test_redidiff_pure_rename_emits_no_new_changes`) pins this: a clean rename emits zero new changes.

- [x] **Q2 (resolved — adopted proposed):** One `dump()` function with `isinstance` dispatch on `RenameMapping | DiffResult`. A `RenameMapping` is written verbatim; a `DiffResult` is reduced to a mapping from `metadata['renames_applied']` first.

- [x] **Q3 (resolved — adopted proposed):** No comments in the exported TOML. The output is purely declarative (`schema_version` plus the array-of-tables sections), sorted by `old` IRI, so a re-export is byte-stable.

All three open questions were resolved by adopting the proposed answers during implementation.

## References

- `docs/ARCHITECTURE.md` § Rename Detector
- `docs/DESIGN_DECISIONS.md` § DD-018 (the limitation Part A addresses)
- Component 11 spec for the rename detection foundation
- Component 10 spec for the orchestrator pipeline order (Component 12 runs inside `detect()`, which is between Layer 1 and severity)
