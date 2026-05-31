"""Acceptance tests for Layer 0 syntactic diff — specs/05-syntactic-diff.md."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import rdflib
from rdflib import RDF, RDFS

from owlcompare.canonicalize import canonicalize
from owlcompare.diff import syntactic
from owlcompare.exceptions import DiffError
from owlcompare.loader import load
from owlcompare.model import EntityIndex, OntologyMetadata, OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIFF_FIXTURES = FIXTURES / "diff"

_RDF_TYPE = str(RDF.type)
_SUBCLASS = str(RDFS.subClassOf)
_LABEL = str(RDFS.label)


def _canon(name: str):
    """Load and canonicalize a fixture by file name."""
    return canonicalize(load(str(DIFF_FIXTURES / name)))


def _load_only(name: str):
    """Load a fixture without canonicalizing (canonical=False)."""
    return load(str(DIFF_FIXTURES / name))


def _empty_canonical() -> OntologySnapshot:
    """An already-canonical snapshot with zero triples.

    The loader rejects empty inputs (raises LoadError), so the empty-ontology
    edge cases build the snapshot directly instead of through a fixture file.
    """
    metadata = OntologyMetadata(
        iri=None,
        version_iri=None,
        imports=(),
        labels=(),
        comments=(),
        version_info=None,
        prior_version=None,
        other_annotations=(),
    )
    index = EntityIndex(
        classes={},
        object_properties={},
        data_properties={},
        annotation_properties={},
        individuals={},
        datatypes={},
    )
    snapshot = OntologySnapshot(
        metadata=metadata,
        entities=index,
        graph=rdflib.Graph(bind_namespaces="none"),
        prefixes={},
        source="<empty>",
        format="turtle",
    )
    return replace(snapshot, canonical=True)


def _find(changes, *, predicate_iri, object_substr=None, kind=None):
    matches = [c for c in changes if c.details.get("predicate_iri") == predicate_iri]
    if object_substr is not None:
        matches = [c for c in matches if object_substr in c.details["object"]]
    if kind is not None:
        matches = [c for c in matches if c.kind == kind]
    return matches


def test_diff_raises_if_inputs_not_canonical():
    a = _load_only("added_class_before.ttl")
    b = _load_only("added_class_after.ttl")
    with pytest.raises(DiffError):
        syntactic.diff(a, b)


def test_diff_raises_if_inputs_not_canonical_exit_code():
    assert DiffError("x").exit_code == 4


def test_diff_identical_canonical_inputs_returns_empty():
    a = _canon("added_class_before.ttl")
    b = _canon("added_class_before.ttl")
    assert syntactic.diff(a, b) == []


def test_diff_equivalent_inputs_different_serialization_returns_empty():
    a = _canon("identical_a.ttl")
    b = _canon("identical_b.ttl")
    assert syntactic.diff(a, b) == []


def test_diff_added_class_produces_added_changes():
    changes = syntactic.diff(_canon("added_class_before.ttl"), _canon("added_class_after.ttl"))
    assert changes
    assert all(c.kind == "triple_added" for c in changes)


def test_diff_removed_class_produces_removed_changes():
    changes = syntactic.diff(_canon("removed_class_before.ttl"), _canon("removed_class_after.ttl"))
    assert changes
    assert all(c.kind == "triple_removed" for c in changes)


def test_diff_change_count_matches_triple_count_added():
    a = _canon("added_class_before.ttl")
    b = _canon("added_class_after.ttl")
    expected = len(set(b.graph) - set(a.graph))
    changes = syntactic.diff(a, b)
    assert len([c for c in changes if c.kind == "triple_added"]) == expected


def test_diff_change_count_matches_triple_count_removed():
    a = _canon("removed_class_before.ttl")
    b = _canon("removed_class_after.ttl")
    expected = len(set(a.graph) - set(b.graph))
    changes = syntactic.diff(a, b)
    assert len([c for c in changes if c.kind == "triple_removed"]) == expected


def test_diff_all_changes_have_layer_syntactic():
    changes = syntactic.diff(_canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl"))
    assert changes
    assert all(c.layer == "syntactic" for c in changes)


def test_diff_removed_change_has_correct_kind_and_severity():
    changes = syntactic.diff(_canon("renamed_label_before.ttl"), _canon("renamed_label_after.ttl"))
    removed = _find(changes, predicate_iri=_LABEL, object_substr="Widget", kind="triple_removed")
    assert len(removed) == 1
    assert removed[0].severity == "info"


def test_diff_added_change_has_correct_kind_and_severity():
    changes = syntactic.diff(_canon("renamed_label_before.ttl"), _canon("renamed_label_after.ttl"))
    added = _find(changes, predicate_iri=_LABEL, object_substr="Gadget", kind="triple_added")
    assert len(added) == 1
    assert added[0].severity == "info"


def test_diff_rdf_type_removed_is_breaking():
    changes = syntactic.diff(_canon("removed_class_before.ttl"), _canon("removed_class_after.ttl"))
    removed_types = _find(changes, predicate_iri=_RDF_TYPE, kind="triple_removed")
    assert removed_types
    assert all(c.severity == "breaking" for c in removed_types)


def test_diff_rdf_type_added_is_additive():
    changes = syntactic.diff(_canon("added_class_before.ttl"), _canon("added_class_after.ttl"))
    added_types = _find(changes, predicate_iri=_RDF_TYPE, kind="triple_added")
    assert added_types
    assert all(c.severity == "additive" for c in added_types)


def test_diff_subclass_removed_is_breaking():
    changes = syntactic.diff(_canon("removed_class_before.ttl"), _canon("removed_class_after.ttl"))
    removed_subclass = _find(changes, predicate_iri=_SUBCLASS, kind="triple_removed")
    assert removed_subclass
    assert all(c.severity == "breaking" for c in removed_subclass)


def test_diff_label_changed_produces_one_removed_one_added_both_info():
    changes = syntactic.diff(_canon("renamed_label_before.ttl"), _canon("renamed_label_after.ttl"))
    assert len(changes) == 2
    assert {c.kind for c in changes} == {"triple_removed", "triple_added"}
    assert all(c.severity == "info" for c in changes)


def test_diff_subject_iri_extracted_for_uri_subject():
    changes = syntactic.diff(_canon("added_class_before.ttl"), _canon("added_class_after.ttl"))
    typed = _find(changes, predicate_iri=_RDF_TYPE, kind="triple_added")
    assert typed
    assert typed[0].subject == "http://example.org/Dog"
    assert typed[0].details["subject_iri"] == "http://example.org/Dog"


def test_diff_subject_none_for_blank_node_subject(tmp_path: Path):
    # An untyped blank node survives canonicalization as a blank node (it is
    # neither a class expression nor an RDF list), so its triples have a
    # blank-node subject -> Change.subject is None.
    src = tmp_path / "bnode.ttl"
    src.write_text(
        '@prefix ex: <http://example.org/> .\nex:Foo ex:bar [ ex:baz "x" ] .\n',
        encoding="utf-8",
    )
    populated = canonicalize(load(str(src)))
    empty = _empty_canonical()
    changes = syntactic.diff(empty, populated)
    bnode_changes = [c for c in changes if c.details["subject"].startswith("_:")]
    assert bnode_changes
    assert all(c.subject is None for c in bnode_changes)


def test_diff_ordering_is_deterministic():
    a = _canon("era_evolution_v1.ttl")
    b = _canon("era_evolution_v2.ttl")
    first = syntactic.diff(a, b)
    second = syntactic.diff(_canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl"))
    assert first == second
    assert [c.summary for c in first] == [c.summary for c in second]


def test_diff_ordering_removed_before_added():
    changes = syntactic.diff(_canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl"))
    kinds = [c.kind for c in changes]
    last_removed = max(i for i, k in enumerate(kinds) if k == "triple_removed")
    first_added = min(i for i, k in enumerate(kinds) if k == "triple_added")
    assert last_removed < first_added


def test_diff_summary_uses_prefixed_form_when_namespace_known():
    changes = syntactic.diff(_canon("added_class_before.ttl"), _canon("added_class_after.ttl"))
    typed = _find(changes, predicate_iri=_RDF_TYPE, kind="triple_added")[0]
    assert "ex:Dog" in typed.summary
    assert "http://example.org/Dog" not in typed.summary


def test_diff_details_contains_n3_terms():
    changes = syntactic.diff(_canon("added_class_before.ttl"), _canon("added_class_after.ttl"))
    change = changes[0]
    expected_keys = {"subject", "predicate", "object", "subject_iri", "predicate_iri"}
    assert set(change.details) >= expected_keys
    # The subject ex:Dog is in a declared namespace, so its n3 form is prefixed.
    assert change.details["subject"] == "ex:Dog"
    # rdfs:label is the only label-bearing triple; rdfs is declared, so prefixed.
    labels = _find(changes, predicate_iri=_LABEL, kind="triple_added")
    assert labels[0].details["predicate"] == "rdfs:label"


def test_diff_details_contains_iri_when_uri():
    changes = syntactic.diff(_canon("added_class_before.ttl"), _canon("added_class_after.ttl"))
    typed = _find(changes, predicate_iri=_RDF_TYPE, kind="triple_added")[0]
    assert typed.details["subject_iri"] == "http://example.org/Dog"
    assert typed.details["predicate_iri"] == _RDF_TYPE


def test_diff_handles_one_empty_one_populated():
    empty = _empty_canonical()
    populated = _canon("added_class_after.ttl")
    changes = syntactic.diff(empty, populated)
    assert changes
    assert all(c.kind == "triple_added" for c in changes)
    assert len(changes) == len(set(populated.graph))


def test_diff_handles_both_empty():
    assert syntactic.diff(_empty_canonical(), _empty_canonical()) == []


def test_diff_same_object_fast_path():
    snapshot = _canon("era_evolution_v1.ttl")
    assert syntactic.diff(snapshot, snapshot) == []


_RESTRICTION_URN_PREFIX = "urn:owlcompare:restriction:"


def _restriction_changes(changes):
    """Changes whose subject is a synthetic restriction URN."""
    return [c for c in changes if (c.subject or "").startswith(_RESTRICTION_URN_PREFIX)]


def test_summary_shortens_synthetic_restriction_urns():
    changes = syntactic.diff(_canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl"))
    restriction_changes = _restriction_changes(changes)
    assert restriction_changes
    for change in restriction_changes:
        assert "_restriction:" in change.summary
        # The full 64-hex hash must not leak into the human-facing summary.
        assert _RESTRICTION_URN_PREFIX not in change.summary
        full_hash = change.subject.removeprefix(_RESTRICTION_URN_PREFIX)
        assert full_hash not in change.summary


def test_details_preserves_full_restriction_urn():
    changes = syntactic.diff(_canon("era_evolution_v1.ttl"), _canon("era_evolution_v2.ttl"))
    restriction_changes = _restriction_changes(changes)
    assert restriction_changes
    for change in restriction_changes:
        # The model keeps the full URN for Layer 1 and machine consumers.
        assert change.details["subject_iri"].startswith(_RESTRICTION_URN_PREFIX)
        assert len(change.details["subject_iri"]) == len(_RESTRICTION_URN_PREFIX) + 64
