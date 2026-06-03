"""User-supplied IRI rename map loaded from a TOML file (Component 11).

The rename detector (:mod:`owlcompare.diff.rename`) consults this mapping *before*
any heuristic: a user-asserted ``old → new`` pairing is the highest-confidence
("certain") signal and overrides label/fingerprint matching. The format is
deliberately small — an array-of-tables per entity kind, each entry carrying the
full ``old`` and ``new`` IRI strings. See ``specs/11-rename-detection.md``
§ Rename mapping file format.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import RenameMappingError

# Only schema 1 exists. Unknown versions are rejected so a future v2 mapping can
# never be silently mis-parsed by an old reader (mirrors severity_config).
_SUPPORTED_SCHEMA_VERSION = 1

# TOML section name -> the RenameMapping field that collects its (old, new) pairs.
_SECTIONS: dict[str, str] = {
    "classes": "classes",
    "object_properties": "object_properties",
    "data_properties": "data_properties",
    "annotation_properties": "annotation_properties",
}


@dataclass(frozen=True, slots=True)
class RenameMapping:
    """User-supplied IRI rename map (one ``(old_iri, new_iri)`` tuple per rename)."""

    classes: tuple[tuple[str, str], ...] = ()
    object_properties: tuple[tuple[str, str], ...] = ()
    data_properties: tuple[tuple[str, str], ...] = ()
    annotation_properties: tuple[tuple[str, str], ...] = ()
    schema_version: int = 1


def empty() -> RenameMapping:
    """Return an empty mapping (no user-supplied renames). The default."""
    return RenameMapping()


def load(path: Path) -> RenameMapping:
    """Load and validate a TOML rename mapping file.

    Args:
        path: Filesystem path to the ``.toml`` mapping.

    Returns:
        The parsed :class:`RenameMapping`.

    Raises:
        RenameMappingError: with exit code 2 if the file does not exist (a usage
            error — wrong path), or exit code 6 for malformed TOML, an unknown
            ``schema_version``, or a malformed entry (missing ``old``/``new``).
    """
    if not path.exists():
        raise RenameMappingError(f"rename mapping file not found: {path}", exit_code=2)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise RenameMappingError(f"malformed rename mapping TOML ({path}): {exc}") from exc

    schema_version = data.get("schema_version", _SUPPORTED_SCHEMA_VERSION)
    if schema_version != _SUPPORTED_SCHEMA_VERSION:
        raise RenameMappingError(
            f"unsupported rename mapping schema_version {schema_version!r}; "
            f"this build supports {_SUPPORTED_SCHEMA_VERSION}"
        )

    parsed: dict[str, tuple[tuple[str, str], ...]] = {}
    for section, field_name in _SECTIONS.items():
        entries = data.get(section, [])
        parsed[field_name] = tuple(_parse_entry(section, item) for item in entries)

    return RenameMapping(
        classes=parsed["classes"],
        object_properties=parsed["object_properties"],
        data_properties=parsed["data_properties"],
        annotation_properties=parsed["annotation_properties"],
        schema_version=_SUPPORTED_SCHEMA_VERSION,
    )


def _parse_entry(section: str, item: dict[str, Any]) -> tuple[str, str]:
    """Validate one ``[[section]]`` table into an ``(old, new)`` IRI pair."""
    old = item.get("old")
    new = item.get("new")
    if not old or not new:
        raise RenameMappingError(
            f"each [[{section}]] entry requires both 'old' and 'new' IRI strings"
        )
    return str(old), str(new)
