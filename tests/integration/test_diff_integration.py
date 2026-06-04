"""Integration tests for Layer 0 diff — specs/05-syntactic-diff.md.

The flagship ``era_evolution`` pair drives the realism of the whole component:
its four intended edits (one class added, one property removed, one cardinality
change, one French label change) plus a version bump expand to an exact set of
triple-level changes that we pin here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from rdflib import RDF

from owlcompare._render_diff import diff_json
from owlcompare.canonicalize import canonicalize
from owlcompare.diff import _severity_rules, orchestrator, syntactic
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.structural import entities
from owlcompare.loader import load

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"
HIER = DIFF / "hierarchy"
SEV = FIXTURES / "severity"


def _run_sev(v_a: str, v_b: str):
    return orchestrator.run(canonicalize(load(str(SEV / v_a))), canonicalize(load(str(SEV / v_b))))


_RDF_TYPE = str(RDF.type)
_SUBCLASS_OF = "http://www.w3.org/2000/01/rdf-schema#subClassOf"


def _canon(name: str):
    return canonicalize(load(str(DIFF / name)))


def _canon_hier(name: str):
    return canonicalize(load(str(HIER / name)))


def test_era_evolution_fixture_produces_expected_change_counts():
    changes = syntactic.diff(_canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl"))

    removed = [c for c in changes if c.kind == "triple_removed"]
    added = [c for c in changes if c.kind == "triple_added"]
    breaking = [c for c in changes if c.severity == "breaking"]

    assert len(changes) == 18
    assert len(removed) == 10
    assert len(added) == 8
    assert len(breaking) == 5

    # The added class: era:Platform declared as an owl:Class (additive).
    platform_decl = [
        c
        for c in added
        if c.subject == "http://data.europa.eu/949/Platform"
        and c.details["predicate_iri"] == _RDF_TYPE
    ]
    assert len(platform_decl) == 1
    assert platform_decl[0].severity == "additive"

    # The French label change surfaces as one removed + one added rdfs:label.
    fr_removed = [c for c in removed if c.details["object"] == '"Voie"@fr']
    fr_added = [c for c in added if c.details["object"] == '"Voie ferrée"@fr']
    assert len(fr_removed) == 1
    assert len(fr_added) == 1
    assert fr_removed[0].severity == "info"
    assert fr_added[0].severity == "info"

    # The removed property era:locatedOn contributes breaking removals.
    located_on = [c for c in removed if c.subject == "http://data.europa.eu/949/locatedOn"]
    assert len(located_on) == 4


def test_diff_via_python_dash_m_subprocess():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "owlcompare",
            "diff",
            str(DIFF / "era_evolution_v1.ttl"),
            str(DIFF / "era_evolution_v2.ttl"),
            "--layers",
            "syntactic",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    # era_evolution has breaking changes -> exit 10. Pinned to the syntactic
    # layer so the Layer 0 triple totals stay the baseline for this check.
    assert proc.returncode == 10
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == 1
    assert payload["summary"]["total"] == 18
    assert payload["summary"]["breaking"] == 5


def _run(v_a: str, v_b: str):
    return orchestrator.run(_canon(v_a), _canon(v_b))


def test_era_evolution_layer1_emits_class_added_for_platform():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    class_added = [c for c in result.changes if c.layer == "structural" and c.kind == "class_added"]
    assert len(class_added) == 1
    assert class_added[0].subject == "http://data.europa.eu/949/Platform"
    assert class_added[0].severity == "additive"
    assert class_added[0].summary == 'Class added: era:Platform "Platform"@en'


def test_era_evolution_layer1_emits_object_property_removed_for_locatedon():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    removed = [
        c for c in result.changes if c.layer == "structural" and c.kind == "object_property_removed"
    ]
    assert len(removed) == 1
    assert removed[0].subject == "http://data.europa.eu/949/locatedOn"
    assert removed[0].severity == "breaking"


def test_era_evolution_layer1_subsumes_associated_layer0_changes():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    platform = next(
        c
        for c in result.changes
        if c.kind == "class_added" and c.subject == "http://data.europa.eu/949/Platform"
    )
    # Platform's rdf:type + rdfs:label triple additions are both subsumed.
    assert len(platform.details["subsumes"]) == 2
    for layer0_id in platform.details["subsumes"]:
        assert registry.is_explained(layer0_id)


def test_era_evolution_total_change_count_reduces_with_subsumption():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    structural = [c for c in result.changes if c.layer == "structural"]
    layer0 = [c for c in result.changes if c.layer == "syntactic"]
    unexplained = [c for c in layer0 if not registry.is_explained(c.details["change_id"])]
    visible_by_default = len(structural) + len(unexplained)
    assert visible_by_default < len(result.changes)
    # And strictly fewer than Component 05's flat 18 Layer 0 changes.
    assert visible_by_default < 18


def _run_hier(v_a: str, v_b: str):
    return orchestrator.run(_canon_hier(v_a), _canon_hier(v_b))


def test_era_hierarchy_fixture_emits_one_reparented_change():
    result = _run_hier("era_hierarchy_v1.ttl", "era_hierarchy_v2.ttl")
    reparented = [c for c in result.changes if c.kind == "class_reparented"]
    assert len(reparented) == 1
    assert reparented[0].subject == "http://data.europa.eu/949/Signal"
    assert reparented[0].details["parents_before"] == ["http://data.europa.eu/949/Equipment"]
    assert reparented[0].details["parents_after"] == ["http://data.europa.eu/949/Asset"]


def test_era_hierarchy_fixture_emits_one_class_added_for_asset():
    result = _run_hier("era_hierarchy_v1.ttl", "era_hierarchy_v2.ttl")
    class_added = [c for c in result.changes if c.kind == "class_added"]
    assert len(class_added) == 1
    assert class_added[0].subject == "http://data.europa.eu/949/Asset"


def test_era_hierarchy_fixture_subsumes_subclassof_triples():
    result = _run_hier("era_hierarchy_v1.ttl", "era_hierarchy_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    reparented = next(c for c in result.changes if c.kind == "class_reparented")
    # The reparent subsumes both the removed (Signal->Equipment) and added
    # (Signal->Asset) subClassOf triples.
    subclass_changes = [
        c
        for c in result.changes
        if c.layer == "syntactic"
        and c.subject == "http://data.europa.eu/949/Signal"
        and c.details.get("predicate_iri") == _SUBCLASS_OF
    ]
    assert len(subclass_changes) == 2
    assert len(reparented.details["subsumes"]) == 2
    for change in subclass_changes:
        assert registry.is_explained(change.details["change_id"])


def test_era_evolution_fixture_unchanged_results():
    # Regression: era_evolution has no hierarchy changes, so the only structural
    # change beyond the entity slice is Component 08's restriction_changed (the
    # era:Track max-cardinality tuning). Everything the entity slice emits must
    # still appear verbatim — Components 07/08 only add, never alter, those.
    a, b = _canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl")
    layer0 = syntactic.diff(a, b)
    entities_only = entities.diff(a, b, layer0, SubsumptionRegistry())

    result = orchestrator.run(a, b)
    structural = [c for c in result.changes if c.layer == "structural"]
    entity_kinds = {"class_added", "object_property_removed"}
    assert [c for c in structural if c.kind in entity_kinds] == entities_only
    restriction_changes = [c for c in structural if c.kind == "restriction_changed"]
    assert len(restriction_changes) == 1


RESTR = DIFF / "restrictions"


def _canon_restr(name: str):
    return canonicalize(load(str(RESTR / name)))


def _run_restr(v_a: str, v_b: str):
    return orchestrator.run(_canon_restr(v_a), _canon_restr(v_b))


def test_era_restrictions_fixture_emits_three_changes():
    result = _run_restr("era_restrictions_v1.ttl", "era_restrictions_v2.ttl")
    structural = [c for c in result.changes if c.layer == "structural"]
    changed = [c for c in structural if c.kind == "restriction_changed"]
    removed = [c for c in structural if c.kind == "restriction_removed"]
    added = [c for c in structural if c.kind == "restriction_added"]
    assert len(changed) == 1  # era:hasMaxSpeed max 5 -> max 3 (tightened)
    assert len(removed) == 1  # era:hasGauge someValuesFrom era:Gauge dropped
    assert len(added) == 1  # era:servesPlatform someValuesFrom era:Platform added
    assert changed[0].severity == "breaking"


def test_era_restrictions_subsumes_all_restriction_triples():
    result = _run_restr("era_restrictions_v1.ttl", "era_restrictions_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    restriction_triples = [
        c
        for c in result.changes
        if c.layer == "syntactic"
        and "urn:owlcompare:restriction:" in (c.details.get("subject") or "")
    ]
    # Also the subClassOf edges that point at restriction URNs.
    edge_triples = [
        c
        for c in result.changes
        if c.layer == "syntactic"
        and "urn:owlcompare:restriction:" in (c.details.get("object") or "")
    ]
    assert restriction_triples
    for triple in restriction_triples + edge_triples:
        assert registry.is_explained(triple.details["change_id"])


def test_era_evolution_fixture_now_subsumes_restriction_triples():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    # The two reified restriction URNs from era_evolution (max 1 / max 2 on
    # era:hasMaxSpeed) are now folded into a single restriction_changed.
    restriction_triples = [
        c
        for c in result.changes
        if c.layer == "syntactic"
        and (
            "urn:owlcompare:restriction:" in (c.details.get("subject") or "")
            or "urn:owlcompare:restriction:" in (c.details.get("object") or "")
        )
    ]
    assert restriction_triples
    for triple in restriction_triples:
        assert registry.is_explained(triple.details["change_id"])

    layer0 = [c for c in result.changes if c.layer == "syntactic"]
    unexplained = [c for c in layer0 if not registry.is_explained(c.details["change_id"])]
    # Down from 14 (Component 06/07 era) to the handful of label/version triples
    # that Component 09 and later will explain.
    assert len(unexplained) <= 6


def test_era_evolution_emits_cardinality_change_for_maxspeed():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    changed = [c for c in result.changes if c.kind == "restriction_changed"]
    assert len(changed) == 1
    change = changed[0]
    assert change.details["entity_iri"] == "http://data.europa.eu/949/Track"
    assert change.details["before"]["cardinality"] == 1
    assert change.details["after"]["cardinality"] == 2


ANNO = DIFF / "annotations"


def _canon_anno(name: str):
    return canonicalize(load(str(ANNO / name)))


def _run_anno(v_a: str, v_b: str):
    return orchestrator.run(_canon_anno(v_a), _canon_anno(v_b))


def test_era_evolution_fixture_after_component_09():
    # After Component 09 the two French label triples fold into one
    # annotation_changed and the two owl:versionInfo triples into one
    # ontology_metadata_changed; Layer 0 unexplained drops to zero.
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    registry = result.metadata["subsumption_registry"]

    label_changes = [
        c
        for c in result.changes
        if c.kind == "annotation_changed"
        and c.subject == "http://data.europa.eu/949/Track"
        and c.details.get("language") == "fr"
    ]
    assert len(label_changes) == 1
    assert label_changes[0].details["before"]["value"] == "Voie"
    assert label_changes[0].details["after"]["value"] == "Voie ferrée"

    version_changes = [c for c in result.changes if c.kind == "ontology_metadata_changed"]
    assert len(version_changes) == 1
    assert version_changes[0].details["before"]["value"] == "1.0.0"
    assert version_changes[0].details["after"]["value"] == "2.0.0"

    layer0 = [c for c in result.changes if c.layer == "syntactic"]
    unexplained = [c for c in layer0 if not registry.is_explained(c.details["change_id"])]
    assert unexplained == []


def test_era_evolution_emits_label_changed_for_voie_voie_ferree():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    change = next(
        c
        for c in result.changes
        if c.kind == "annotation_changed" and c.details.get("language") == "fr"
    )
    assert change.severity == "info"
    assert "Voie" in change.summary
    assert "Voie ferrée" in change.summary


def test_era_evolution_emits_ontology_metadata_changed_for_versioninfo():
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    change = next(c for c in result.changes if c.kind == "ontology_metadata_changed")
    assert change.details["predicate_short"] == "versionInfo"
    assert change.subject == "http://data.europa.eu/949/ontology"


def test_era_annotations_fixture_emits_expected_changes():
    result = _run_anno("era_annotations_v1.ttl", "era_annotations_v2.ttl")
    structural = [c for c in result.changes if c.layer == "structural"]
    kinds = sorted(c.kind for c in structural)
    # French label change + comment change + Signal deprecation + version bump.
    assert kinds == [
        "annotation_changed",
        "annotation_changed",
        "entity_deprecated",
        "ontology_metadata_changed",
    ]


# --------------------------------------------------------------------------- #
# Component 10 — severity refinement
# --------------------------------------------------------------------------- #


def test_era_evolution_severity_refinement_only_affects_subsumed_layer0():
    # era_evolution has no genuine cross-cutting case, but Rule 6 (subsumed Layer 0
    # -> info) is universal and fires on the triples folded into Layer 1 changes.
    # The invariant is therefore not "no refinements" but "nothing meaningful was
    # touched": only Rule 6 fired, and only on subsumed Layer 0 changes.
    result = _run("era_evolution_v1.ttl", "era_evolution_v2.ttl")
    registry = result.metadata["subsumption_registry"]
    refinements = result.metadata["severity_refinements"]

    # 1. Every refinement that happened is Rule 6 — no other rule misfired here.
    assert refinements  # Rule 6 does fire (this fixture subsumes plenty)
    assert all(r.rule_id == "subsumed-layer0-info" for r in refinements)

    refined_ids = {r.change_id for r in refinements}

    # 2. No Layer 1 (structural) change had its severity refined.
    structural_ids = {c.details["change_id"] for c in result.changes if c.layer == "structural"}
    assert refined_ids.isdisjoint(structural_ids)

    # 3. No *unsubsumed* Layer 0 change had its severity refined.
    unsubsumed_layer0_ids = {
        c.details["change_id"]
        for c in result.changes
        if c.layer == "syntactic" and not registry.is_explained(c.details["change_id"])
    }
    assert refined_ids.isdisjoint(unsubsumed_layer0_ids)

    # 4. Exit code unchanged: era:locatedOn's object_property_removed is still
    #    breaking after refinement, so the CI signal stays 10.
    assert any(c.severity == "breaking" for c in result.changes)


def test_era_annotations_label_change_on_deprecated_entity_demoted():
    # A label change AND a deprecation land on the same entity (era:Track). Rule 2
    # treats the editorial edit as reduced significance.
    result = _run_sev("annotation_on_deprecated_v1.ttl", "annotation_on_deprecated_v2.ttl")
    track = "http://data.europa.eu/949/Track"

    assert any(c.kind == "entity_deprecated" and c.subject == track for c in result.changes)
    label = next(c for c in result.changes if c.kind == "annotation_changed" and c.subject == track)
    # End state: the editorial change on the deprecating entity is info.
    assert label.severity == "info"
    # Rule 2 is what classifies it so — observable by forcing a non-info copy
    # (in the real pipeline Component 09 already emits annotations as info, so the
    # demotion is a no-op and is not written to the audit trail; Q3).
    forced = replace(label, severity="breaking")
    ref = _severity_rules.rule_annotation_on_deprecated(forced, result)
    assert ref is not None
    assert ref.refined_severity == "info"
    assert ref.rule_id == "annotation-on-deprecated"


# --------------------------------------------------------------------------- #
# Component 11 — rename detection
# --------------------------------------------------------------------------- #

REN = FIXTURES / "rename"


def _canon_ren(name: str):
    return canonicalize(load(str(REN / name)))


def _run_ren(v_a: str, v_b: str, **kwargs):
    return orchestrator.run(_canon_ren(v_a), _canon_ren(v_b), **kwargs)


def test_simple_rename_fixture_produces_one_renamed_change():
    result = _run_ren("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl")
    structural = [c for c in result.changes if c.layer == "structural"]
    assert len([c for c in structural if c.kind == "class_renamed"]) == 1
    assert [c for c in structural if c.kind == "class_removed"] == []
    assert [c for c in structural if c.kind == "class_added"] == []


def test_cascade_fixture_consolidates_referencing_changes():
    result = _run_ren("cascade_simple_v1.ttl", "cascade_simple_v2.ttl")
    structural = [c for c in result.changes if c.layer == "structural"]
    assert sorted(c.kind for c in structural) == ["class_renamed"]
    renamed = next(c for c in structural if c.kind == "class_renamed")
    # Both the Tunnel reparent and the measuredOn range_changed are subsumed.
    assert len(renamed.details["cascade_subsumes"]) == 2


def test_era_renames_fixture_produces_expected_counts():
    result = _run_ren("era_renames_v1.ttl", "era_renames_v2.ttl")
    structural = [c for c in result.changes if c.layer == "structural"]
    class_renames = [c for c in structural if c.kind == "class_renamed"]
    prop_renames = [c for c in structural if c.kind == "object_property_renamed"]
    assert len(class_renames) == 2
    assert len(prop_renames) == 1
    # No leftover add/remove or cascade consequences, and Layer 0 fully explained.
    leftover = {"class_added", "class_removed", "class_reparented", "restriction_changed"}
    assert not [c for c in structural if c.kind in leftover]
    registry = result.metadata["subsumption_registry"]
    layer0 = [c for c in result.changes if c.layer == "syntactic"]
    unexplained = [c for c in layer0 if not registry.is_explained(c.details["change_id"])]
    assert unexplained == []


def test_era_evolution_fixture_unchanged_after_rename_detection():
    # era_evolution has no renames, so enabling Component 11 must leave the diff
    # byte-identical to the pre-Component-11 pipeline.
    a, b = _canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl")
    with_renames = orchestrator.run(a, b)
    without_renames = orchestrator.run(a, b, detect_renames=False)
    refined_with = with_renames.metadata["severity_refinements"]
    refined_without = without_renames.metadata["severity_refinements"]
    assert diff_json(list(with_renames.changes), refined_with) == diff_json(
        list(without_renames.changes), refined_without
    )


def test_severity_classifier_runs_after_renames():
    # The severity classifier sees the *consolidated* result: the cascade reparent
    # is gone before refinement, and the rename itself is info.
    result = _run_ren("cascade_simple_v1.ttl", "cascade_simple_v2.ttl")
    renamed = next(c for c in result.changes if c.kind == "class_renamed")
    assert renamed.severity == "info"
    assert not any(c.kind == "class_reparented" for c in result.changes)
    refinements = result.metadata["severity_refinements"]
    refined_ids = {r.change_id for r in refinements}
    assert renamed.details["change_id"] not in refined_ids


REDIDIFF = REN / "redidiff"


def _canon_redidiff(name: str):
    return canonicalize(load(str(REDIDIFF / name)))


def _run_redidiff(v_a: str, v_b: str, **kwargs):
    return orchestrator.run(_canon_redidiff(v_a), _canon_redidiff(v_b), **kwargs)


def test_era_rename_with_additions_emits_expected_4_changes():
    # Flagship for Component 12 Part A: 2 renames + 1 restriction_added + 1
    # annotation_removed surfaced by the post-rename re-diff.
    result = _run_redidiff("era_rename_with_additions_v1.ttl", "era_rename_with_additions_v2.ttl")
    structural = [c for c in result.changes if c.layer == "structural"]
    assert sorted(c.kind for c in structural) == [
        "annotation_removed",
        "class_renamed",
        "class_renamed",
        "restriction_added",
    ]


def test_era_renames_export_round_trip(tmp_path):
    from owlcompare.rename_mapping import dump
    from owlcompare.rename_mapping import load as load_mapping

    result = _run_ren("era_renames_v1.ttl", "era_renames_v2.ttl")
    path = tmp_path / "m.toml"
    dump(result, path)
    mapping = load_mapping(path)
    rerun = orchestrator.run(
        _canon_ren("era_renames_v1.ttl"),
        _canon_ren("era_renames_v2.ttl"),
        rename_mapping=mapping,
        rename_min_confidence="certain",
    )
    renamed = [c for c in rerun.changes if c.kind.endswith("_renamed")]
    assert len(renamed) == 3
    assert all(c.details["confidence"] == "certain" for c in renamed)


def test_simple_rename_fixture_now_no_phantom_changes():
    # Regression: Component 12's re-diff introduces no new changes for a pure rename.
    result = _run_ren("simple_class_rename_v1.ttl", "simple_class_rename_v2.ttl")
    structural = [c for c in result.changes if c.layer == "structural"]
    assert sorted(c.kind for c in structural) == ["class_renamed"]


def test_reparent_with_new_restriction_fixture_upgrades_severity():
    # era:Track is reparented (a generalization Component 07 alone rates
    # non_breaking) and simultaneously gains a restriction; Rule 5 upgrades the
    # combined change to breaking.
    result = _run_sev("reparent_with_restriction_v1.ttl", "reparent_with_restriction_v2.ttl")
    reparent = next(c for c in result.changes if c.kind == "class_reparented")
    assert reparent.severity == "breaking"
    refs = [
        r
        for r in result.metadata["severity_refinements"]
        if r.change_id == reparent.details["change_id"]
    ]
    assert len(refs) == 1
    assert refs[0].rule_id == "reparent-with-new-restriction"
    assert refs[0].original_severity == "non_breaking"


# --------------------------------------------------------------------------- #
# Markdown report end-to-end (Component 15)
# --------------------------------------------------------------------------- #

MARKDOWN_GOLDEN = FIXTURES / "markdown"
RENAME = FIXTURES / "rename"


def _markdown_result(name_a: str, name_b: str, base: Path):
    # Override the snapshot source to the bare basename so the rendered
    # "Compared A against B" line — and therefore the golden — is independent of
    # the absolute fixture path on the running machine.
    a = replace(load(str(base / name_a)), source=name_a)
    b = replace(load(str(base / name_b)), source=name_b)
    return orchestrator.run(a, b)


def _golden(name: str) -> str:
    return (MARKDOWN_GOLDEN / name).read_text(encoding="utf-8").rstrip("\n")


def test_era_evolution_markdown_output_matches_golden():
    from owlcompare.report.markdown_report import render

    result = _markdown_result("era_evolution_v1.ttl", "era_evolution_v2.ttl", DIFF)
    assert render(result) == _golden("era_evolution.md")


def test_era_renames_markdown_output_matches_golden():
    from owlcompare.report.markdown_report import render

    result = _markdown_result("era_renames_v1.ttl", "era_renames_v2.ttl", RENAME)
    assert render(result) == _golden("era_renames.md")
