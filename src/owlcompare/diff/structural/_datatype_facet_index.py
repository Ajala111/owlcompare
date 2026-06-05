"""Indexed view of datatype facet restrictions (Component 12.5).

Decodes the OWL 2 ``owl:onDatatype`` + ``owl:withRestrictions`` pattern attached
to a data property's ``rdfs:range`` into a flat, diffable record. After
canonicalization a ``[ a rdfs:Datatype ; owl:onDatatype xsd:decimal ;
owl:withRestrictions ( [ xsd:minInclusive 0 ] [ xsd:maxInclusive 327670 ] ) ]``
stays a blank node (``rdfs:Datatype`` is not reified into a URN), with its
``owl:withRestrictions`` list collapsed to a ``urn:owlcompare:list:<sha>`` chain
whose cells point at the (still blank) facet nodes. This module reads through
that shape; ``raw_urn`` is ``None`` for the usual blank-node case. See
``specs/12.5-anonymous-structures.md`` § Part 3.

A union *of* datatypes (``rdfs:Datatype`` with ``owl:unionOf``) carries no
``owl:onDatatype`` and is therefore *not* a facet restriction — it is decoded by
:mod:`._class_set_index` instead, so the two decoders never overlap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rdflib import OWL, RDF, RDFS, XSD, Graph
from rdflib.term import Literal as RDFLiteral
from rdflib.term import Node, URIRef

from owlcompare.model import OntologySnapshot

# Facet predicate → the ``DatatypeFacets`` field it populates. Numeric bounds plus
# the length / pattern facets OWL 2 § 7.1 allows on the supported datatypes.
_FACET_FIELDS: dict[URIRef, str] = {
    XSD.minInclusive: "min_inclusive",
    XSD.maxInclusive: "max_inclusive",
    XSD.minExclusive: "min_exclusive",
    XSD.maxExclusive: "max_exclusive",
    XSD.length: "length",
    XSD.minLength: "min_length",
    XSD.maxLength: "max_length",
    XSD.pattern: "pattern",
}

# Facet field names in a stable display order (matches the bound-tightening reading
# order min → max, then length family, then pattern).
_FIELD_ORDER: tuple[str, ...] = (
    "min_inclusive",
    "max_inclusive",
    "min_exclusive",
    "max_exclusive",
    "length",
    "min_length",
    "max_length",
    "pattern",
)
_LENGTH_FIELDS = frozenset({"length", "min_length", "max_length"})

# JSON-safe facet value: numeric bounds normalize to int/float (never Decimal, which
# is not JSON-serializable), lengths to int, pattern to str.
FacetValue = int | float | str


@dataclass(frozen=True, slots=True)
class DatatypeFacets:
    """Decoded datatype facet restriction on a property's range."""

    property_iri: str
    base_datatype: str  # IRI of the owl:onDatatype base, e.g. xsd:decimal
    min_inclusive: int | float | None
    max_inclusive: int | float | None
    min_exclusive: int | float | None
    max_exclusive: int | float | None
    length: int | None
    min_length: int | None
    max_length: int | None
    pattern: str | None
    raw_urn: str | None  # the datatype node's URN, or None for the usual blank node

    def present_facets(self) -> dict[str, FacetValue]:
        """The non-``None`` facets as a ``{field_name: value}`` dict in display order."""
        values: dict[str, FacetValue] = {}
        for field in _FIELD_ORDER:
            value = getattr(self, field)
            if value is not None:
                values[field] = value
        return values


def build(snapshot: OntologySnapshot) -> dict[str, DatatypeFacets]:
    """Decode every ``owl:onDatatype`` + ``owl:withRestrictions`` range restriction.

    Args:
        snapshot: The (typically canonical) snapshot to index.

    Returns:
        A ``{property_iri: DatatypeFacets}`` map. Only data properties whose
        ``rdfs:range`` points at an ``rdfs:Datatype`` node carrying an
        ``owl:onDatatype`` are included; union-of-datatypes ranges (no
        ``owl:onDatatype``) are left to :mod:`._class_set_index`.
    """
    graph = snapshot.graph
    result: dict[str, DatatypeFacets] = {}
    for prop, _, node in graph.triples((None, RDFS.range, None)):
        if not isinstance(prop, URIRef):
            continue
        if (node, RDF.type, RDFS.Datatype) not in graph:
            continue
        base_objects = list(graph.objects(node, OWL.onDatatype))
        if not base_objects:
            continue  # no onDatatype → a union-of-datatypes, not a facet restriction
        facets = _read_facets(graph, node)
        result[str(prop)] = DatatypeFacets(
            property_iri=str(prop),
            base_datatype=str(base_objects[0]),
            raw_urn=str(node) if isinstance(node, URIRef) else None,
            **facets,
        )
    return result


def _read_facets(graph: Graph, node: Node) -> dict[str, Any]:
    """Read the ``owl:withRestrictions`` facet list into the ``DatatypeFacets`` fields.

    Returns ``dict[str, Any]`` (rather than the precise per-field union) so the
    ``**facets`` spread into :class:`DatatypeFacets` type-checks; each value is
    already narrowed to the field's type by :func:`_decode_value`.
    """
    fields: dict[str, Any] = {name: None for name in _FIELD_ORDER}
    for list_head in graph.objects(node, OWL.withRestrictions):
        for facet_node in _read_list_members(graph, list_head):
            for predicate, obj in graph.predicate_objects(facet_node):
                field = _FACET_FIELDS.get(predicate) if isinstance(predicate, URIRef) else None
                if field is not None:
                    fields[field] = _decode_value(field, obj)
    return fields


def _read_list_members(graph: Graph, head: Node) -> list[Node]:
    """Walk a canonicalized RDF list, returning each cell's ``rdf:first`` object."""
    members: list[Node] = []
    seen: set[Node] = set()
    node: Node = head
    while node != RDF.nil and node not in seen:
        seen.add(node)
        firsts = list(graph.objects(node, RDF.first))
        if not firsts:
            break
        members.append(firsts[0])
        rests = list(graph.objects(node, RDF.rest))
        if not rests:
            break
        node = rests[0]
    return members


def _decode_value(field: str, obj: Node) -> int | float | str | None:
    """Decode a facet literal into a JSON-safe value (int/float for bounds, str pattern)."""
    if field == "pattern":
        return str(obj)
    if not isinstance(obj, RDFLiteral):
        return None
    if field in _LENGTH_FIELDS:
        try:
            return int(obj)
        except (TypeError, ValueError):
            return None
    return _number(obj)


def _number(obj: RDFLiteral) -> int | float | None:
    """A numeric literal as ``int`` when integral, else ``float`` (never Decimal)."""
    try:
        value = float(obj)
    except (TypeError, ValueError):
        return None
    return int(value) if value.is_integer() else value
