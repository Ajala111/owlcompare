"""Acceptance tests for owlcompare.loader — specs/02-loader.md."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from owlcompare.exceptions import LoadError
from owlcompare.loader import load
from owlcompare.model import LoadOptions

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_load_minimal_class_fixture_succeeds():
    snap = load(FIXTURES / "minimal_class.ttl")
    assert snap.metadata.iri == "http://example.org/minimal"
    assert snap.format == "turtle"


def test_load_minimal_class_indexes_one_class_one_property_one_individual():
    snap = load(FIXTURES / "minimal_class.ttl")
    counts = snap.entities.counts()
    assert counts["class"] == 1
    assert counts["object_property"] == 1
    assert counts["individual"] == 1
    assert "http://example.org/minimal#Thing" in snap.entities.classes
    assert "http://example.org/minimal#hasFriend" in snap.entities.object_properties
    assert "http://example.org/minimal#alice" in snap.entities.individuals


def test_load_with_metadata_captures_version_iri():
    snap = load(FIXTURES / "with_metadata.ttl")
    assert snap.metadata.version_iri == "http://example.org/meta/2.0.0"
    assert snap.metadata.version_info == "2.0.0"
    assert snap.metadata.prior_version == "http://example.org/meta/1.0.0"


def test_load_with_metadata_captures_imports():
    snap = load(FIXTURES / "with_metadata.ttl")
    assert set(snap.metadata.imports) == {
        "http://www.w3.org/2004/02/skos/core",
        "http://purl.org/dc/terms/",
    }


def test_load_with_metadata_captures_multilingual_labels():
    snap = load(FIXTURES / "with_metadata.ttl")
    labels_by_lang = dict(snap.metadata.labels)
    assert labels_by_lang["en"] == "Metadata Ontology"
    assert labels_by_lang["fr"] == "Ontologie de métadonnées"


def test_load_punned_iri_appears_under_multiple_kinds():
    snap = load(FIXTURES / "punned.ttl")
    iri = "http://example.org/punned#Eagle"
    kinds = set(snap.entities.kinds_of(iri))
    assert {"class", "individual"} <= kinds
    assert iri in snap.entities.classes
    assert iri in snap.entities.individuals


def test_load_multilingual_labels_preserved_with_language_tags():
    snap = load(FIXTURES / "multilingual.ttl")
    house = snap.entities.classes["http://example.org/ml#House"]
    labels_by_lang = dict(house.labels)
    assert labels_by_lang["en"] == "House"
    assert labels_by_lang["fr"] == "Maison"
    assert labels_by_lang["de"] == "Haus"


def test_load_deprecated_entity_has_is_deprecated_true():
    snap = load(FIXTURES / "deprecated.ttl")
    old = snap.entities.classes["http://example.org/dep#OldThing"]
    new = snap.entities.classes["http://example.org/dep#NewThing"]
    assert old.is_deprecated is True
    assert new.is_deprecated is False


def test_load_era_micro_indexes_expected_entities():
    snap = load(FIXTURES / "era_micro.ttl")
    assert snap.metadata.iri == "http://data.europa.eu/949/ontology"
    assert snap.metadata.version_iri == "http://data.europa.eu/949/ontology/3.2.0"
    iris = snap.entities.all_iris()
    assert "http://data.europa.eu/949/Track" in iris
    assert "http://data.europa.eu/949/BaliseGroup" in iris
    assert "http://data.europa.eu/949/Balise" in iris
    assert "http://data.europa.eu/949/locatedOn" in snap.entities.object_properties
    assert "http://data.europa.eu/949/kilometricPoint" in snap.entities.data_properties


def test_load_broken_turtle_raises_load_error():
    with pytest.raises(LoadError) as info:
        load(FIXTURES / "broken.ttl")
    assert "parse" in str(info.value).lower()


def test_load_empty_file_raises_load_error(tmp_path: Path):
    empty = tmp_path / "empty.ttl"
    empty.write_text("")
    with pytest.raises(LoadError) as info:
        load(empty)
    assert "no triples" in str(info.value).lower()


def test_load_missing_file_raises_load_error_exit_code_3(tmp_path: Path):
    with pytest.raises(LoadError) as info:
        load(tmp_path / "absent.ttl")
    assert info.value.exit_code == 3


def test_load_directory_path_raises_load_error(tmp_path: Path):
    with pytest.raises(LoadError) as info:
        load(tmp_path)
    assert info.value.exit_code == 3
    assert "directory" in str(info.value).lower()


def test_load_unknown_format_hint_raises_load_error_exit_code_2(tmp_path: Path):
    path = tmp_path / "x.ttl"
    path.write_text("@prefix : <http://example.org/> .\n:Thing a :Class .\n")
    with pytest.raises(LoadError) as info:
        load(path, LoadOptions(format_hint="madeup"))
    assert info.value.exit_code == 2
    assert "unsupported format hint" in str(info.value).lower()


_NO_ONTOLOGY_TURTLE = (
    "@prefix : <http://example.org/no-onto#> .\n"
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    ":A a owl:Class .\n"
)


def test_load_no_owl_ontology_declaration_warns_not_strict(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    path = tmp_path / "no_ontology.ttl"
    path.write_text(_NO_ONTOLOGY_TURTLE)
    with caplog.at_level(logging.INFO, logger="owlcompare.loader"):
        snap = load(path)
    assert snap.metadata.iri is None
    assert any("No owl:Ontology declaration" in r.getMessage() for r in caplog.records)


def test_load_no_owl_ontology_declaration_strict_raises(tmp_path: Path):
    path = tmp_path / "no_ontology.ttl"
    path.write_text(_NO_ONTOLOGY_TURTLE)
    with pytest.raises(LoadError) as info:
        load(path, LoadOptions(strict=True))
    assert "no owl:ontology" in str(info.value).lower()


def test_load_captures_prefixes_from_turtle():
    snap = load(FIXTURES / "with_metadata.ttl")
    # Only prefixes declared in the source — no rdflib core/rdflib auto-bindings.
    assert snap.prefixes == {
        "": "http://example.org/meta#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }


def test_load_prefixes_exclude_rdflib_auto_bindings():
    # era_micro.ttl declares era/owl/rdfs only; nothing else should appear.
    snap = load(FIXTURES / "era_micro.ttl")
    assert set(snap.prefixes) == {"era", "owl", "rdfs"}
    assert "brick" not in snap.prefixes
    assert "csvw" not in snap.prefixes
    assert "dcat" not in snap.prefixes


def test_load_format_autodetect_from_extension(tmp_path: Path):
    path = tmp_path / "minimal.ttl"
    path.write_text(
        "@prefix : <http://example.org/x#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        ":A a owl:Class .\n"
    )
    snap = load(path)
    assert snap.format == "turtle"


def test_load_with_format_hint_overrides_extension(tmp_path: Path):
    # ``.ttl`` extension but the body is N-Triples — only the explicit
    # ``format_hint="nt"`` lets rdflib parse it successfully.
    path = tmp_path / "lying.ttl"
    path.write_text(
        "<http://example.org/A> "
        "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
        "<http://www.w3.org/2002/07/owl#Class> .\n"
    )
    snap = load(path, LoadOptions(format_hint="nt"))
    assert snap.format == "n-triples"
    assert "http://example.org/A" in snap.entities.classes
