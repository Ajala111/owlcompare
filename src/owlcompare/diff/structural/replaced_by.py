"""Layer 1 — ``dcterms:isReplacedBy`` soft-deprecation diff (Component 12.5).

When a curator asserts ``:Old dcterms:isReplacedBy :New`` they are recording a
soft-deprecation / migration signal that is *semantically* a rename but is
*evidence* worth surfacing in its own right. This slice promotes such assertions
from the generic ``annotation_added`` that :mod:`.annotations` would emit into a
dedicated ``replaced_by_set`` (or ``replaced_by_unset`` when the assertion is
withdrawn), and cross-references the detected renames so a consistent rename is
flagged in ``details``.

It runs *after* rename detection (so it can read ``renames_applied``) and the
orchestrator retracts the superseded ``annotation_added`` / ``annotation_removed``
changes for the same triple — the retraction pattern (Q3): the annotation slice
stays oblivious to specific predicates, and this and any future predicate-specific
promoter reuse the same mechanism. See ``specs/12.5-anonymous-structures.md`` § Part 4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from rdflib.namespace import DCTERMS, NamespaceManager
from rdflib.term import URIRef

from owlcompare.exceptions import DiffError
from owlcompare.model import OntologySnapshot, shorten_iri

from .._common import Change, DiffOptions, Severity
from .._subsumption import SubsumptionRegistry

logger = logging.getLogger(__name__)

# The one predicate this slice promotes. Exposed so the orchestrator can retract
# the annotation-layer emissions for the same triple.
IS_REPLACED_BY = str(DCTERMS.isReplacedBy)

Layer0EdgeIndex = dict[tuple[str | None, str | None, str], list[Change]]


@dataclass(slots=True)
class _Ctx:
    """Per-call state threaded through the replaced-by diff helpers."""

    prefixes: dict[str, str]
    registry: SubsumptionRegistry
    nsm_a: NamespaceManager
    nsm_b: NamespaceManager
    by_edge: Layer0EdgeIndex
    iris_a: set[str]
    iris_b: set[str]
    renames: dict[str, str]  # before_iri -> after_iri for accepted renames

    def short(self, iri: str) -> str:
        return shorten_iri(iri, self.prefixes)


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    layer0_changes: list[Change],
    registry: SubsumptionRegistry,
    renames_applied: tuple[Any, ...] = (),
    options: DiffOptions | None = None,
) -> list[Change]:
    """Detect ``dcterms:isReplacedBy`` assertions added or removed between A and B.

    Emits ``replaced_by_set`` (non_breaking) for a newly asserted replacement and
    ``replaced_by_unset`` (info) for a withdrawn one, subsuming the underlying
    ``dcterms:isReplacedBy`` triple change. Sets
    ``details.matches_detected_rename`` when the assertion mirrors an accepted
    rename (``before_iri`` == entity, ``after_iri`` == target).

    Args:
        a: Baseline snapshot (canonicalized).
        b: Comparison snapshot (canonicalized).
        layer0_changes: Component 05's output, used for subsumption tracking.
        registry: Shared subsumption registry, mutated in place.
        renames_applied: The accepted ``RenameCandidate`` tuple from rename
            detection, for the consistency cross-check.
        options: Reserved for future layer knobs; unused by this slice.

    Returns:
        A list of ``Change`` records with ``layer="structural"``.

    Raises:
        DiffError: if either snapshot is not canonicalized.
    """
    del options  # no replaced-by-slice knobs yet; kept for a uniform signature
    if not a.canonical or not b.canonical:
        raise DiffError("inputs must be canonicalized first")

    ctx = _Ctx(
        prefixes={**a.prefixes, **b.prefixes},
        registry=registry,
        nsm_a=a.graph.namespace_manager,
        nsm_b=b.graph.namespace_manager,
        by_edge=_index_by_edge(layer0_changes),
        iris_a=a.entities.all_iris(),
        iris_b=b.entities.all_iris(),
        renames={cand.removed_iri: cand.added_iri for cand in renames_applied},
    )

    assertions_a = _assertions(a)
    assertions_b = _assertions(b)

    changes: list[Change] = []
    for entity, target in sorted(assertions_b - assertions_a):
        change = _emit(ctx, entity, target, added=True)
        if change is not None:
            changes.append(change)
    for entity, target in sorted(assertions_a - assertions_b):
        change = _emit(ctx, entity, target, added=False)
        if change is not None:
            changes.append(change)
    return changes


def supersedes_annotation(change: Change) -> bool:
    """Whether ``change`` is an annotation emission this slice replaces.

    The orchestrator removes these ``annotation_added`` / ``annotation_removed``
    changes once ``replaced_by_*`` has been emitted for the same triple.
    """
    return (
        change.kind in ("annotation_added", "annotation_removed", "annotation_changed")
        and change.details.get("predicate_iri") == IS_REPLACED_BY
    )


def _assertions(snapshot: OntologySnapshot) -> set[tuple[str, str]]:
    """All ``(entity_iri, target_iri)`` ``dcterms:isReplacedBy`` pairs in a snapshot."""
    pairs: set[tuple[str, str]] = set()
    for subject, _, obj in snapshot.graph.triples((None, DCTERMS.isReplacedBy, None)):
        if isinstance(subject, URIRef) and isinstance(obj, URIRef):
            pairs.add((str(subject), str(obj)))
    return pairs


def _emit(ctx: _Ctx, entity: str, target: str, *, added: bool) -> Change | None:
    """Build one ``replaced_by_set`` / ``replaced_by_unset`` change (or ``None`` to skip)."""
    matches_rename = ctx.renames.get(entity) == target
    # An entity wholly added/removed has its triples subsumed under Component 06's
    # change; don't double-emit (spec § Edge cases: renamed-away assertion). The
    # exception is a renamed entity whose isReplacedBy target *is* its rename's new
    # IRI: the rename consolidated the removal, so surfacing the curator's
    # corroborating signal is exactly the point (the consistency cross-check).
    if _wholly_changed(ctx, entity) and not matches_rename:
        return None

    target_existed_in_b = target in ctx.iris_b
    kind: str
    severity: Severity
    if added:
        kind, severity = "replaced_by_set", "non_breaking"
        summary = f"{ctx.short(entity)} marked as replaced by {ctx.short(target)}"
        if matches_rename:
            summary += " (consistent with detected rename)"
    else:
        kind, severity = "replaced_by_unset", "info"
        summary = f"{ctx.short(entity)} no longer marked as replaced by {ctx.short(target)}"

    details: dict[str, object] = {
        "entity_iri": entity,
        "target_iri": target,
        "matches_detected_rename": matches_rename,
        "target_existed_in_b": target_existed_in_b,
    }
    subsumed = _match_edge(ctx, entity, target, removed=not added)
    return _finalize(ctx, kind, severity, entity, summary, details, subsumed)


def _wholly_changed(ctx: _Ctx, iri: str) -> bool:
    """Whether ``iri`` exists on exactly one side (wholly added or removed)."""
    return (iri in ctx.iris_a) != (iri in ctx.iris_b)


def _index_by_edge(layer0_changes: list[Change]) -> Layer0EdgeIndex:
    """Bucket Layer 0 changes by ``(subject_iri, predicate_iri, kind)``."""
    index: Layer0EdgeIndex = {}
    for change in layer0_changes:
        key = (
            change.details.get("subject_iri"),
            change.details.get("predicate_iri"),
            change.kind,
        )
        index.setdefault(key, []).append(change)
    return index


def _match_edge(ctx: _Ctx, entity: str, target: str, *, removed: bool) -> list[Change]:
    """Layer 0 changes for the exact ``entity dcterms:isReplacedBy target`` triple."""
    triple_kind = "triple_removed" if removed else "triple_added"
    nsm = ctx.nsm_a if removed else ctx.nsm_b
    candidates = ctx.by_edge.get((entity, IS_REPLACED_BY, triple_kind), [])
    target_n3 = URIRef(target).n3(nsm)
    return [c for c in candidates if c.details.get("object") == target_n3]


def _finalize(
    ctx: _Ctx,
    kind: str,
    severity: Severity,
    subject: str,
    summary: str,
    details: dict[str, object],
    subsumed: list[Change],
) -> Change:
    """Attach subsumption + change_id to a replaced-by change and register it."""
    details["subsumes"] = [SubsumptionRegistry.change_id(c) for c in subsumed]
    change = Change(
        layer="structural",
        kind=kind,
        severity=severity,
        subject=subject,
        summary=summary,
        details=details,
    )
    change_id = SubsumptionRegistry.change_id(change)
    change.details["change_id"] = change_id
    if subsumed:
        ctx.registry.register(change_id, subsumed)
    else:
        logger.debug("replaced-by change %s has no matching Layer 0 changes", change_id)
    return change
