"""User-supplied severity overrides loaded from a TOML config (Component 10).

The severity classifier (:mod:`owlcompare.diff.severity`) applies these overrides
*before* any built-in cross-cutting rule, so a project can force its own severity
conventions ("all annotation changes are info"; "any class reparent is breaking
for us") and even change the CLI exit code by doing so. The format is deliberately
small and glob-based — no regex, which is a footgun in user config. See
``specs/10-severity.md`` § Severity config file format.
"""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_args

from .diff._common import Change, Severity
from .exceptions import SeverityConfigError

# The valid severity literals, derived from the single source of truth in
# ``_common.Severity`` so this never drifts from the type.
_VALID_SEVERITIES: frozenset[str] = frozenset(get_args(Severity))

# Only schema 1 exists. Unknown versions are rejected so a future v2 config can
# never be silently mis-parsed by an old reader.
_SUPPORTED_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SeverityOverride:
    """A user-supplied rule to force a specific severity for matching changes."""

    kind_pattern: str  # e.g., 'annotation_changed' or 'annotation_*' (glob)
    layer: str | None = None  # optional exact filter: 'syntactic' or 'structural'
    subject_pattern: str | None = None  # optional glob on the full subject IRI
    severity: Severity = "info"


@dataclass(frozen=True, slots=True)
class SeverityConfig:
    """Top-level severity config loaded from TOML."""

    overrides: tuple[SeverityOverride, ...] = ()
    schema_version: int = 1


def empty() -> SeverityConfig:
    """Return an empty config (no overrides). The default when none is supplied."""
    return SeverityConfig()


def load(path: Path) -> SeverityConfig:
    """Load and validate a TOML severity config.

    Args:
        path: Filesystem path to the ``.toml`` config.

    Returns:
        The parsed :class:`SeverityConfig`.

    Raises:
        SeverityConfigError: with exit code 2 if the file does not exist (a usage
            error — wrong path), or exit code 6 for malformed TOML, an unknown
            ``schema_version``, an unknown severity value, or an override missing
            its required ``kind_pattern``.
    """
    if not path.exists():
        raise SeverityConfigError(f"severity config file not found: {path}", exit_code=2)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise SeverityConfigError(f"malformed severity config TOML ({path}): {exc}") from exc

    schema_version = data.get("schema_version", _SUPPORTED_SCHEMA_VERSION)
    if schema_version != _SUPPORTED_SCHEMA_VERSION:
        raise SeverityConfigError(
            f"unsupported severity config schema_version {schema_version!r}; "
            f"this build supports {_SUPPORTED_SCHEMA_VERSION}"
        )

    raw_overrides = data.get("overrides", [])
    overrides = tuple(_parse_override(item) for item in raw_overrides)
    return SeverityConfig(overrides=overrides, schema_version=_SUPPORTED_SCHEMA_VERSION)


def _parse_override(item: dict[str, Any]) -> SeverityOverride:
    """Validate one ``[[overrides]]`` table into a :class:`SeverityOverride`."""
    kind_pattern = item.get("kind_pattern")
    if not kind_pattern:
        raise SeverityConfigError("each [[overrides]] entry requires a 'kind_pattern'")
    severity = item.get("severity", "info")
    if severity not in _VALID_SEVERITIES:
        raise SeverityConfigError(
            f"invalid severity {severity!r}; valid values are: "
            + ", ".join(sorted(_VALID_SEVERITIES))
        )
    return SeverityOverride(
        kind_pattern=str(kind_pattern),
        layer=item.get("layer"),
        subject_pattern=item.get("subject_pattern"),
        severity=severity,
    )


def matches(change: Change, override: SeverityOverride) -> bool:
    """Whether ``change`` satisfies *all* conditions of ``override``.

    ``kind_pattern`` and ``subject_pattern`` are shell globs (``*``/``?``);
    ``layer`` is an exact match. The subject is matched against the full IRI
    (Q1) — a ``subject_pattern`` on a change with no subject never matches.
    """
    if not fnmatch.fnmatch(change.kind, override.kind_pattern):
        return False
    if override.layer is not None and change.layer != override.layer:
        return False
    if override.subject_pattern is not None:
        if change.subject is None:
            return False
        if not fnmatch.fnmatch(change.subject, override.subject_pattern):
            return False
    return True
