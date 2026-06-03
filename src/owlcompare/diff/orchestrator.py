"""Top-level diff orchestrator — the canonical entry point for a full diff.

Runs the layer pipeline end-to-end: canonicalize if needed, Layer 0 (always),
then each enabled Layer 1 slice sharing one :class:`SubsumptionRegistry`. Layer
2/3 are stubs that contribute nothing yet (DD-009). The CLI calls :func:`run`
rather than poking individual layers, so canonicalization and layer wiring live
in exactly one place. See ``specs/06-structural-entities.md`` § Orchestrator.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from owlcompare.canonicalize import canonicalize
from owlcompare.exceptions import DiffError
from owlcompare.model import OntologySnapshot
from owlcompare.rename_mapping import RenameMapping
from owlcompare.severity_config import SeverityConfig

from . import rename, severity, syntactic
from ._common import Change, DiffOptions, DiffResult
from ._subsumption import SubsumptionRegistry
from .rename import RenameConfidence

# Aliased: the bare name ``annotations`` would clash with the module-level
# ``from __future__ import annotations`` binding above (a ``__future__._Feature``),
# which both mypy and the import machinery resolve ahead of the submodule.
from .structural import annotations as annotations_slice
from .structural import entities, hierarchy, restrictions

logger = logging.getLogger(__name__)


def run(
    a: OntologySnapshot,
    b: OntologySnapshot,
    options: DiffOptions | None = None,
    severity_config: SeverityConfig | None = None,
    refine_severity: bool = True,
    rename_mapping: RenameMapping | None = None,
    rename_min_confidence: RenameConfidence = "high",
    detect_renames: bool = True,
) -> DiffResult:
    """Run the diff pipeline end-to-end across all enabled layers.

    Canonicalizes non-canonical inputs silently (Q3 — logged at INFO), runs
    Layer 0 then any enabled Layer 1 slice with a shared subsumption registry,
    and finally (Component 10) refines severities with cross-cutting rules and any
    user overrides. Returns a :class:`DiffResult` carrying every change plus
    metadata (per-layer counts, the registry, and the severity-refinement audit
    trail).

    Args:
        a: Baseline snapshot (canonical or not).
        b: Comparison snapshot (canonical or not).
        options: Layer selection and future knobs.
        severity_config: Optional user severity overrides (Component 10).
        refine_severity: When ``False``, skip Component 10 entirely (the CLI's
            ``--no-severity-refinement``); metadata still gets an empty
            ``severity_refinements`` tuple so the schema is stable.
        rename_mapping: Optional user-supplied rename map (Component 11), applied
            at ``certain`` confidence before any heuristic.
        rename_min_confidence: Minimum confidence tier to accept a rename.
        detect_renames: When ``False``, skip Component 11 entirely (the CLI's
            ``--rename-confidence none``).

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
        # Run entity-level first, then hierarchy, then restrictions, then
        # annotations: all share one registry, so later slices can defer a
        # new/removed entity's edges to Component 06's change instead of
        # double-reporting them, and each slice can consult the prior subsumption
        # decisions. Annotations run last — the final Layer 1 slice.
        structural_changes = entities.diff(a, b, layer0, registry, opts)
        structural_changes += hierarchy.diff(a, b, layer0, registry, opts)
        structural_changes += restrictions.diff(a, b, layer0, registry, opts)
        structural_changes += annotations_slice.diff(a, b, layer0, registry, opts)
        all_changes.extend(structural_changes)
        layer_counts["structural"] = len(structural_changes)

    metadata = {
        "layer_counts": layer_counts,
        "subsumption_registry": registry,
    }
    result = DiffResult(a=a, b=b, changes=tuple(all_changes), metadata=metadata)

    if detect_renames:
        # Component 11 runs between the Layer 1 slices and severity refinement:
        # it consolidates paired add/remove changes (plus cascade consequences)
        # into single ``*_renamed`` changes so the severity classifier sees the
        # consolidated result, not the duplicated one. See specs/11-rename-detection.md.
        result = rename.detect(result, rename_mapping, rename_min_confidence)

    if refine_severity:
        # Component 10 runs after every Layer 1 slice: it is the one place with
        # all changes (and the populated registry) in view. See specs/10-severity.md.
        return severity.refine(result, severity_config)
    new_metadata = dict(result.metadata)
    new_metadata["severity_refinements"] = ()
    return replace(result, metadata=new_metadata)


def _ensure_canonical(snapshot: OntologySnapshot) -> OntologySnapshot:
    """Return a canonical snapshot, canonicalizing (and logging) if needed."""
    if snapshot.canonical:
        return snapshot
    logger.info("auto-canonicalizing non-canonical snapshot: %s", snapshot.source)
    return canonicalize(snapshot)
