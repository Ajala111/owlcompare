"""User-supplied IRI rename map loaded from a TOML file (Component 11).

The rename detector (:mod:`owlcompare.diff.rename`) consults this mapping *before*
any heuristic: a user-asserted ``old → new`` pairing is the highest-confidence
("certain") signal and overrides label/fingerprint matching. The format is
deliberately small — an array-of-tables per entity kind, each entry carrying the
full ``old`` and ``new`` IRI strings. See ``specs/11-rename-detection.md``
§ Rename mapping file format.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exceptions import RenameMappingError

if TYPE_CHECKING:
    from .diff._common import DiffResult

logger = logging.getLogger(__name__)

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

# Entity kind (RenameCandidate.entity_kind) -> the RenameMapping field it exports
# to. Mirrors the section names above; kept separate so an unknown kind is simply
# skipped rather than crashing the export.
_KIND_TO_FIELD: dict[str, str] = {
    "class": "classes",
    "object_property": "object_properties",
    "data_property": "data_properties",
    "annotation_property": "annotation_properties",
}

# Confidence tiers exported by default. ``medium`` is opt-in (it may be wrong;
# the user should review it first — Component 12 § Part B).
_DEFAULT_EXPORT_CONFIDENCES: frozenset[str] = frozenset({"certain", "high"})


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


def dump(
    mapping_or_diff_result: RenameMapping | DiffResult,
    path: Path,
    *,
    include_medium: bool = False,
) -> None:
    """Write a :class:`RenameMapping` or a ``DiffResult`` to ``path`` as TOML.

    Accepts either a :class:`RenameMapping` directly (programmatic export, written
    verbatim) or a ``DiffResult`` (the typical CLI path), in which case a mapping
    is built from ``result.metadata['renames_applied']``. Only ``certain`` and
    ``high`` confidence renames are exported unless ``include_medium`` is set. The
    output is sorted by ``old`` IRI for stable diffs and is loadable by
    :func:`load`. Component 12 § Part B.

    Args:
        mapping_or_diff_result: The mapping to export, or a diff result to derive
            one from.
        path: Destination file (created or overwritten silently).
        include_medium: Also export ``medium`` confidence renames (only meaningful
            for the ``DiffResult`` form).

    Raises:
        RenameMappingError: with exit code 5 if the file cannot be written.
    """
    if isinstance(mapping_or_diff_result, RenameMapping):
        mapping = mapping_or_diff_result
    else:
        mapping = _mapping_from_result(mapping_or_diff_result, include_medium=include_medium)
    _write_toml(mapping, path)


def _mapping_from_result(result: DiffResult, *, include_medium: bool) -> RenameMapping:
    """Build a :class:`RenameMapping` from a diff result's accepted renames."""
    accepted = set(_DEFAULT_EXPORT_CONFIDENCES) | ({"medium"} if include_medium else set())
    collected: dict[str, list[tuple[str, str]]] = {field: [] for field in _SECTIONS.values()}
    for candidate in result.metadata.get("renames_applied", ()):
        if candidate.confidence not in accepted:
            continue
        field = _KIND_TO_FIELD.get(candidate.entity_kind)
        if field is not None:
            collected[field].append((candidate.removed_iri, candidate.added_iri))
    return RenameMapping(
        classes=tuple(sorted(collected["classes"])),
        object_properties=tuple(sorted(collected["object_properties"])),
        data_properties=tuple(sorted(collected["data_properties"])),
        annotation_properties=tuple(sorted(collected["annotation_properties"])),
    )


def _write_toml(mapping: RenameMapping, path: Path) -> None:
    """Serialize ``mapping`` to TOML at ``path`` (no comments — Q3)."""
    sections = (
        ("classes", mapping.classes),
        ("object_properties", mapping.object_properties),
        ("data_properties", mapping.data_properties),
        ("annotation_properties", mapping.annotation_properties),
    )
    lines = [f"schema_version = {_SUPPORTED_SCHEMA_VERSION}"]
    total = 0
    for section, pairs in sections:
        for old, new in sorted(pairs):
            total += 1
            lines.append("")
            lines.append(f"[[{section}]]")
            lines.append(f'old = "{_escape(old)}"')
            lines.append(f'new = "{_escape(new)}"')
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        raise RenameMappingError(
            f"could not write rename mapping to {path}: {exc}", exit_code=5
        ) from exc
    if total == 0:
        logger.info("wrote empty rename mapping to %s (no renames to export)", path)


def _escape(value: str) -> str:
    """Escape a string for a TOML basic (double-quoted) string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
