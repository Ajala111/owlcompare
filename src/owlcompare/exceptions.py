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


class ReportError(OwlCompareError):
    """Failure during report generation."""

    exit_code: int = 5


class NotImplementedYetError(OwlCompareError):
    """A planned feature stub. Used by Layer 2/3 stubs and the diff stub in v1."""

    exit_code: int = 2
