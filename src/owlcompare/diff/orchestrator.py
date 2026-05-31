"""Top-level diff orchestrator — the canonical entry point for a full diff.

Runs the layer pipeline end-to-end: canonicalize if needed, Layer 0 (always),
then each enabled Layer 1 slice sharing one :class:`SubsumptionRegistry`. Layer
2/3 are stubs that contribute nothing yet (DD-009). The CLI calls :func:`run`
rather than poking individual layers, so canonicalization and layer wiring live
in exactly one place. See ``specs/06-structural-entities.md`` § Orchestrator.
"""

from __future__ import annotations

import logging

from owlcompare.canonicalize import canonicalize
from owlcompare.exceptions import DiffError
from owlcompare.model import OntologySnapshot

from . import syntactic
from ._common import Change, DiffOptions, DiffResult
from ._subsumption import SubsumptionRegistry
from .structural import entities

logger = logging.getLogger(__name__)


def run(
    a: OntologySnapshot,
    b: OntologySnapshot,
    options: DiffOptions | None = None,
) -> DiffResult:
    """Run the diff pipeline end-to-end across all enabled layers.

    Canonicalizes non-canonical inputs silently (Q3 — logged at INFO), runs
    Layer 0 then any enabled Layer 1 slice with a shared subsumption registry,
    and returns a :class:`DiffResult` carrying every change plus metadata
    (per-layer counts and the registry).

    Args:
        a: Baseline snapshot (canonical or not).
        b: Comparison snapshot (canonical or not).
        options: Layer selection and future knobs.

    Returns:
        Aggregated :class:`DiffResult`.

    Raises:
        DiffError: if the structural layer is requested without the syntactic
            layer it depends on.
    """
    opts = options or DiffOptions()
    layers = opts.include_layers
    if "structural" in layers and "syntactic" not in layers:
        raise DiffError("the structural layer depends on the syntactic layer; enable both")

    a = _ensure_canonical(a)
    b = _ensure_canonical(b)

    registry = SubsumptionRegistry()
    all_changes: list[Change] = []
    layer_counts: dict[str, int] = {}

    layer0: list[Change] = []
    if "syntactic" in layers:
        layer0 = syntactic.diff(a, b, opts)
        all_changes.extend(layer0)
        layer_counts["syntactic"] = len(layer0)

    if "structural" in layers:
        structural_changes = entities.diff(a, b, layer0, registry, opts)
        all_changes.extend(structural_changes)
        layer_counts["structural"] = len(structural_changes)

    metadata = {
        "layer_counts": layer_counts,
        "subsumption_registry": registry,
    }
    return DiffResult(a=a, b=b, changes=tuple(all_changes), metadata=metadata)


def _ensure_canonical(snapshot: OntologySnapshot) -> OntologySnapshot:
    """Return a canonical snapshot, canonicalizing (and logging) if needed."""
    if snapshot.canonical:
        return snapshot
    logger.info("auto-canonicalizing non-canonical snapshot: %s", snapshot.source)
    return canonicalize(snapshot)
