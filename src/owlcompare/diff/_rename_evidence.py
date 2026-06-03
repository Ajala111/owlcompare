"""Fingerprinting and scoring helpers for rename detection (Component 11).

A rename is inferred by comparing the *shape* of a removed-side entity (in A)
with an added-side entity (in B): their labels, asserted parents, and the
predicates of the triples flowing into and out of them. :class:`EntityFingerprint`
captures that shape; :func:`score` turns a pair of fingerprints into a normalized
``0.0-1.0`` similarity used by the medium-confidence (structural) heuristic.

The scoring weights and per-category caps are fixed by the spec and pinned in
tests so an accidental retune is caught. See ``specs/11-rename-detection.md``
§ Step 2 / § Step 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from rdflib import RDFS
from rdflib.term import URIRef

from owlcompare.model import EntityKind, OntologySnapshot

from .structural._hierarchy_index import HierarchyIndex
from .structural._hierarchy_index import build as build_hierarchy

# Canonicalization mints these synthetic URNs for reified restrictions; a class's
# attached restrictions sit on ``rdfs:subClassOf`` edges pointing at them.
_RESTRICTION_PREFIX = "urn:owlcompare:restriction:"

# Fingerprint scoring (spec § Step 5). Per-shared-item weight and per-category
# cap. DO NOT retune without updating specs/11-rename-detection.md and the tests
# that pin these exact values.
_LABEL_WEIGHT, _LABEL_CAP = 0.3, 0.5
_PARENT_WEIGHT, _PARENT_CAP = 0.2, 0.4
_INCOMING_WEIGHT, _INCOMING_CAP = 0.1, 0.3
_OUTGOING_WEIGHT, _OUTGOING_CAP = 0.05, 0.2

# Acceptance and separation thresholds for a medium-confidence fingerprint match.
ACCEPT_THRESHOLD = 0.6
SEPARATION_THRESHOLD = 0.2

# Entity kinds that use the property hierarchy (subPropertyOf) rather than the
# class hierarchy (subClassOf) for their parent/child edges.
_PROPERTY_KINDS = frozenset({"object_property", "data_property", "annotation_property"})


@dataclass(frozen=True, slots=True)
class EntityFingerprint:
    """Structural fingerprint of an entity for rename matching."""

    iri: str
    kind: str
    labels: tuple[tuple[str, str], ...]  # ((lang, text), ...) sorted
    parents: tuple[str, ...]  # direct subClass/subProperty parents (named, sorted)
    children: tuple[str, ...]  # direct children (named, sorted)
    incoming_predicates: tuple[str, ...]  # predicates of triples with entity as object
    outgoing_predicates: tuple[str, ...]  # predicates of triples with entity as subject
    attached_restrictions: tuple[str, ...]  # reified restriction URNs via subClassOf


def build_fingerprint(
    snapshot: OntologySnapshot,
    iri: str,
    kind: str,
    hierarchy: HierarchyIndex | None = None,
) -> EntityFingerprint:
    """Build the :class:`EntityFingerprint` for ``iri`` (of ``kind``) in ``snapshot``.

    Queries the snapshot's canonical graph for the entity's labels, asserted
    parents/children, and the predicates flowing in and out. The entity's own
    IRI is never recorded as a value — only the *predicates* are kept, so the
    fingerprint captures the entity's shape, not its identity.

    Args:
        snapshot: The (canonical) snapshot the entity lives in.
        iri: The entity IRI.
        kind: One of ``class`` / ``object_property`` / ``data_property`` /
            ``annotation_property``.
        hierarchy: A prebuilt :class:`HierarchyIndex` for ``snapshot`` (built on
            demand if omitted; callers diffing many entities should pass one).

    Returns:
        The entity's fingerprint.
    """
    index = hierarchy if hierarchy is not None else build_hierarchy(snapshot)
    if kind in _PROPERTY_KINDS:
        parents_map, children_map = index.property_parents, index.property_children
    else:
        parents_map, children_map = index.class_parents, index.class_children

    bucket = snapshot.entities.by_kind().get(cast("EntityKind", kind), {})
    entity = bucket.get(iri)
    labels = tuple(sorted(entity.labels)) if entity is not None else ()

    node = URIRef(iri)
    outgoing = sorted({str(p) for _, p, _ in snapshot.graph.triples((node, None, None))})
    incoming = sorted({str(p) for _, p, _ in snapshot.graph.triples((None, None, node))})
    attached = sorted(
        str(o)
        for _, _, o in snapshot.graph.triples((node, RDFS.subClassOf, None))
        if str(o).startswith(_RESTRICTION_PREFIX)
    )

    return EntityFingerprint(
        iri=iri,
        kind=kind,
        labels=labels,
        parents=tuple(sorted(parents_map.get(iri, frozenset()))),
        children=tuple(sorted(children_map.get(iri, frozenset()))),
        incoming_predicates=tuple(incoming),
        outgoing_predicates=tuple(outgoing),
        attached_restrictions=tuple(attached),
    )


def score(left: EntityFingerprint, right: EntityFingerprint) -> float:
    """Normalized ``0.0-1.0`` structural similarity between two fingerprints.

    Sums four capped category contributions — shared labels, shared parents,
    shared incoming predicates, shared outgoing predicates — and clamps the
    total to ``1.0`` (the raw maximum is ``1.4``). Weights/caps are fixed by the
    spec; see the module constants.
    """
    labels = _capped(_shared(left.labels, right.labels), _LABEL_WEIGHT, _LABEL_CAP)
    parents = _capped(_shared(left.parents, right.parents), _PARENT_WEIGHT, _PARENT_CAP)
    incoming = _capped(
        _shared(left.incoming_predicates, right.incoming_predicates),
        _INCOMING_WEIGHT,
        _INCOMING_CAP,
    )
    outgoing = _capped(
        _shared(left.outgoing_predicates, right.outgoing_predicates),
        _OUTGOING_WEIGHT,
        _OUTGOING_CAP,
    )
    return min(1.0, labels + parents + incoming + outgoing)


def shared_counts(left: EntityFingerprint, right: EntityFingerprint) -> dict[str, int]:
    """Per-category overlap counts, for building human-readable evidence lines."""
    return {
        "labels": _shared(left.labels, right.labels),
        "parents": _shared(left.parents, right.parents),
        "incoming": _shared(left.incoming_predicates, right.incoming_predicates),
        "outgoing": _shared(left.outgoing_predicates, right.outgoing_predicates),
    }


def _shared(left: tuple[object, ...], right: tuple[object, ...]) -> int:
    return len(set(left) & set(right))


def _capped(count: int, weight: float, cap: float) -> float:
    return min(count * weight, cap)
