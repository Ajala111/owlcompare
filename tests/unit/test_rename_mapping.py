"""Unit tests for the rename mapping loader and exporter — specs/11 & 12."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from owlcompare.canonicalize import canonicalize
from owlcompare.diff._common import DiffResult
from owlcompare.diff.rename import RenameCandidate
from owlcompare.exceptions import RenameMappingError
from owlcompare.loader import load as load_ontology
from owlcompare.rename_mapping import RenameMapping, dump, empty, load

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "rename"


def _fx(name: str) -> Path:
    return FIXTURES / name


def test_load_valid_mapping_returns_parsed_entries():
    mapping = load(_fx("valid_mapping.toml"))
    assert mapping.classes == (
        ("http://data.europa.eu/949/Track", "http://data.europa.eu/949/RailwayTrack"),
    )
    assert mapping.object_properties == (
        ("http://data.europa.eu/949/locatedOn", "http://data.europa.eu/949/hasLocation"),
    )


def test_load_missing_file_raises_rename_mapping_error_exit_code_2():
    with pytest.raises(RenameMappingError) as exc:
        load(_fx("does_not_exist.toml"))
    assert exc.value.exit_code == 2


def test_load_malformed_toml_raises_exit_code_6():
    with pytest.raises(RenameMappingError) as exc:
        load(_fx("mapping_malformed.toml"))
    assert exc.value.exit_code == 6


def test_load_unknown_schema_version_raises():
    with pytest.raises(RenameMappingError) as exc:
        load(_fx("mapping_unknown_version.toml"))
    assert exc.value.exit_code == 6
    assert "schema_version" in str(exc.value)


def test_empty_mapping_has_no_entries():
    mapping = empty()
    assert mapping == RenameMapping()
    assert mapping.classes == ()
    assert mapping.object_properties == ()
    assert mapping.data_properties == ()
    assert mapping.annotation_properties == ()


def test_load_handles_multiple_classes(tmp_path: Path):
    content = (
        "schema_version = 1\n"
        '[[classes]]\nold = "urn:a"\nnew = "urn:b"\n'
        '[[classes]]\nold = "urn:c"\nnew = "urn:d"\n'
    )
    path = tmp_path / "m.toml"
    path.write_text(content, encoding="utf-8")
    mapping = load(path)
    assert mapping.classes == (("urn:a", "urn:b"), ("urn:c", "urn:d"))


def test_load_handles_multiple_kinds(tmp_path: Path):
    content = (
        "schema_version = 1\n"
        '[[classes]]\nold = "urn:c1"\nnew = "urn:c2"\n'
        '[[object_properties]]\nold = "urn:o1"\nnew = "urn:o2"\n'
        '[[data_properties]]\nold = "urn:d1"\nnew = "urn:d2"\n'
        '[[annotation_properties]]\nold = "urn:a1"\nnew = "urn:a2"\n'
    )
    path = tmp_path / "m.toml"
    path.write_text(content, encoding="utf-8")
    mapping = load(path)
    assert mapping.classes == (("urn:c1", "urn:c2"),)
    assert mapping.object_properties == (("urn:o1", "urn:o2"),)
    assert mapping.data_properties == (("urn:d1", "urn:d2"),)
    assert mapping.annotation_properties == (("urn:a1", "urn:a2"),)


def test_load_entry_missing_new_raises(tmp_path: Path):
    path = tmp_path / "m.toml"
    path.write_text('schema_version = 1\n[[classes]]\nold = "urn:a"\n', encoding="utf-8")
    with pytest.raises(RenameMappingError) as exc:
        load(path)
    assert exc.value.exit_code == 6


# --------------------------------------------------------------------------- #
# Component 12 Part B — dump() / export
# --------------------------------------------------------------------------- #


def _result_with(*candidates: RenameCandidate) -> DiffResult:
    """A minimal DiffResult carrying the given accepted renames in metadata."""
    a = canonicalize(load_ontology(str(_fx("simple_class_rename_v1.ttl"))))
    b = canonicalize(load_ontology(str(_fx("simple_class_rename_v2.ttl"))))
    return DiffResult(a=a, b=b, changes=(), metadata={"renames_applied": candidates})


def _cand(old: str, new: str, kind: str, confidence: str) -> RenameCandidate:
    return RenameCandidate(
        removed_iri=old,
        added_iri=new,
        entity_kind=kind,
        confidence=confidence,
        evidence=(),
        score=1.0,
    )


def test_dump_writes_valid_toml(tmp_path: Path):
    path = tmp_path / "out.toml"
    dump(RenameMapping(classes=(("urn:a", "urn:b"),)), path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["classes"] == [{"old": "urn:a", "new": "urn:b"}]


def test_dump_empty_mapping_writes_schema_version_only(tmp_path: Path):
    path = tmp_path / "out.toml"
    dump(empty(), path)
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {"schema_version": 1}


def test_dump_classes_sorted_by_old_iri(tmp_path: Path):
    path = tmp_path / "out.toml"
    dump(RenameMapping(classes=(("urn:z", "urn:1"), ("urn:a", "urn:2"))), path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert [c["old"] for c in data["classes"]] == ["urn:a", "urn:z"]


def test_dump_properties_sorted_by_old_iri(tmp_path: Path):
    path = tmp_path / "out.toml"
    dump(RenameMapping(object_properties=(("urn:z", "urn:1"), ("urn:a", "urn:2"))), path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert [p["old"] for p in data["object_properties"]] == ["urn:a", "urn:z"]


def test_dump_accepts_renamemapping_directly(tmp_path: Path):
    path = tmp_path / "out.toml"
    dump(RenameMapping(classes=(("urn:a", "urn:b"),)), path)
    assert load(path).classes == (("urn:a", "urn:b"),)


def test_dump_accepts_diffresult_extracts_renames_applied(tmp_path: Path):
    path = tmp_path / "out.toml"
    dump(_result_with(_cand("urn:old", "urn:new", "class", "high")), path)
    assert load(path).classes == (("urn:old", "urn:new"),)


def test_dump_excludes_medium_confidence_by_default(tmp_path: Path):
    path = tmp_path / "out.toml"
    dump(
        _result_with(
            _cand("urn:m_old", "urn:m_new", "class", "medium"),
            _cand("urn:h_old", "urn:h_new", "class", "high"),
        ),
        path,
    )
    classes = load(path).classes
    assert ("urn:h_old", "urn:h_new") in classes
    assert ("urn:m_old", "urn:m_new") not in classes


def test_dump_includes_medium_confidence_when_user_opted_in(tmp_path: Path):
    path = tmp_path / "out.toml"
    dump(
        _result_with(_cand("urn:m_old", "urn:m_new", "class", "medium")), path, include_medium=True
    )
    assert ("urn:m_old", "urn:m_new") in load(path).classes


def test_dump_round_trip(tmp_path: Path):
    path = tmp_path / "out.toml"
    source = RenameMapping(classes=(("urn:a", "urn:b"),), object_properties=(("urn:c", "urn:d"),))
    dump(source, path)
    assert load(path) == source


def test_dump_write_failure_raises_rename_mapping_error_exit_code_5(tmp_path: Path):
    # tmp_path is a directory; writing a file to that path fails.
    with pytest.raises(RenameMappingError) as exc:
        dump(empty(), tmp_path)
    assert exc.value.exit_code == 5
