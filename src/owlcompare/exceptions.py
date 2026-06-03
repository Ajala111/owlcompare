"""Typed exception hierarchy shared across owlcompare.

Library code raises these; the CLI boundary (`cli.main`) catches them and
translates each one's ``exit_code`` into the process exit status. The codes are
canonical and defined in ``specs/01-cli.md``.
"""

from __future__ import annotations


class OwlCompareError(Exception):
    """Base for all owlcompare errors. Carries an ``exit_code`` attribute."""

    exit_code: int = 1


class UsageError(OwlCompareError):
    """User-facing input error (bad CLI args, missing file)."""

    exit_code: int = 2


class LoadError(OwlCompareError):
    """Failure to load or parse an ontology."""

    exit_code: int = 3

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        # Allow per-instance override (e.g., unknown --format hint is a usage
        # error → exit 2 — see specs/02-loader.md § Edge cases).
        if exit_code is not None:
            self.exit_code = exit_code


class DiffError(OwlCompareError):
    """Failure during diff computation."""

    exit_code: int = 4


class CanonicalizationError(OwlCompareError):
    """Failure during canonicalization (Component 04)."""

    exit_code: int = 4


class ReportError(OwlCompareError):
    """Failure during report generation."""

    exit_code: int = 5


class SchemaValidationError(OwlCompareError):
    """A DiffResult JSON payload failed validation against the bundled schema.

    Shares exit code 5 ("report generation error") with :class:`ReportError`:
    emitting JSON that does not conform to the published contract is a failure of
    the report layer. Raised by ``schema.validate_diff_json`` and surfaced to the
    CLI only when ``owlcompare diff --validate-schema`` is set (Component 14).
    """

    exit_code: int = 5


class SeverityConfigError(OwlCompareError):
    """Invalid severity config file (Component 10).

    Default exit code 6 ("config invalid": malformed TOML, unknown
    ``schema_version``, unknown severity value, missing ``kind_pattern``). The
    per-instance override exists for the one case the spec maps elsewhere — a
    config path that does not exist on disk is a usage error (exit 2), not a
    config-content error. See ``specs/10-severity.md`` § Edge cases.
    """

    exit_code: int = 6

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class RenameMappingError(OwlCompareError):
    """Invalid rename mapping config file (Component 11).

    Default exit code 6 ("config invalid": malformed TOML, unknown
    ``schema_version``, or a malformed entry). It shares the config-error code
    with :class:`SeverityConfigError`. The per-instance override exists for the
    one case the spec maps elsewhere — a mapping path that does not exist on disk
    is a usage error (exit 2), not a config-content error. See
    ``specs/11-rename-detection.md`` § Public API.
    """

    exit_code: int = 6

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class NotImplementedYetError(OwlCompareError):
    """A planned feature stub. Used by Layer 2/3 stubs and the diff stub in v1."""

    exit_code: int = 2
