"""Shared diff types used by every layer (0-3) and the report renderers.

``Change`` is the long-lived contract: one record per difference. Layers 1-3
and all renderers consume it, so its shape is deliberately stable. See
``specs/05-syntactic-diff.md`` § Public API and DD-006 (frozen dataclasses) /
DD-008 (severity is set by the producing layer, not computed afterward).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from owlcompare.model import OntologySnapshot

DiffLayer = Literal["syntactic", "structural", "inferential", "impact"]
Severity = Literal["breaking", "non_breaking", "additive", "info"]

# Synthetic IRIs minted by canonicalization (Component 04): a 64-hex content
# hash. At full length they dominate diff-row width and trigger truncation, so
# the *display* layer abbreviates them. The full URN stays in Change.details for
# Layer 1 and machine consumers — only human-facing summaries/tables shorten.
_SYNTHETIC_IRI_RE = re.compile(r"^urn:owlcompare:(restriction|list):([0-9a-f]{64})$")
# How many leading hex chars of the hash to keep — enough to stay unique within
# a single small diff while fitting comfortably on one row.
_SYNTHETIC_HASH_PREFIX_LEN = 8


def shorten_synthetic_iri(iri: str) -> str:
    """Return a compact display form for a canonicalization-minted URN.

    ``urn:owlcompare:restriction:<64-hex>`` becomes ``_restriction:<8-hex>`` and
    the ``list`` variant becomes ``_list:<8-hex>``. The leading underscore marks
    the term as synthetic without colliding with a real namespace prefix. Any
    other string is returned unchanged.
    """
    match = _SYNTHETIC_IRI_RE.match(iri)
    if match is None:
        return iri
    kind, digest = match.group(1), match.group(2)
    return f"_{kind}:{digest[:_SYNTHETIC_HASH_PREFIX_LEN]}"


@dataclass(frozen=True, slots=True)
class Change:
    """A single record describing one difference between two snapshots.

    ``details``, ``before`` and ``after`` are excluded from ``__hash__`` (they
    may hold dicts/lists, which are unhashable) but remain part of ``__eq__``,
    so a ``Change`` is both hashable and value-comparable. Field names and types
    match the contract in ``specs/05-syntactic-diff.md``.
    """

    layer: DiffLayer
    kind: str  # e.g., "triple_added", "triple_removed"
    severity: Severity
    subject: str | None  # IRI of the affected entity, when applicable
    summary: str  # one-line human description
    details: dict[str, Any] = field(default_factory=dict, hash=False)
    before: Any | None = field(default=None, hash=False)
    after: Any | None = field(default=None, hash=False)


@dataclass(frozen=True, slots=True)
class DiffOptions:
    """Diff invocation knobs."""

    include_layers: tuple[DiffLayer, ...] = ("syntactic", "structural", "inferential", "impact")
    # Layer-specific knobs added later; deliberately empty for v1 syntactic.


@dataclass(frozen=True)
class DiffResult:
    """Aggregated diff output (populated by the orchestrator; defined here for shared use)."""

    a: OntologySnapshot  # forward ref to avoid circular import
    b: OntologySnapshot
    changes: tuple[Change, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
