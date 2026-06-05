"""Indexed view of anonymous class-set structures (Component 12.5).

Decodes ``owl:unionOf`` / ``owl:intersectionOf`` lists attached to a named entity
via ``rdfs:domain``, ``rdfs:range``, ``rdfs:subClassOf`` or ``owl:equivalentClass``
into a flat, diffable form. After canonicalization (Component 04) an anonymous
``[ a owl:Class ; owl:unionOf ( :A :B ) ]`` becomes a
``urn:owlcompare:restriction:<sha>`` URN typed ``owl:Class`` carrying an
``owl:unionOf`` edge to a collapsed ``urn:owlcompare:list:<sha>`` chain; a
union *of datatypes* (``[ a rdfs:Datatype ; owl:unionOf (...) ]``) stays a blank
node (``rdfs:Datatype`` is not reified) but is decoded the same way — its
``raw_urn`` is simply ``None``. See ``specs/12.5-anonymous-structures.md`` § Part 1.

This module is a pure decoder. The Layer 1 slice that emits the change records
lives in :mod:`.class_sets`; the ownership helpers (:func:`owned_keys`,
:func:`class_set_node_ids`) let Components 07 and 08 step aside for the structures
decoded here rather than mis-reporting them as bare hierarchy / domain-range
edits or opaque ``complex_class_expression_changed`` fallbacks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from rdflib import OWL, RDF, RDFS, Graph
from rdflib.term import Node, URIRef

from owlcompare.model import OntologySnapshot

logger = logging.getLogger(__name__)

# Synthetic URNs minted by canonicalization. List URNs are walked (they are the
# union's members' carrier); restriction URNs appearing *as members* are nested
# anonymous expressions and are skipped (left to Component 08's complex fallback).
_SYNTHETIC_PREFIX = "urn:owlcompare:"
_RESTRICTION_NS = "urn:owlcompare:restriction:"

ViaPredicate = Literal["rdfs:domain", "rdfs:range", "rdfs:subClassOf", "owl:equivalentClass"]
Operator = Literal["unionOf", "intersectionOf"]

# Attachment predicates and the CURIE recorded in ``via_predicate`` / details.
_ATTACH_PREDICATES: tuple[tuple[URIRef, str], ...] = (
    (RDFS.domain, "rdfs:domain"),
    (RDFS.range, "rdfs:range"),
    (RDFS.subClassOf, "rdfs:subClassOf"),
    (OWL.equivalentClass, "owl:equivalentClass"),
)

# Class-set operators and the short token recorded in ``operator``.
_OPERATORS: tuple[tuple[URIRef, Operator], ...] = (
    (OWL.unionOf, "unionOf"),
    (OWL.intersectionOf, "intersectionOf"),
)


@dataclass(frozen=True, slots=True)
class ClassSetAttachment:
    """An ``owl:unionOf`` / ``owl:intersectionOf`` set attached to a named entity."""

    attached_to: str  # IRI of the named entity (the subject)
    via_predicate: ViaPredicate
    operator: Operator
    member_iris: tuple[str, ...]  # sorted tuple of named-entity member IRIs
    raw_urn: str | None  # the urn:owlcompare:restriction: URN, or None for a blank node


@dataclass(frozen=True, slots=True)
class ClassSetIndex:
    """Structured view of one snapshot's anonymous class-set attachments."""

    # key = (attached_to, via_predicate, operator)
    by_attachment: dict[tuple[str, str, str], ClassSetAttachment]

    def for_key(self, attached_to: str, via_predicate: str) -> ClassSetAttachment | None:
        """The attachment for ``(attached_to, via_predicate)`` regardless of operator."""
        for operator in ("unionOf", "intersectionOf"):
            attachment = self.by_attachment.get((attached_to, via_predicate, operator))
            if attachment is not None:
                return attachment
        return None


def build(snapshot: OntologySnapshot) -> ClassSetIndex:
    """Decode ``snapshot``'s anonymous union/intersection class-set attachments.

    Args:
        snapshot: The (typically canonical) snapshot to index.

    Returns:
        A :class:`ClassSetIndex` keyed by ``(attached_to, via_predicate, operator)``.
        Empty unions (``owl:unionOf rdf:nil``) and attachments whose members are
        all blank nodes / nested anonymous expressions are dropped (logged at INFO).
    """
    graph = snapshot.graph
    by_attachment: dict[tuple[str, str, str], ClassSetAttachment] = {}

    for predicate, via in _ATTACH_PREDICATES:
        for subject, _, target in graph.triples((None, predicate, None)):
            if not isinstance(subject, URIRef):
                continue
            decoded = _decode_target(graph, target)
            if decoded is None:
                continue
            operator, members = decoded
            # Flattening normalization (spec § Part 1 step 3): a union/intersection
            # with fewer than two named members is logically a bare relation, so it
            # is not recorded as a set attachment. The class-set *node* is still
            # owned (see ``owned_keys``) so Components 07/08 step aside, and the
            # diff reads the lone member through the graph as an effective member.
            if len(members) < 2:
                logger.info(
                    "single-member/empty class set on %s via %s; normalized to bare",
                    str(subject),
                    via,
                )
                continue
            key = (str(subject), via, operator)
            existing = _existing_other_operator(by_attachment, str(subject), via, operator)
            if existing is not None:
                logger.info(
                    "both unionOf and intersectionOf on %s via %s; keeping first (%s)",
                    str(subject),
                    via,
                    existing,
                )
                continue
            raw_urn = str(target) if isinstance(target, URIRef) else None
            by_attachment[key] = ClassSetAttachment(
                attached_to=str(subject),
                via_predicate=via,  # type: ignore[arg-type]
                operator=operator,
                member_iris=members,
                raw_urn=raw_urn,
            )

    return ClassSetIndex(by_attachment=by_attachment)


def _existing_other_operator(
    by_attachment: dict[tuple[str, str, str], ClassSetAttachment],
    attached_to: str,
    via: str,
    operator: Operator,
) -> str | None:
    """The operator already recorded for ``(attached_to, via)`` if it differs."""
    for candidate, _ in _OPERATORS:
        token = "unionOf" if candidate == OWL.unionOf else "intersectionOf"
        if token != operator and (attached_to, via, token) in by_attachment:
            return token
    return None


def _decode_target(graph: Graph, target: Node) -> tuple[Operator, tuple[str, ...]] | None:
    """Decode a class-set target into ``(operator, sorted named members)``.

    ``None`` when ``target`` is not an anonymous class set (no ``owl:unionOf`` /
    ``owl:intersectionOf`` edge), e.g. a named class, a plain datatype, or a
    property restriction (Component 08's territory).
    """
    for op_predicate, operator in _OPERATORS:
        list_heads = list(graph.objects(target, op_predicate))
        if not list_heads:
            continue
        members = _read_named_members(graph, list_heads[0])
        return operator, members
    return None


def _read_named_members(graph: Graph, head: Node) -> tuple[str, ...]:
    """Walk a canonicalized RDF list, returning its sorted *named* member IRIs.

    Blank-node members and nested anonymous expressions (synthetic restriction
    URNs) are skipped — those are left to Component 08's complex fallback; only
    the union's named members are tracked here (spec § Part 1).
    """
    members: set[str] = set()
    seen: set[Node] = set()
    node: Node = head
    while node != RDF.nil and node not in seen:
        seen.add(node)
        firsts = list(graph.objects(node, RDF.first))
        if not firsts:
            break
        first = firsts[0]
        if isinstance(first, URIRef) and not str(first).startswith(_RESTRICTION_NS):
            members.add(str(first))
        rests = list(graph.objects(node, RDF.rest))
        if not rests:
            break
        node = rests[0]
    return tuple(sorted(members))


def class_set_node_ids(graph: Graph) -> set[str]:
    """String ids of every node that is an anonymous class set in ``graph``.

    A node is a class set iff it is the subject of an ``owl:unionOf`` or
    ``owl:intersectionOf`` triple. Used by Components 07 and 08 to recognize (and
    step aside for) the targets this module decodes.
    """
    ids: set[str] = set()
    for op_predicate, _ in _OPERATORS:
        for subject in graph.subjects(op_predicate, None):
            ids.add(str(subject))
    return ids


def owned_keys(a: OntologySnapshot, b: OntologySnapshot) -> set[tuple[str, str]]:
    """``(attached_to, via_predicate)`` keys owned by the class-set slice on either side.

    A key is owned when *either* snapshot attaches an anonymous class set to that
    entity via that predicate. Components 07 (hierarchy) and 08 (restrictions,
    domain/range, equivalent-class) consult this so the flattening / unflattening
    cases — where one side is a bare named relation and the other is a union — are
    handled wholly by :mod:`.class_sets` rather than double-reported.
    """
    keys: set[tuple[str, str]] = set()
    for snapshot in (a, b):
        graph = snapshot.graph
        node_ids = class_set_node_ids(graph)
        for predicate, via in _ATTACH_PREDICATES:
            for subject, _, target in graph.triples((None, predicate, None)):
                if isinstance(subject, URIRef) and str(target) in node_ids:
                    keys.add((str(subject), via))
    return keys
