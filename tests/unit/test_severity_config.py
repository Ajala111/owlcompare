"""Acceptance tests for the severity config loader — specs/10-severity.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from owlcompare.diff._common import Change
from owlcompare.exceptions import SeverityConfigError
from owlcompare.severity_config import (
    SeverityOverride,
    empty,
    load,
    matches,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "severity"


def _change(kind: str, *, layer: str = "structural", subject: str | None = None) -> Change:
    return Change(
        layer=layer,  # type: ignore[arg-type]
        kind=kind,
        severity="breaking",
        subject=subject,
        summary=f"{kind} on {subject}",
        details={},
    )


def test_load_valid_config_returns_parsed_overrides():
    config = load(FIXTURES / "valid_config.toml")
    assert config.schema_version == 1
    assert len(config.overrides) == 4
    first = config.overrides[0]
    assert first.kind_pattern == "annotation_*"
    assert first.severity == "info"
    # The layer-filtered override is parsed with its exact-match layer.
    layered = [o for o in config.overrides if o.layer is not None]
    assert layered and layered[0].layer == "structural"


def test_load_missing_file_raises_severity_config_error_exit_code_2():
    with pytest.raises(SeverityConfigError) as exc:
        load(FIXTURES / "does_not_exist.toml")
    assert exc.value.exit_code == 2


def test_load_malformed_toml_raises_severity_config_error_exit_code_6():
    with pytest.raises(SeverityConfigError) as exc:
        load(FIXTURES / "malformed.toml")
    assert exc.value.exit_code == 6


def test_load_unknown_schema_version_raises():
    with pytest.raises(SeverityConfigError, match="schema_version"):
        load(FIXTURES / "unknown_version.toml")


def test_load_unknown_severity_value_raises():
    with pytest.raises(SeverityConfigError, match="invalid severity"):
        load(FIXTURES / "unknown_severity.toml")


def test_load_missing_kind_pattern_raises():
    with pytest.raises(SeverityConfigError, match="kind_pattern"):
        load(FIXTURES / "missing_kind.toml")


def test_empty_config_has_no_overrides():
    assert empty().overrides == ()


def test_override_pattern_matching_glob_kind_only():
    override = SeverityOverride(kind_pattern="annotation_*", severity="info")
    assert matches(_change("annotation_changed"), override)
    assert matches(_change("annotation_added"), override)
    assert not matches(_change("class_added"), override)


def test_override_pattern_matching_glob_subject_too():
    override = SeverityOverride(
        kind_pattern="restriction_*",
        subject_pattern="*LegacyTrack*",
        severity="info",
    )
    yes = _change("restriction_removed", subject="http://data.europa.eu/949/LegacyTrack")
    no = _change("restriction_removed", subject="http://data.europa.eu/949/Track")
    assert matches(yes, override)
    assert not matches(no, override)
    # A subject_pattern never matches a change with no subject.
    assert not matches(_change("restriction_removed", subject=None), override)


def test_override_pattern_matching_layer_filter():
    override = SeverityOverride(kind_pattern="*_removed", layer="structural", severity="breaking")
    assert matches(_change("class_removed", layer="structural"), override)
    assert not matches(_change("triple_removed", layer="syntactic"), override)


def test_override_pattern_no_match_returns_false():
    override = SeverityOverride(kind_pattern="class_reparented", severity="breaking")
    assert not matches(_change("class_added"), override)
