"""Indexed subClassOf / subPropertyOf views for the hierarchy diff (Component 07).

Builds, per snapshot, direct-parent and direct-child maps for both the class
hierarchy (``rdfs:subClassOf``) and the property hierarchy
(``rdfs:subPropertyOf``). Only edges between *named* entities are kept:
blank-node and synthetic (``urn:owlcompare:*``) endpoints are class expressions
or reified restrictions, not hierarchy entities, so they are filtered out here
and left for Component 08. See ``specs/07-structural-hierarchy.md`` § Step 1.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from rdflib import RDFS
from rdflib.term import Node, URIRef

from owlcompare.model import OntologySnapshot

# Canonicalization (Component 04) mints synthetic URNs — ``urn:owlcompare:restriction:…``
# and ``urn:owlcompare:list:…`` — for reified class expressions and RDF lists.
# These can legitimately sit in the object slot of a ``subClassOf`` triple, but
# they are not entities, so the hierarchy index excludes them; Component 08 owns
# restriction edges.
_SYNTHETIC_PREFIX = "urn:owlcompare:"


@dataclass(frozen=True, slots=True)
class HierarchyIndex:
    """Indexed asserted subClassOf / subPropertyOf graph for one snapshot."""

    class_parents: dict[str, frozenset[str]]
    class_children: dict[str, frozenset[str]]
    property_parents: dict[str, frozenset[str]]
    property_children: dict[str, frozenset[str]]


def build(snapshot: OntologySnapshot) -> HierarchyIndex:
    """Scan ``snapshot``'s graph for named-entity hierarchy edges.

    Args:
        snapshot: The (typically canonical) snapshot to index.

    Returns:
        A :class:`HierarchyIndex` with direct parent/child maps for the class
        and property hierarchies, excluding blank-node and synthetic endpoints.
    """
    class_parents = _collect(snapshot, RDFS.subClassOf)
    property_parents = _collect(snapshot, RDFS.subPropertyOf)
    return HierarchyIndex(
        class_parents=class_parents,
        class_children=_invert(class_parents),
        property_parents=property_parents,
        property_children=_invert(property_parents),
    )


def _collect(snapshot: OntologySnapshot, predicate: URIRef) -> dict[str, frozenset[str]]:
    """Map each child IRI to the frozenset of its direct parents for one predicate."""
    parents: dict[str, set[str]] = defaultdict(set)
    for subject, _, obj in snapshot.graph.triples((None, predicate, None)):
        if not _is_named_entity(subject) or not _is_named_entity(obj):
            continue
        parents[str(subject)].add(str(obj))
    return {child: frozenset(parent_set) for child, parent_set in parents.items()}


def _invert(parents: dict[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    """Build the child map (parent IRI -> frozenset of direct child IRIs)."""
    children: dict[str, set[str]] = defaultdict(set)
    for child, parent_set in parents.items():
        for parent in parent_set:
            children[parent].add(child)
    return {parent: frozenset(child_set) for parent, child_set in children.items()}


def _is_named_entity(term: Node) -> bool:
    """True if ``term`` is a named IRI that is not a canonicalization synthetic URN."""
    return isinstance(term, URIRef) and not str(term).startswith(_SYNTHETIC_PREFIX)
