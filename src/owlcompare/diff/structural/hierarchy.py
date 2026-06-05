"""Layer 1 — hierarchy structural diff (subClassOf / subPropertyOf).

Consolidates the raw subClassOf / subPropertyOf triple delta into meaningful
hierarchy events: a class or property gained or lost a parent, was reparented
(with a generalization / specialization / lateral direction hint), or — rarely —
sits on a cycle the diff introduced. Runs after the entity-level slice
(Component 06) sharing one :class:`SubsumptionRegistry`: edges that merely
accompany a newly-added or newly-removed entity are deferred to that entity's
change rather than re-reported here. See ``specs/07-structural-hierarchy.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from rdflib import RDF, RDFS
from rdflib.namespace import NamespaceManager
from rdflib.term import URIRef

from owlcompare.exceptions import DiffError
from owlcompare.model import OntologySnapshot, shorten_iri

from .._common import Change, DiffOptions, Severity
from .._subsumption import SubsumptionRegistry
from ._class_set_index import owned_keys as class_set_owned_keys
from ._hierarchy_index import HierarchyIndex, build

logger = logging.getLogger(__name__)

# Direction-detection recursion cap (Q2): real hierarchies top out around 20-30
# deep, so 50 is comfortable margin; anything past it almost certainly indicates
# a cycle, and the walk gracefully bails out to "lateral".
_MAX_DEPTH = 50

_SUBCLASS_OF = str(RDFS.subClassOf)
_SUBPROPERTY_OF = str(RDFS.subPropertyOf)
_RDF_TYPE = str(RDF.type)

# Ordering within the structural section (spec § Ordering): reparents first, then
# parent-added, then parent-removed, then cycles; ties broken by subject IRI.
_KIND_RANK: dict[str, int] = {
    "class_reparented": 0,
    "property_reparented": 1,
    "class_parent_added": 2,
    "property_parent_added": 3,
    "class_parent_removed": 4,
    "property_parent_removed": 5,
    "class_hierarchy_cycle_introduced": 6,
}

Direction = Literal["generalization", "specialization", "lateral"]
ParentMap = dict[str, frozenset[str]]
Layer0Index = dict[tuple[str | None, str | None, str], list[Change]]


@dataclass(slots=True)
class _Ctx:
    """Bundle of per-call state threaded through the hierarchy diff helpers."""

    a: OntologySnapshot
    b: OntologySnapshot
    index_a: HierarchyIndex
    index_b: HierarchyIndex
    prefixes: dict[str, str]
    layer0_index: Layer0Index
    registry: SubsumptionRegistry
    nsm_a: NamespaceManager
    nsm_b: NamespaceManager
    # (entity, "rdfs:subClassOf") keys owned by Component 12.5's class-set slice:
    # a subClassOf union on either side, whose bare-named flattened form must not
    # be re-reported here as a plain parent edit.
    class_set_keys: set[tuple[str, str]]


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    layer0_changes: list[Change],
    registry: SubsumptionRegistry,
    options: DiffOptions | None = None,
) -> list[Change]:
    """Compute Layer 1 hierarchy-level differences (subClassOf, subPropertyOf).

    Updates ``registry`` in-place to mark Layer 0 changes that are now explained
    by the structural changes returned here (and defers edges belonging to a
    newly added/removed entity to that entity's Component 06 change).

    Args:
        a: Baseline snapshot (canonicalized).
        b: Comparison snapshot (canonicalized).
        layer0_changes: Component 05's output, used for subsumption tracking.
        registry: Shared subsumption registry, mutated in place.
        options: Reserved for future layer knobs; unused by this slice.

    Returns:
        A list of ``Change`` records with ``layer="structural"``. Kinds include
        ``class_parent_added``, ``class_parent_removed``, ``class_reparented``,
        the ``property_*`` analogues, and ``class_hierarchy_cycle_introduced``.

    Raises:
        DiffError: if either snapshot is not canonicalized.
    """
    del options  # no hierarchy-slice knobs yet; kept for a uniform layer signature
    if not a.canonical or not b.canonical:
        raise DiffError("inputs must be canonicalized first")

    ctx = _Ctx(
        a=a,
        b=b,
        index_a=build(a),
        index_b=build(b),
        prefixes={**a.prefixes, **b.prefixes},
        layer0_index=_index_layer0(layer0_changes),
        registry=registry,
        nsm_a=a.graph.namespace_manager,
        nsm_b=b.graph.namespace_manager,
        class_set_keys=class_set_owned_keys(a, b),
    )

    cycle_paths, cycle_edges = _detect_introduced_cycles(ctx.index_a, ctx.index_b)
    changes: list[Change] = list(_emit_cycles(ctx, cycle_paths))
    changes.extend(_diff_axis(ctx, is_class=True, cycle_edges=cycle_edges))
    changes.extend(_diff_axis(ctx, is_class=False, cycle_edges=set()))

    changes.sort(key=lambda c: (_KIND_RANK[c.kind], c.subject or ""))
    return changes


# --------------------------------------------------------------------------- #
# Per-axis (class / property) diff
# --------------------------------------------------------------------------- #


def _diff_axis(ctx: _Ctx, *, is_class: bool, cycle_edges: set[tuple[str, str]]) -> list[Change]:
    """Diff one hierarchy axis (classes via subClassOf, properties via subPropertyOf)."""
    parents_a = ctx.index_a.class_parents if is_class else ctx.index_a.property_parents
    parents_b = ctx.index_b.class_parents if is_class else ctx.index_b.property_parents
    predicate = _SUBCLASS_OF if is_class else _SUBPROPERTY_OF

    changes: list[Change] = []
    for iri in sorted(set(parents_a) | set(parents_b)):
        # A subClassOf union (on either side) is Component 12.5's territory; its
        # flattened bare-named form must not surface here as a parent edit.
        if is_class and (iri, "rdfs:subClassOf") in ctx.class_set_keys:
            continue
        pa = parents_a.get(iri, frozenset())
        pb = parents_b.get(iri, frozenset())
        removed = pa - pb
        # Edges that close a freshly-introduced cycle are reported as cycle
        # changes (Step 4), not as ordinary parent additions.
        added = (pb - pa) - {parent for child, parent in cycle_edges if child == iri}
        if not removed and not added:
            continue
        if _defer_to_entity_change(ctx, iri, is_class, predicate, added=added, removed=removed):
            continue
        changes.extend(
            _emit_axis_changes(
                ctx, iri, is_class=is_class, pa=pa, pb=pb, removed=removed, added=added
            )
        )
    return changes


def _emit_axis_changes(
    ctx: _Ctx,
    iri: str,
    *,
    is_class: bool,
    pa: frozenset[str],
    pb: frozenset[str],
    removed: frozenset[str],
    added: frozenset[str],
) -> list[Change]:
    """Dispatch to reparent / parent-added / parent-removed for one entity."""
    if removed and added:
        return [
            _reparent_change(
                ctx, iri, is_class=is_class, pa=pa, pb=pb, removed=removed, added=added
            )
        ]
    if added:
        return [
            _parent_added_change(ctx, iri, parent, is_class=is_class) for parent in sorted(added)
        ]
    return [
        _parent_removed_change(ctx, iri, parent, is_class=is_class, has_others=bool(pb))
        for parent in sorted(removed)
    ]


# --------------------------------------------------------------------------- #
# Defer edges of newly added / removed entities to Component 06's change
# --------------------------------------------------------------------------- #


def _defer_to_entity_change(
    ctx: _Ctx,
    iri: str,
    is_class: bool,
    predicate: str,
    *,
    added: frozenset[str],
    removed: frozenset[str],
) -> bool:
    """Skip emission and subsume edges under the entity's add/remove change.

    When the entity itself was introduced or dropped (Component 06 already
    emitted ``*_added`` / ``*_removed``), its parent assertions are part of that
    introduction/removal. We read the registry to find Component 06's change id
    for the entity and register the hierarchy triples under it, instead of
    emitting a standalone hierarchy change (spec § Edge cases).
    """
    if _in_entities(iri, ctx.b, is_class) and not _in_entities(iri, ctx.a, is_class):
        _subsume_under_entity(ctx, iri, predicate, added, added=True)
        return True
    if _in_entities(iri, ctx.a, is_class) and not _in_entities(iri, ctx.b, is_class):
        _subsume_under_entity(ctx, iri, predicate, removed, added=False)
        return True
    return False


def _in_entities(iri: str, snapshot: OntologySnapshot, is_class: bool) -> bool:
    """Whether ``iri`` is declared as the relevant kind (class, or any property)."""
    entities = snapshot.entities
    if is_class:
        return iri in entities.classes
    return (
        iri in entities.object_properties
        or iri in entities.data_properties
        or iri in entities.annotation_properties
    )


def _subsume_under_entity(
    ctx: _Ctx, iri: str, predicate: str, parents: frozenset[str], *, added: bool
) -> None:
    """Register the entity's hierarchy edges under its Component 06 change id."""
    triple_kind = "triple_added" if added else "triple_removed"
    entity_change_id = _entity_change_id(ctx, iri, triple_kind)
    if entity_change_id is None:
        return
    nsm = ctx.nsm_b if added else ctx.nsm_a
    edges: list[Change] = []
    for parent in parents:
        edges.extend(_match_edge(ctx, iri, predicate, parent, triple_kind, nsm))
    if edges:
        ctx.registry.register(entity_change_id, edges)


def _entity_change_id(ctx: _Ctx, iri: str, triple_kind: str) -> str | None:
    """The Component 06 change id that explains ``iri``'s ``rdf:type`` triple, if any."""
    for change in ctx.layer0_index.get((iri, _RDF_TYPE, triple_kind), []):
        explainers = ctx.registry.explainers(SubsumptionRegistry.change_id(change))
        if explainers:
            return explainers[0]
    return None


# --------------------------------------------------------------------------- #
# Change builders
# --------------------------------------------------------------------------- #


def _reparent_change(
    ctx: _Ctx,
    iri: str,
    *,
    is_class: bool,
    pa: frozenset[str],
    pb: frozenset[str],
    removed: frozenset[str],
    added: frozenset[str],
) -> Change:
    """Build a ``*_reparented`` change with direction hint and full before/after."""
    parents_a = ctx.index_a.class_parents if is_class else ctx.index_a.property_parents
    parents_b = ctx.index_b.class_parents if is_class else ctx.index_b.property_parents
    predicate = _SUBCLASS_OF if is_class else _SUBPROPERTY_OF
    kind = "class_reparented" if is_class else "property_reparented"
    direction = _reparent_direction(removed, added, parents_a, parents_b)
    severity: Severity = "non_breaking" if direction == "generalization" else "breaking"

    summary = (
        f"{_noun(is_class)} {_short(ctx, iri)} reparented: "
        f"{_format_set(ctx, removed, added)} → {_format_set(ctx, added, removed)} ({direction})"
    )
    details: dict[str, object] = {
        "entity_iri": iri,
        "entity_kind": _entity_kind(is_class),
        "parents_before": sorted(pa),
        "parents_after": sorted(pb),
        "direction": direction,
    }
    subsumed = [
        *_edges_for(ctx, iri, predicate, removed, "triple_removed", ctx.nsm_a),
        *_edges_for(ctx, iri, predicate, added, "triple_added", ctx.nsm_b),
    ]
    return _finalize(kind, severity, iri, summary, details, subsumed, ctx.registry)


def _parent_added_change(ctx: _Ctx, iri: str, parent: str, *, is_class: bool) -> Change:
    """Build a ``*_parent_added`` change (severity keyed on direction)."""
    parents_b = ctx.index_b.class_parents if is_class else ctx.index_b.property_parents
    predicate = _SUBCLASS_OF if is_class else _SUBPROPERTY_OF
    kind = "class_parent_added" if is_class else "property_parent_added"
    direction = _parent_added_direction(iri, parent, parents_b)
    severity: Severity = "additive" if direction == "generalization" else "non_breaking"

    summary = f"{_noun(is_class)} {_short(ctx, iri)} gained parent {_short(ctx, parent)}"
    details: dict[str, object] = {
        "entity_iri": iri,
        "entity_kind": _entity_kind(is_class),
        "parent_iri": parent,
    }
    subsumed = _match_edge(ctx, iri, predicate, parent, "triple_added", ctx.nsm_b)
    return _finalize(kind, severity, iri, summary, details, subsumed, ctx.registry)


def _parent_removed_change(
    ctx: _Ctx, iri: str, parent: str, *, is_class: bool, has_others: bool
) -> Change:
    """Build a ``*_parent_removed`` change (breaking only when it orphans the entity)."""
    predicate = _SUBCLASS_OF if is_class else _SUBPROPERTY_OF
    kind = "class_parent_removed" if is_class else "property_parent_removed"
    severity: Severity = "non_breaking" if has_others else "breaking"

    summary = f"{_noun(is_class)} {_short(ctx, iri)} lost parent {_short(ctx, parent)}"
    details: dict[str, object] = {
        "entity_iri": iri,
        "entity_kind": _entity_kind(is_class),
        "parent_iri": parent,
    }
    subsumed = _match_edge(ctx, iri, predicate, parent, "triple_removed", ctx.nsm_a)
    return _finalize(kind, severity, iri, summary, details, subsumed, ctx.registry)


def _finalize(
    kind: str,
    severity: Severity,
    subject: str,
    summary: str,
    details: dict[str, object],
    subsumed: list[Change],
    registry: SubsumptionRegistry,
) -> Change:
    """Attach subsumption + change_id to a hierarchy change and register it."""
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
        registry.register(change_id, subsumed)
    else:
        logger.debug("hierarchy change %s has no matching Layer 0 changes", change_id)
    return change


# --------------------------------------------------------------------------- #
# Direction detection (depth-limited, cycle-safe DFS)
# --------------------------------------------------------------------------- #


def _reparent_direction(
    removed: frozenset[str], added: frozenset[str], parents_a: ParentMap, parents_b: ParentMap
) -> Direction:
    """Classify a reparent as generalization, specialization, or lateral.

    Specialization: walk the *new* hierarchy up from the new parent(s) and reach
    an old parent (the entity moved down). Generalization: walk the *old*
    hierarchy up from the old parent(s) and reach a new parent (it moved up). A
    multi-to-multi move, or an ambiguous/incomparable one, is lateral (Q1).
    """
    if len(removed) > 1 and len(added) > 1:
        return "lateral"
    specialization = _reachable(parents_b, added, removed)
    generalization = _reachable(parents_a, removed, added)
    if specialization and not generalization:
        return "specialization"
    if generalization and not specialization:
        return "generalization"
    return "lateral"


def _parent_added_direction(iri: str, parent: str, parents_b: ParentMap) -> Direction:
    """Direction of a newly-added parent relative to the entity's other parents.

    Generalization (broader supertype, additive): the added parent is an ancestor
    of a retained parent. Specialization: the added parent is a descendant of a
    retained parent. Otherwise lateral (a new, incomparable classification axis).
    """
    others = parents_b.get(iri, frozenset()) - {parent}
    if not others:
        return "lateral"
    if _reachable(parents_b, others, frozenset({parent})):
        return "generalization"
    if _reachable(parents_b, frozenset({parent}), others):
        return "specialization"
    return "lateral"


def _reachable(parents_map: ParentMap, starts: frozenset[str], targets: frozenset[str]) -> bool:
    """Whether any target is an ancestor of any start (walking parent edges up)."""
    target_set = set(targets)
    return any(_can_reach(parents_map, start, target_set) for start in starts)


def _can_reach(parents_map: ParentMap, start: str, targets: set[str]) -> bool:
    """Depth-limited, cycle-safe ancestor search from ``start`` toward ``targets``."""
    visited = {start}
    stack: list[tuple[str, int]] = [(start, 0)]
    while stack:
        node, depth = stack.pop()
        if depth >= _MAX_DEPTH:
            return False  # graceful bail: treat as not reachable -> lateral
        for nxt in parents_map.get(node, frozenset()):
            if nxt in targets:
                return True
            if nxt in visited:
                continue
            visited.add(nxt)
            stack.append((nxt, depth + 1))
    return False


# --------------------------------------------------------------------------- #
# Cycle detection (Step 4)
# --------------------------------------------------------------------------- #


def _detect_introduced_cycles(
    index_a: HierarchyIndex, index_b: HierarchyIndex
) -> tuple[list[list[str]], set[tuple[str, str]]]:
    """Find class-hierarchy cycles that a newly-added subClassOf edge closes.

    Returns ``(paths, cycle_edges)`` where each path is ``[X, ..., X]`` and
    ``cycle_edges`` is the set of new ``(child, parent)`` edges that close a
    cycle. Cycles whose edges all pre-exist in A are not flagged.
    """
    a_parents = index_a.class_parents
    b_parents = index_b.class_parents
    added_edges = sorted(
        (child, parent)
        for child, parents in b_parents.items()
        for parent in parents
        if parent not in a_parents.get(child, frozenset())
    )
    paths: list[list[str]] = []
    cycle_edges: set[tuple[str, str]] = set()
    seen: set[frozenset[str]] = set()
    for child, parent in added_edges:
        path_up = _find_path(b_parents, parent, child)
        if path_up is None:
            continue
        cycle = [child, *path_up]  # child -> parent -> ... -> child
        node_key = frozenset(cycle[:-1])
        if node_key in seen:
            continue
        seen.add(node_key)
        paths.append(cycle)
        cycle_edges.add((child, parent))
    return paths, cycle_edges


def _find_path(parents_map: ParentMap, start: str, target: str) -> list[str] | None:
    """Return a parent-edge path ``[start, ..., target]`` or ``None`` if none/too deep."""
    if start == target:  # self-loop: A subClassOf A
        return [start]
    visited = {start}
    stack: list[tuple[str, list[str]]] = [(start, [start])]
    while stack:
        node, path = stack.pop()
        if len(path) > _MAX_DEPTH:
            return None  # graceful bail on a pathologically deep / tangled graph
        for nxt in sorted(parents_map.get(node, frozenset())):
            if nxt == target:
                return [*path, nxt]
            if nxt in visited:
                continue
            visited.add(nxt)
            stack.append((nxt, [*path, nxt]))
    return None


def _emit_cycles(ctx: _Ctx, paths: list[list[str]]) -> list[Change]:
    """Emit one ``class_hierarchy_cycle_introduced`` per entity on each cycle (Q3)."""
    changes: list[Change] = []
    for path in paths:
        subsumed = _cycle_added_triples(ctx, path)
        rendered = " → ".join(_short(ctx, iri) for iri in path)
        summary = f"Cycle introduced: {rendered}"
        for entity in sorted(set(path)):
            details: dict[str, object] = {"entity_iri": entity, "path": list(path)}
            changes.append(
                _finalize(
                    "class_hierarchy_cycle_introduced",
                    "breaking",
                    entity,
                    summary,
                    details,
                    subsumed,
                    ctx.registry,
                )
            )
    return changes


def _cycle_added_triples(ctx: _Ctx, path: list[str]) -> list[Change]:
    """Layer 0 ``triple_added`` changes for the cycle's edges that are new in B."""
    a_parents = ctx.index_a.class_parents
    triples: list[Change] = []
    for child, parent in pairwise(path):
        if parent in a_parents.get(child, frozenset()):
            continue  # pre-existing edge of the cycle
        triples.extend(_match_edge(ctx, child, _SUBCLASS_OF, parent, "triple_added", ctx.nsm_b))
    return triples


# --------------------------------------------------------------------------- #
# Layer 0 matching + small formatters
# --------------------------------------------------------------------------- #


def _index_layer0(layer0_changes: list[Change]) -> Layer0Index:
    """Bucket Layer 0 changes by ``(subject_iri, predicate_iri, kind)``."""
    index: Layer0Index = {}
    for change in layer0_changes:
        key = (
            change.details.get("subject_iri"),
            change.details.get("predicate_iri"),
            change.kind,
        )
        index.setdefault(key, []).append(change)
    return index


def _edges_for(
    ctx: _Ctx,
    child: str,
    predicate: str,
    parents: frozenset[str],
    triple_kind: str,
    nsm: NamespaceManager,
) -> list[Change]:
    """All Layer 0 edge changes from ``child`` to any IRI in ``parents``."""
    edges: list[Change] = []
    for parent in parents:
        edges.extend(_match_edge(ctx, child, predicate, parent, triple_kind, nsm))
    return edges


def _match_edge(
    ctx: _Ctx, child: str, predicate: str, parent: str, triple_kind: str, nsm: NamespaceManager
) -> list[Change]:
    """Layer 0 changes for the exact triple ``child <predicate> parent``.

    The object is matched by its n3 form computed with the same namespace
    manager Layer 0 used, so a specific parent edge is picked out even when an
    entity gained or lost several parents at once.
    """
    candidates = ctx.layer0_index.get((child, predicate, triple_kind), [])
    target_n3 = URIRef(parent).n3(nsm)
    return [c for c in candidates if c.details.get("object") == target_n3]


def _short(ctx: _Ctx, iri: str) -> str:
    return shorten_iri(iri, ctx.prefixes)


def _noun(is_class: bool) -> str:
    return "Class" if is_class else "Property"


def _entity_kind(is_class: bool) -> str:
    return "class" if is_class else "property"


def _format_set(ctx: _Ctx, iris: frozenset[str], counterpart: frozenset[str]) -> str:
    """Render a parent set: braces when either side of the move has >1 parent."""
    braces = len(iris) > 1 or len(counterpart) > 1
    rendered = ", ".join(_short(ctx, iri) for iri in sorted(iris))
    return f"{{{rendered}}}" if braces else rendered
