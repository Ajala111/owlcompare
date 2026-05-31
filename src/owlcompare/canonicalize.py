"""Canonicalization passes for :class:`OntologySnapshot`.

Implements the four-pass pipeline described in ``specs/04-canonicalize.md``:

1. Blank node label canonicalization via W3C RDFC-1.0 (rdflib).
2. Restriction reification — anonymous class expressions get content-addressed
   ``urn:owlcompare:restriction:<sha256>`` IRIs.
3. RDF list collapsing — list head/tail blank nodes get content-addressed
   ``urn:owlcompare:list:<sha256>`` IRIs.
4. Deterministic triple ordering for stable serialization.

Each pass is a small private function from ``Graph`` to ``Graph`` so the
pipeline composes cleanly and every stage is independently testable.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace

import rdflib
from rdflib import OWL, RDF
from rdflib.compare import to_canonical_graph
from rdflib.term import BNode, Literal, Node, URIRef

from owlcompare.exceptions import CanonicalizationError
from owlcompare.model import OntologySnapshot

logger = logging.getLogger(__name__)

# Q1 (resolved): synthetic URN namespaces — clearly not HTTP-resolvable and
# never collide with user IRIs.
_RESTRICTION_NS = "urn:owlcompare:restriction:"
_LIST_NS = "urn:owlcompare:list:"

# Blank nodes typed as either of these are treated as anonymous class
# expressions and reified. ``owl:Class`` covers unions/intersections/oneOf
# wrappers; ``owl:Restriction`` covers the property-restriction family.
_CLASS_EXPR_TYPES: frozenset[URIRef] = frozenset({OWL.Restriction, OWL.Class})

# Hash placeholder for the back-edge in a self-referential class expression.
# Stable string → equivalent cyclic inputs produce equivalent hashes.
_CYCLE_PLACEHOLDER = "__owlcompare_cycle__"


@dataclass(frozen=True, slots=True)
class CanonicalizeOptions:
    """Toggle individual passes for debugging or differential testing."""

    canonicalize_blank_nodes: bool = True
    reify_restrictions: bool = True
    collapse_lists: bool = True
    sort_triples: bool = True
    algorithm: str = "rdfc-1.0"


def canonicalize(
    snapshot: OntologySnapshot,
    options: CanonicalizeOptions | None = None,
) -> OntologySnapshot:
    """Return a canonicalized copy of ``snapshot``.

    The returned snapshot has the same entities (same IRIs) but a normalized
    graph: blank nodes have stable labels, anonymous restrictions are reified
    with deterministic identifiers, RDF lists are collapsed, and triples are
    sorted. The original snapshot is not modified.

    Args:
        snapshot: The loader's output. Must be the default graph only.
        options: Per-pass toggles. Defaults to all passes enabled.

    Returns:
        A new :class:`OntologySnapshot` with ``canonical=True`` and a
        normalized graph.

    Raises:
        CanonicalizationError: if the input contains named graphs.
    """
    opts = options or CanonicalizeOptions()
    _reject_named_graphs(snapshot.graph)

    graph = snapshot.graph
    if opts.canonicalize_blank_nodes:
        graph = _canonicalize_blank_nodes(graph)
    if opts.reify_restrictions:
        graph = _reify_restrictions(graph)
    if opts.collapse_lists:
        graph = _collapse_lists(graph)
    if opts.sort_triples:
        graph = _sort_triples(graph)

    _rebind_prefixes(graph, snapshot.prefixes)
    return replace(snapshot, graph=graph, canonical=True)


def _reject_named_graphs(graph: rdflib.Graph) -> None:
    """Raise if the input carries named (non-default) contexts.

    Plain ``rdflib.Graph`` has no contexts; only Dataset/ConjunctiveGraph do.
    v1 deliberately covers the default graph only — see spec § Edge cases.
    """
    if isinstance(graph, rdflib.Dataset):
        default_id = graph.default_graph.identifier
        contexts = graph.graphs()
    elif isinstance(graph, rdflib.ConjunctiveGraph):
        default_id = graph.default_context.identifier
        contexts = graph.contexts()
    else:
        return
    for ctx in contexts:
        if ctx.identifier != default_id and len(ctx) > 0:
            raise CanonicalizationError("named graphs not supported in v1")


def _rebind_prefixes(graph: rdflib.Graph, prefixes: dict[str, str]) -> None:
    for prefix, namespace in prefixes.items():
        graph.bind(prefix, namespace, replace=True)


def _empty_graph() -> rdflib.Graph:
    return rdflib.Graph(bind_namespaces="none")


# ---------------------------------------------------------------------------
# Pass 1 — Blank node canonicalization (RDFC-1.0)
# ---------------------------------------------------------------------------


def _canonicalize_blank_nodes(graph: rdflib.Graph) -> rdflib.Graph:
    """Relabel blank nodes via W3C RDFC-1.0.

    Identical-up-to-isomorphism graphs end up with identical blank node
    labels. Returns a fresh graph; the input is not modified.
    """
    if len(graph) == 0:
        return _empty_graph()
    canonical = to_canonical_graph(graph)
    result = _empty_graph()
    for triple in canonical:
        result.add(triple)
    return result


# ---------------------------------------------------------------------------
# Pass 2 — Restriction reification
# ---------------------------------------------------------------------------


def _term_repr(term: Node, bnode_labels: dict[BNode, str]) -> str:
    """Stable string representation of a term for hashing.

    Blank nodes use a separately-computed content hash (or RDFC-1.0 label as
    fallback); IRIs and literals use n3 form.
    """
    if isinstance(term, BNode):
        return f"_:{bnode_labels.get(term, str(term))}"
    if isinstance(term, (URIRef, Literal)):
        return term.n3()
    return str(term)


def _hash_class_expr(
    bnode: BNode,
    graph: rdflib.Graph,
    cache: dict[BNode, str],
    visiting: frozenset[BNode],
) -> str:
    """Content-hash for an anonymous class expression blank node.

    Recurses through nested anonymous class expressions and uses the
    RDFC-1.0-stable blank node labels for non-class-expression blank nodes
    (e.g., list nodes), so cross-ontology comparison is well-defined.
    """
    if bnode in cache:
        return cache[bnode]
    if bnode in visiting:
        return _CYCLE_PLACEHOLDER
    next_visiting = visiting | {bnode}

    pairs: list[tuple[str, str]] = []
    for predicate, obj in graph.predicate_objects(bnode):
        if isinstance(obj, BNode) and _is_class_expr_bnode(obj, graph):
            obj_repr = f"_:{_hash_class_expr(obj, graph, cache, next_visiting)}"
        else:
            obj_repr = _term_repr(obj, {})
        pairs.append((predicate.n3(), obj_repr))
    pairs.sort()
    content = "|".join(f"{p}={o}" for p, o in pairs)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    cache[bnode] = digest
    return digest


def _is_class_expr_bnode(node: Node, graph: rdflib.Graph) -> bool:
    if not isinstance(node, BNode):
        return False
    return any(type_iri in _CLASS_EXPR_TYPES for type_iri in graph.objects(node, RDF.type))


def _reify_restrictions(graph: rdflib.Graph) -> rdflib.Graph:
    """Replace anonymous class-expression blank nodes with content URIs."""
    targets: set[BNode] = set()
    for subject in graph.subjects(RDF.type):
        if _is_class_expr_bnode(subject, graph):
            assert isinstance(subject, BNode)
            targets.add(subject)

    if not targets:
        return _copy_graph(graph)

    cache: dict[BNode, str] = {}
    # Sort for deterministic recursion across runs.
    for bnode in sorted(targets, key=str):
        _hash_class_expr(bnode, graph, cache, frozenset())

    mapping: dict[BNode, URIRef] = {
        bnode: URIRef(f"{_RESTRICTION_NS}{cache[bnode]}") for bnode in targets
    }
    return _rewrite_bnodes(graph, mapping)


# ---------------------------------------------------------------------------
# Pass 3 — RDF list collapsing
# ---------------------------------------------------------------------------


def _hash_list_node(
    node: Node,
    graph: rdflib.Graph,
    cache: dict[BNode, str],
    visiting: frozenset[BNode],
) -> str | None:
    """Content-hash for a list node, or ``None`` if the list is malformed."""
    if node == RDF.nil:
        return "nil"
    if not isinstance(node, BNode):
        # A list-tail pointing to a non-list URI is unusual but stable.
        return _term_repr(node, {})
    if node in cache:
        return cache[node]
    if node in visiting:
        return None  # cycle — treat as malformed

    firsts = list(graph.objects(node, RDF.first))
    rests = list(graph.objects(node, RDF.rest))
    if len(firsts) != 1 or len(rests) != 1:
        return None

    first_repr = _term_repr(firsts[0], {})
    rest_repr = _hash_list_node(rests[0], graph, cache, visiting | {node})
    if rest_repr is None:
        return None

    digest = hashlib.sha256(f"{first_repr}|{rest_repr}".encode()).hexdigest()
    cache[node] = digest
    return digest


def _collapse_lists(graph: rdflib.Graph) -> rdflib.Graph:
    """Replace RDF-list blank nodes with content-addressed URIs."""
    candidates: set[BNode] = set()
    for subject in graph.subjects(RDF.first):
        if isinstance(subject, BNode):
            candidates.add(subject)

    if not candidates:
        return _copy_graph(graph)

    cache: dict[BNode, str] = {}
    valid: set[BNode] = set()
    for bnode in sorted(candidates, key=str):
        if _hash_list_node(bnode, graph, cache, frozenset()) is not None:
            valid.add(bnode)

    malformed = candidates - valid
    if malformed:
        logger.info("Found %d malformed RDF list node(s); leaving as-is", len(malformed))

    mapping: dict[BNode, URIRef] = {bnode: URIRef(f"{_LIST_NS}{cache[bnode]}") for bnode in valid}
    return _rewrite_bnodes(graph, mapping)


# ---------------------------------------------------------------------------
# Pass 4 — Triple sorting
# ---------------------------------------------------------------------------


def _sort_triples(graph: rdflib.Graph) -> rdflib.Graph:
    """Insert triples into a new graph in a deterministic order.

    Order does not affect set semantics; it does affect serialization, which
    is the whole point: byte-identical input → byte-identical output.
    """
    new_graph = _empty_graph()
    for triple in sorted(graph, key=_triple_sort_key):
        new_graph.add(triple)
    return new_graph


def _triple_sort_key(triple: tuple[Node, Node, Node]) -> tuple[str, str, str]:
    s, p, o = triple
    return (s.n3(), p.n3(), o.n3())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rewrite_bnodes(graph: rdflib.Graph, mapping: dict[BNode, URIRef]) -> rdflib.Graph:
    new_graph = _empty_graph()
    for s, p, o in graph:
        new_s = mapping.get(s, s) if isinstance(s, BNode) else s
        new_o = mapping.get(o, o) if isinstance(o, BNode) else o
        new_graph.add((new_s, p, new_o))
    return new_graph


def _copy_graph(graph: rdflib.Graph) -> rdflib.Graph:
    new_graph = _empty_graph()
    for triple in graph:
        new_graph.add(triple)
    return new_graph


__all__ = (
    "CanonicalizeOptions",
    "canonicalize",
)
