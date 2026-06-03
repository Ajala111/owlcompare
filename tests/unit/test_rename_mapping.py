"""Unit tests for the rename mapping loader — specs/11-rename-detection.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.exceptions import RenameMappingError
from owlcompare.rename_mapping import RenameMapping, empty, load

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
