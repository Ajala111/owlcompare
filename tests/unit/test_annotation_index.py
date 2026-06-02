"""Acceptance tests for the annotation index — specs/09-structural-annotations.md."""

from __future__ import annotations

from pathlib import Path

from owlcompare.canonicalize import canonicalize
from owlcompare.diff.structural._annotation_index import AnnotationIndex, build
from owlcompare.loader import load
from owlcompare.model import OntologySnapshot

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ANNO = FIXTURES / "diff" / "annotations"

EX = "http://example.org/"
ERA = "http://data.europa.eu/949/"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDFS_SEEALSO = "http://www.w3.org/2000/01/rdf-schema#seeAlso"
OWL_DEPRECATED = "http://www.w3.org/2002/07/owl#deprecated"
OWL_VERSIONINFO = "http://www.w3.org/2002/07/owl#versionInfo"
SKOS_ALTLABEL = "http://www.w3.org/2004/02/skos/core#altLabel"


def _canon(name: str) -> AnnotationIndex:
    return build(canonicalize(load(str(ANNO / name))))


def _load(name: str) -> OntologySnapshot:
    return load(str(ANNO / name))


def test_build_captures_rdfs_label():
    index = _canon("label_changed_same_lang_before.ttl")
    values = index.by_subject[EX + "Track"][RDFS_LABEL]["en"]
    assert [v.value for v in values] == ["Track"]


def test_build_captures_rdfs_comment():
    index = _canon("comment_changed_before.ttl")
    values = index.by_subject[EX + "Track"][RDFS_COMMENT]["en"]
    assert values[0].value == "A length of railway on which trains run."


def test_build_captures_multiple_languages_separately():
    index = _canon("era_annotations_v1.ttl")
    labels = index.by_subject[ERA + "Track"][RDFS_LABEL]
    assert labels["en"][0].value == "Track"
    assert labels["fr"][0].value == "Voie"


def test_build_groups_multivalue_annotations():
    index = _canon("multivalue_altLabel_one_removed_before.ttl")
    values = index.by_subject[EX + "Track"][SKOS_ALTLABEL]["en"]
    assert {v.value for v in values} == {"Rail", "Permanent Way", "Track Bed"}


def test_build_captures_owl_deprecated():
    index = _canon("deprecated_removed_before.ttl")
    values = index.by_subject[EX + "Track"][OWL_DEPRECATED][None]
    assert values[0].value == "true"


def test_build_captures_ontology_annotations_separately():
    index = _canon("ontology_versioninfo_changed_before.ttl")
    predicates = {v.predicate for v in index.ontology_annotations}
    assert OWL_VERSIONINFO in predicates
    # The ontology subject must not leak into the per-entity index.
    assert EX + "ontology" not in index.by_subject


def test_build_skips_restriction_urn_subjects():
    index = _canon("annotation_on_restriction_urn_skipped_before.ttl")
    urn_subjects = [s for s in index.by_subject if s.startswith("urn:owlcompare:")]
    assert urn_subjects == []


def test_build_skips_blank_node_subjects():
    # Load without canonicalization so the blank node is still a BNode subject.
    index = build(_load("blank_node_annotation.ttl"))
    # The anonymous note's label must not appear; only ex:Track is indexed.
    assert set(index.by_subject) == {EX + "Track"}


def test_build_recognizes_user_declared_annotation_property():
    index = _canon("user_declared_annotation.ttl")
    predicates = index.by_subject[EX + "Track"]
    assert EX + "editorialStatus" in predicates


def test_build_captures_iri_valued_annotation():
    index = _canon("iri_valued_annotation_before.ttl")
    value = index.by_subject[EX + "Track"][RDFS_SEEALSO][None][0]
    assert value.is_iri_value is True
    assert value.value == EX + "related"


def test_build_captures_no_language_literal():
    index = _canon("user_declared_annotation.ttl")
    value = index.by_subject[EX + "Track"][EX + "editorialStatus"][None][0]
    assert value.language is None
    assert value.is_iri_value is False
    assert value.value == "approved"
