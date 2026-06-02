"""Indexed view of reified restrictions and class axioms (Component 08).

Builds, per snapshot, a structured decoding of every OWL restriction that
Component 04 reified into a ``urn:owlcompare:restriction:<sha>`` URN, plus the
non-anonymous class axioms that live in the same conceptual layer: property
domain/range, ``owl:equivalentClass`` between named classes, ``owl:disjointWith``
(including the n-ary ``owl:AllDisjointClasses`` form expanded to pairs), and
``owl:complementOf``. See ``specs/08-structural-restrictions.md`` § Step 1.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Literal

from rdflib import OWL, RDF, RDFS, Graph
from rdflib.term import Literal as RDFLiteral
from rdflib.term import Node, URIRef

from owlcompare.model import OntologySnapshot

# Canonicalization (Component 04) mints synthetic URNs for reified restrictions
# and collapsed RDF lists. Restriction URNs are the subjects we decode here.
_RESTRICTION_NS = "urn:owlcompare:restriction:"

# Shape predicates and the ``kind`` they map to. The qualified cardinality
# variants additionally carry a filler via ``owl:onClass`` / ``owl:onDataRange``.
_CARDINALITY_KINDS: dict[URIRef, str] = {
    OWL.minCardinality: "min_cardinality",
    OWL.maxCardinality: "max_cardinality",
    OWL.cardinality: "exact_cardinality",
    OWL.minQualifiedCardinality: "min_qualified_cardinality",
    OWL.maxQualifiedCardinality: "max_qualified_cardinality",
    OWL.qualifiedCardinality: "exact_qualified_cardinality",
}
_VALUE_KINDS: dict[URIRef, str] = {
    OWL.someValuesFrom: "some_values_from",
    OWL.allValuesFrom: "all_values_from",
    OWL.hasValue: "has_value",
}
# Where a qualified-cardinality restriction keeps its filler.
_QUALIFIED_FILLER_PREDICATES: tuple[URIRef, ...] = (OWL.onClass, OWL.onDataRange)

# CURIE strings used in ``DecodedRestriction.via_predicate`` (and the details
# dict) so renderers and tests see a stable, readable predicate label.
_SUBCLASS_OF_CURIE = "rdfs:subClassOf"
_EQUIVALENT_CLASS_CURIE = "owl:equivalentClass"

RestrictionKind = Literal[
    "min_cardinality",
    "max_cardinality",
    "exact_cardinality",
    "min_qualified_cardinality",
    "max_qualified_cardinality",
    "exact_qualified_cardinality",
    "some_values_from",
    "all_values_from",
    "has_value",
    "complex",
]


@dataclass(frozen=True, slots=True)
class DecodedRestriction:
    """A restriction reified by Component 04, decoded into structured form."""

    urn: str
    attached_to: str  # IRI of the class the restriction is attached to ("" if none)
    via_predicate: str  # 'rdfs:subClassOf' | 'owl:equivalentClass' ("" if unattached)
    on_property: str | None  # owl:onProperty IRI (None if not present)
    kind: RestrictionKind
    cardinality: int | None  # for cardinality kinds
    filler: str | None  # IRI of value range / individual / datatype filler
    filler_label: str | None  # human label for the filler if known


@dataclass(frozen=True, slots=True)
class RestrictionIndex:
    """Structured view of one snapshot's restrictions and class axioms."""

    by_urn: dict[str, DecodedRestriction]
    by_attached_entity: dict[str, list[DecodedRestriction]]
    domains: dict[str, frozenset[str]]
    ranges: dict[str, frozenset[str]]
    equivalent_class_sets: dict[str, frozenset[str]]
    disjoint_sets: dict[str, frozenset[str]]
    complement_targets: dict[str, str]


def build(snapshot: OntologySnapshot) -> RestrictionIndex:
    """Decode ``snapshot``'s restrictions and collect its class axioms.

    Args:
        snapshot: The (typically canonical) snapshot to index.

    Returns:
        A :class:`RestrictionIndex`. Restrictions are decoded into
        :class:`DecodedRestriction` records keyed by URN and grouped by the named
        class they attach to; domain/range/equivalent/disjoint/complement axioms
        are collected as simple maps.
    """
    graph = snapshot.graph
    labels = _label_map(snapshot)

    by_urn: dict[str, DecodedRestriction] = {
        urn: _decode(urn, graph, labels) for urn in _restriction_urns(graph)
    }

    by_attached_entity: dict[str, list[DecodedRestriction]] = defaultdict(list)
    for cls, via, urn in _attachment_edges(graph):
        decoded = by_urn.get(urn)
        if decoded is None:
            continue
        attached = replace(decoded, attached_to=cls, via_predicate=via)
        by_attached_entity[cls].append(attached)
        # Surface the (first) attachment on the canonical by_urn entry too.
        if by_urn[urn].attached_to == "":
            by_urn[urn] = attached

    return RestrictionIndex(
        by_urn=by_urn,
        by_attached_entity=dict(by_attached_entity),
        domains=_collect_pred(graph, RDFS.domain),
        ranges=_collect_pred(graph, RDFS.range),
        equivalent_class_sets=_collect_equivalent(graph),
        disjoint_sets=_collect_disjoint(graph),
        complement_targets=_collect_complement(graph),
    )


# --------------------------------------------------------------------------- #
# Restriction decoding
# --------------------------------------------------------------------------- #


def _restriction_urns(graph: Graph) -> list[str]:
    """Sorted list of distinct restriction URNs appearing as triple subjects."""
    urns: set[str] = set()
    for subject in graph.subjects():
        if isinstance(subject, URIRef) and str(subject).startswith(_RESTRICTION_NS):
            urns.add(str(subject))
    return sorted(urns)


def _decode(urn: str, graph: Graph, labels: dict[str, str]) -> DecodedRestriction:
    """Decode a single restriction URN into a :class:`DecodedRestriction`."""
    ref = URIRef(urn)
    on_property = _single_uri(graph, ref, OWL.onProperty)
    shape_objects = _shape_predicates(graph, ref)

    base = DecodedRestriction(
        urn=urn,
        attached_to="",
        via_predicate="",
        on_property=on_property,
        kind="complex",
        cardinality=None,
        filler=None,
        filler_label=None,
    )

    # No onProperty, or more than one shape predicate, is malformed → complex.
    if on_property is None or len(shape_objects) != 1:
        return base

    predicate, value = shape_objects[0]
    if predicate in _CARDINALITY_KINDS:
        return _decode_cardinality(base, predicate, value, graph, ref, labels)
    if predicate in _VALUE_KINDS:
        return _decode_value(base, predicate, value, labels)
    # owl:hasSelf and anything else we don't model → complex (spec § Edge cases).
    return base


def _shape_predicates(graph: Graph, ref: URIRef) -> list[tuple[URIRef, Node]]:
    """All (predicate, object) pairs on ``ref`` that define a restriction shape."""
    pairs: list[tuple[URIRef, Node]] = []
    for predicate, obj in graph.predicate_objects(ref):
        if isinstance(predicate, URIRef) and (
            predicate in _CARDINALITY_KINDS or predicate in _VALUE_KINDS
        ):
            pairs.append((predicate, obj))
    return pairs


def _decode_cardinality(
    base: DecodedRestriction,
    predicate: URIRef,
    value: Node,
    graph: Graph,
    ref: URIRef,
    labels: dict[str, str],
) -> DecodedRestriction:
    """Fill in a cardinality (optionally qualified) restriction."""
    cardinality = _as_int(value)
    if cardinality is None:
        return base  # non-integer cardinality literal → leave as complex
    filler = _qualified_filler(graph, ref)
    return replace(
        base,
        kind=_kind(_CARDINALITY_KINDS[predicate]),
        cardinality=cardinality,
        filler=filler,
        filler_label=labels.get(filler) if filler else None,
    )


def _decode_value(
    base: DecodedRestriction,
    predicate: URIRef,
    value: Node,
    labels: dict[str, str],
) -> DecodedRestriction:
    """Fill in a someValuesFrom / allValuesFrom / hasValue restriction."""
    filler = str(value) if isinstance(value, (URIRef, RDFLiteral)) else None
    return replace(
        base,
        kind=_kind(_VALUE_KINDS[predicate]),
        filler=filler,
        filler_label=labels.get(filler) if filler else None,
    )


def _qualified_filler(graph: Graph, ref: URIRef) -> str | None:
    """The owl:onClass / owl:onDataRange filler of a qualified cardinality, if any."""
    for predicate in _QUALIFIED_FILLER_PREDICATES:
        value = _single_uri(graph, ref, predicate)
        if value is not None:
            return value
    return None


def _attachment_edges(graph: Graph) -> list[tuple[str, str, str]]:
    """``(class_iri, via_curie, restriction_urn)`` edges, sorted deterministically."""
    edges: list[tuple[str, str, str]] = []
    via_by_predicate = (
        (RDFS.subClassOf, _SUBCLASS_OF_CURIE),
        (OWL.equivalentClass, _EQUIVALENT_CLASS_CURIE),
    )
    for predicate, curie in via_by_predicate:
        for subject, _, obj in graph.triples((None, predicate, None)):
            if not isinstance(subject, URIRef) or not isinstance(obj, URIRef):
                continue
            if str(obj).startswith(_RESTRICTION_NS):
                edges.append((str(subject), curie, str(obj)))
    return sorted(edges)


# --------------------------------------------------------------------------- #
# Domain / range / equivalent / disjoint / complement
# --------------------------------------------------------------------------- #


def _collect_pred(graph: Graph, predicate: URIRef) -> dict[str, frozenset[str]]:
    """Map each named subject to the frozenset of named objects for ``predicate``."""
    collected: dict[str, set[str]] = defaultdict(set)
    for subject, _, obj in graph.triples((None, predicate, None)):
        if isinstance(subject, URIRef) and isinstance(obj, URIRef):
            collected[str(subject)].add(str(obj))
    return {key: frozenset(values) for key, values in collected.items()}


def _collect_equivalent(graph: Graph) -> dict[str, frozenset[str]]:
    """Named ``owl:equivalentClass`` pairs (restriction-URN targets excluded)."""
    collected: dict[str, set[str]] = defaultdict(set)
    for subject, _, obj in graph.triples((None, OWL.equivalentClass, None)):
        if not isinstance(subject, URIRef) or not isinstance(obj, URIRef):
            continue
        if str(obj).startswith(_RESTRICTION_NS) or str(subject).startswith(_RESTRICTION_NS):
            continue  # restriction attachment, handled via by_attached_entity
        collected[str(subject)].add(str(obj))
    return {key: frozenset(values) for key, values in collected.items()}


def _collect_disjoint(graph: Graph) -> dict[str, frozenset[str]]:
    """Symmetric disjointness map from ``owl:disjointWith`` and AllDisjointClasses."""
    collected: dict[str, set[str]] = defaultdict(set)

    def add_pair(first: str, second: str) -> None:
        collected[first].add(second)
        collected[second].add(first)

    for subject, _, obj in graph.triples((None, OWL.disjointWith, None)):
        if isinstance(subject, URIRef) and isinstance(obj, URIRef):
            add_pair(str(subject), str(obj))

    for node in graph.subjects(RDF.type, OWL.AllDisjointClasses):
        members = _disjoint_members(graph, node)
        for i, first in enumerate(members):
            for second in members[i + 1 :]:
                add_pair(first, second)

    return {key: frozenset(values) for key, values in collected.items()}


def _disjoint_members(graph: Graph, node: Node) -> list[str]:
    """Named members of an ``owl:AllDisjointClasses`` node's ``owl:members`` list."""
    members: list[str] = []
    for list_head in graph.objects(node, OWL.members):
        members.extend(_read_list(graph, list_head))
    return members


def _read_list(graph: Graph, head: Node) -> list[str]:
    """Walk a (canonicalized) RDF list, returning its named-IRI members in order."""
    members: list[str] = []
    seen: set[Node] = set()
    node: Node = head
    while node != RDF.nil and node not in seen:
        seen.add(node)
        firsts = list(graph.objects(node, RDF.first))
        if not firsts:
            break
        first = firsts[0]
        if isinstance(first, URIRef):
            members.append(str(first))
        rests = list(graph.objects(node, RDF.rest))
        if not rests:
            break
        node = rests[0]
    return members


def _collect_complement(graph: Graph) -> dict[str, str]:
    """Map each named class to the named class it is the ``owl:complementOf``."""
    targets: dict[str, str] = {}
    for subject, _, obj in graph.triples((None, OWL.complementOf, None)):
        if isinstance(subject, URIRef) and isinstance(obj, URIRef):
            targets[str(subject)] = str(obj)
    return targets


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _single_uri(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    """The single URIRef object of ``subject predicate ?o``, or ``None``."""
    for obj in graph.objects(subject, predicate):
        if isinstance(obj, URIRef):
            return str(obj)
    return None


def _as_int(value: Node) -> int | None:
    """Parse an rdflib literal as an int, or ``None`` if not integral."""
    if not isinstance(value, RDFLiteral):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _kind(value: str) -> RestrictionKind:
    """Narrow a kind string from the lookup tables to :data:`RestrictionKind`."""
    return value  # type: ignore[return-value]


def _label_map(snapshot: OntologySnapshot) -> dict[str, str]:
    """IRI → best label, reusing the snapshot's already-indexed entity labels."""
    labels: dict[str, str] = {}
    for bucket in snapshot.entities.by_kind().values():
        for iri, entity in bucket.items():
            if entity.labels:
                labels[iri] = entity.labels[0][1]
    return labels
