"""Acceptance tests for Layer 1 entity-level diff — specs/06-structural-entities.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import syntactic
from owlcompare.diff._common import Change
from owlcompare.diff._subsumption import SubsumptionRegistry
from owlcompare.diff.structural import entities
from owlcompare.exceptions import DiffError
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF = FIXTURES / "diff"


def _canon(name: str) -> OntologySnapshot:
    return canonicalize(load(str(DIFF / name)))


def _canon_text(tmp_path: Path, name: str, text: str) -> OntologySnapshot:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return canonicalize(load(str(path)))


def _diff(
    a: OntologySnapshot, b: OntologySnapshot
) -> tuple[list[Change], SubsumptionRegistry, list[Change]]:
    """Run Layer 0 + Layer 1 entities; return (structural, registry, layer0)."""
    registry = SubsumptionRegistry()
    layer0 = syntactic.diff(a, b)
    structural = entities.diff(a, b, layer0, registry)
    return structural, registry, layer0


_PREFIXES = (
    "@prefix ex: <http://example.org/> .\n"
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
)


def test_diff_requires_canonical_inputs():
    a = load(str(DIFF / "class_added_before.ttl"))
    b = load(str(DIFF / "class_added_after.ttl"))
    with pytest.raises(DiffError):
        entities.diff(a, b, [], SubsumptionRegistry())


def test_diff_identical_inputs_returns_empty():
    snap = _canon("class_added_before.ttl")
    structural, _, _ = _diff(snap, snap)
    assert structural == []


def test_diff_class_added_emits_class_added_change():
    structural, _, _ = _diff(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    class_added = [c for c in structural if c.kind == "class_added"]
    assert len(class_added) == 1
    assert class_added[0].subject == "http://example.org/Dog"


def test_diff_class_added_change_severity_is_additive():
    structural, _, _ = _diff(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    assert structural[0].severity == "additive"


def test_diff_class_removed_change_severity_is_breaking():
    structural, _, _ = _diff(_canon("class_removed_before.ttl"), _canon("class_removed_after.ttl"))
    class_removed = [c for c in structural if c.kind == "class_removed"]
    assert len(class_removed) == 1
    assert class_removed[0].severity == "breaking"


def test_diff_class_added_subsumes_rdf_type_triple_added():
    a, b = _canon("class_added_before.ttl"), _canon("class_added_after.ttl")
    _, registry, layer0 = _diff(a, b)
    rdf_type_added = [
        c
        for c in layer0
        if c.subject == "http://example.org/Dog"
        and c.details["predicate_iri"] == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    ]
    assert len(rdf_type_added) == 1
    assert registry.is_explained(rdf_type_added[0].details["change_id"])


def test_diff_class_added_subsumes_rdfs_label_triple_added():
    a, b = _canon("class_added_before.ttl"), _canon("class_added_after.ttl")
    _, registry, layer0 = _diff(a, b)
    label_added = [
        c
        for c in layer0
        if c.subject == "http://example.org/Dog"
        and c.details["predicate_iri"] == "http://www.w3.org/2000/01/rdf-schema#label"
    ]
    assert len(label_added) == 1
    assert registry.is_explained(label_added[0].details["change_id"])


def test_diff_object_property_added_emits_correct_kind():
    structural, _, _ = _diff(
        _canon("property_added_before.ttl"), _canon("property_added_after.ttl")
    )
    kinds = {c.kind for c in structural}
    assert "object_property_added" in kinds


def test_diff_data_property_added_emits_correct_kind():
    structural, _, _ = _diff(
        _canon("property_added_before.ttl"), _canon("property_added_after.ttl")
    )
    kinds = {c.kind for c in structural}
    assert "data_property_added" in kinds


def test_diff_individual_added_severity_is_additive():
    structural, _, _ = _diff(
        _canon("multiple_kinds_added_before.ttl"), _canon("multiple_kinds_added_after.ttl")
    )
    individual_added = [c for c in structural if c.kind == "individual_added"]
    assert len(individual_added) == 1
    assert individual_added[0].severity == "additive"


def test_diff_individual_removed_severity_is_non_breaking():
    structural, _, _ = _diff(
        _canon("punning_resolution_before.ttl"), _canon("punning_resolution_after.ttl")
    )
    individual_removed = [c for c in structural if c.kind == "individual_removed"]
    assert len(individual_removed) == 1
    assert individual_removed[0].severity == "non_breaking"


def test_diff_datatype_added_emits_correct_kind(tmp_path: Path):
    before = _canon_text(tmp_path, "dt_before.ttl", _PREFIXES + "ex:Thing a owl:Class .\n")
    after = _canon_text(
        tmp_path,
        "dt_after.ttl",
        _PREFIXES + "ex:Thing a owl:Class .\nex:MyType a rdfs:Datatype .\n",
    )
    structural, _, _ = _diff(before, after)
    datatype_added = [c for c in structural if c.kind == "datatype_added"]
    assert len(datatype_added) == 1
    assert datatype_added[0].subject == "http://example.org/MyType"


def test_diff_summary_includes_english_label_when_available():
    structural, _, _ = _diff(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    assert structural[0].summary == 'Class added: ex:Dog "Dog"@en'


def test_diff_summary_falls_back_to_any_label_when_no_english(tmp_path: Path):
    before = _canon_text(tmp_path, "fr_before.ttl", _PREFIXES + "ex:Thing a owl:Class .\n")
    after = _canon_text(
        tmp_path,
        "fr_after.ttl",
        _PREFIXES + 'ex:Thing a owl:Class .\nex:Chien a owl:Class ;\n  rdfs:label "Chien"@fr .\n',
    )
    structural, _, _ = _diff(before, after)
    added = [c for c in structural if c.subject == "http://example.org/Chien"]
    assert added[0].summary == 'Class added: ex:Chien "Chien"@fr'


def test_diff_summary_omits_label_when_none(tmp_path: Path):
    before = _canon_text(tmp_path, "nl_before.ttl", _PREFIXES + "ex:Thing a owl:Class .\n")
    after = _canon_text(
        tmp_path, "nl_after.ttl", _PREFIXES + "ex:Thing a owl:Class .\nex:Bare a owl:Class .\n"
    )
    structural, _, _ = _diff(before, after)
    added = [c for c in structural if c.subject == "http://example.org/Bare"]
    assert added[0].summary == "Class added: ex:Bare"


def test_diff_uses_prefixed_iri_when_namespace_known():
    structural, _, _ = _diff(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    assert "ex:Dog" in structural[0].summary
    assert "http://example.org/Dog" not in structural[0].summary


def test_diff_kind_changed_emits_single_entity_kind_changed():
    structural, _, _ = _diff(_canon("kind_changed_before.ttl"), _canon("kind_changed_after.ttl"))
    kind_changed = [c for c in structural if c.kind == "entity_kind_changed"]
    assert len(kind_changed) == 1
    assert kind_changed[0].details["from_kind"] == "class"
    assert kind_changed[0].details["to_kind"] == "individual"


def test_diff_kind_changed_severity_is_breaking():
    structural, _, _ = _diff(_canon("kind_changed_before.ttl"), _canon("kind_changed_after.ttl"))
    assert structural[0].severity == "breaking"


def test_diff_kind_changed_does_not_emit_add_and_remove():
    structural, _, _ = _diff(_canon("kind_changed_before.ttl"), _canon("kind_changed_after.ttl"))
    kinds = [c.kind for c in structural]
    assert "class_removed" not in kinds
    assert "individual_added" not in kinds
    assert kinds == ["entity_kind_changed"]


def test_diff_punning_resolution_emits_individual_removed_only():
    structural, _, _ = _diff(
        _canon("punning_resolution_before.ttl"), _canon("punning_resolution_after.ttl")
    )
    kinds = [c.kind for c in structural]
    assert kinds == ["individual_removed"]
    assert "entity_kind_changed" not in kinds


def test_diff_skips_synthetic_restriction_iris():
    # era_evolution canonicalizes its restrictions into urn:owlcompare:restriction
    # IRIs; those are owl:Restriction, never indexed as entities, so Layer 1 must
    # not emit any change whose subject is synthetic.
    structural, _, _ = _diff(_canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl"))
    assert all(not (c.subject or "").startswith("urn:owlcompare:") for c in structural)


def test_diff_changes_ordered_by_kind_then_subject():
    structural, _, _ = _diff(
        _canon("multiple_kinds_added_before.ttl"), _canon("multiple_kinds_added_after.ttl")
    )
    keys = [(c.kind, c.subject) for c in structural]
    assert keys == sorted(keys)
    assert [c.kind for c in structural] == [
        "class_added",
        "individual_added",
        "object_property_added",
    ]


def test_diff_change_id_present_in_details():
    structural, _, _ = _diff(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    change_id = structural[0].details["change_id"]
    assert change_id.startswith("structural:class_added:")


def test_diff_subsumes_field_populated_when_layer0_matched():
    structural, _, _ = _diff(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    # ex:Dog added with rdf:type + rdfs:label → both subsumed.
    assert len(structural[0].details["subsumes"]) == 2


def test_diff_subsumes_list_is_sorted():
    # DD-021: the subsumes array must be lexicographically sorted at the producer.
    structural, _, _ = _diff(_canon("class_added_before.ttl"), _canon("class_added_after.ttl"))
    subsumes = structural[0].details["subsumes"]
    assert len(subsumes) >= 2  # a meaningful order check needs >1 element
    assert subsumes == sorted(subsumes)


def test_diff_subsumes_empty_when_no_matching_layer0():
    # Defensive: with no Layer 0 changes supplied, the structural change is still
    # emitted and its subsumes list is empty.
    a, b = _canon("class_added_before.ttl"), _canon("class_added_after.ttl")
    registry = SubsumptionRegistry()
    structural = entities.diff(a, b, [], registry)
    assert structural[0].details["subsumes"] == []
