"""Layer 1 — anonymous class-set & datatype-facet structural diff (Component 12.5).

Decodes the anonymous structures that the raw pipeline otherwise leaves as
``_list:`` / ``_restriction:`` Layer 0 noise and emits them as structured Layer 1
changes:

* ``owl:unionOf`` / ``owl:intersectionOf`` attached to ``rdfs:domain`` /
  ``rdfs:range`` / ``rdfs:subClassOf`` / ``owl:equivalentClass`` →
  ``<context>_union_added`` / ``_removed`` / ``_changed`` (12 kinds), including the
  flattening (union → bare) and unflattening (bare → union) reshapes.
* ``owl:onDatatype`` + ``owl:withRestrictions`` on a data property's range →
  ``datatype_facet_added`` / ``_removed`` / ``_changed`` / ``datatype_base_changed``
  (4 kinds).

Runs after :mod:`.restrictions` and before :mod:`.annotations` (orchestrator
order). Components 07 (hierarchy) and 08 (restrictions/domain/range/equivalent)
consult :func:`._class_set_index.owned_keys` and step aside for the
``(attached_to, via_predicate)`` keys handled here, so the flattening cases — one
side bare, the other a union — are reported once, by this slice. Intersection
inverts the union severity (Q2): a member *added* to an intersection narrows
(breaking); a member *removed* broadens (non_breaking). See
``specs/12.5-anonymous-structures.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rdflib import OWL, RDF, RDFS
from rdflib.namespace import NamespaceManager
from rdflib.term import Node, URIRef

from owlcompare.exceptions import DiffError
from owlcompare.model import OntologySnapshot, shorten_iri

from .._common import Change, DiffOptions, Severity, shorten_synthetic_iri
from .._subsumption import SubsumptionRegistry
from . import _class_set_index as csi
from . import _datatype_facet_index as dfi

logger = logging.getLogger(__name__)

_RESTRICTION_NS = "urn:owlcompare:restriction:"

# Attachment CURIE → its full predicate IRI and the rdflib term, for Layer 0
# matching and graph queries.
_VIA_URIREF: dict[str, URIRef] = {
    "rdfs:domain": RDFS.domain,
    "rdfs:range": RDFS.range,
    "rdfs:subClassOf": RDFS.subClassOf,
    "owl:equivalentClass": OWL.equivalentClass,
}
_VIA_IRI: dict[str, str] = {curie: str(term) for curie, term in _VIA_URIREF.items()}

# Attachment CURIE → the change-kind context token and the human summary noun.
_CTX_BY_VIA: dict[str, str] = {
    "rdfs:domain": "domain",
    "rdfs:range": "range",
    "rdfs:subClassOf": "subclass",
    "owl:equivalentClass": "equivalent_class",
}
_NOUN_BY_CTX: dict[str, str] = {
    "domain": "Domain",
    "range": "Range",
    "subclass": "Subclass",
    "equivalent_class": "Equivalent class",
}
_VERB_BY_ACTION: dict[str, str] = {"added": "expanded", "removed": "narrowed", "changed": "changed"}

# Datatype facet field → its short display label (used in summaries).
_FACET_LABEL: dict[str, str] = {
    "min_inclusive": "min",
    "max_inclusive": "max",
    "min_exclusive": "min (exclusive)",
    "max_exclusive": "max (exclusive)",
    "length": "length",
    "min_length": "minLength",
    "max_length": "maxLength",
    "pattern": "pattern",
}
# Tightening direction per facet: a larger min / smaller max is the tighter bound.
_FACET_MIN_FIELDS = frozenset({"min_inclusive", "min_exclusive", "min_length"})
_FACET_MAX_FIELDS = frozenset({"max_inclusive", "max_exclusive", "max_length"})

# Ordering within the structural section: changed first, then added, then removed
# per context; datatype facet kinds after the union kinds; base change last.
_KIND_RANK: dict[str, int] = {
    "domain_union_changed": 0,
    "domain_union_added": 1,
    "domain_union_removed": 2,
    "range_union_changed": 3,
    "range_union_added": 4,
    "range_union_removed": 5,
    "subclass_union_changed": 6,
    "subclass_union_added": 7,
    "subclass_union_removed": 8,
    "equivalent_class_union_changed": 9,
    "equivalent_class_union_added": 10,
    "equivalent_class_union_removed": 11,
    "datatype_facet_changed": 12,
    "datatype_facet_added": 13,
    "datatype_facet_removed": 14,
    "datatype_base_changed": 15,
}

Layer0EdgeIndex = dict[tuple[str | None, str | None, str], list[Change]]
Layer0SubjectIndex = dict[tuple[str, str], list[Change]]


@dataclass(slots=True)
class _Ctx:
    """Per-call state threaded through the class-set diff helpers."""

    a: OntologySnapshot
    b: OntologySnapshot
    index_a: csi.ClassSetIndex
    index_b: csi.ClassSetIndex
    facets_a: dict[str, dfi.DatatypeFacets]
    facets_b: dict[str, dfi.DatatypeFacets]
    prefixes: dict[str, str]
    registry: SubsumptionRegistry
    nsm_a: NamespaceManager
    nsm_b: NamespaceManager
    by_edge: Layer0EdgeIndex
    by_subject_n3: Layer0SubjectIndex

    def short(self, iri: str) -> str:
        """Prefixed display form, collapsing synthetic restriction/list URNs."""
        return shorten_synthetic_iri(shorten_iri(iri, self.prefixes))


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    layer0_changes: list[Change],
    registry: SubsumptionRegistry,
    options: DiffOptions | None = None,
) -> list[Change]:
    """Detect and emit Layer 1 changes for anonymous class-set and datatype-facet structures.

    Handles ``owl:unionOf`` / ``owl:intersectionOf`` attached to ``rdfs:domain``,
    ``rdfs:range``, ``rdfs:subClassOf`` and ``owl:equivalentClass`` (the
    ``*_union_*`` kinds, flattening/unflattening included) and ``owl:onDatatype`` +
    ``owl:withRestrictions`` datatype facet restrictions (the ``datatype_facet_*`` /
    ``datatype_base_changed`` kinds). Updates ``registry`` in place.

    Args:
        a: Baseline snapshot (canonicalized).
        b: Comparison snapshot (canonicalized).
        layer0_changes: Component 05's output, used for subsumption tracking.
        registry: Shared subsumption registry, mutated in place.
        options: Reserved for future layer knobs; unused by this slice.

    Returns:
        A list of ``Change`` records with ``layer="structural"``.

    Raises:
        DiffError: if either snapshot is not canonicalized.
    """
    del options  # no class-set-slice knobs yet; kept for a uniform signature
    if not a.canonical or not b.canonical:
        raise DiffError("inputs must be canonicalized first")

    ctx = _Ctx(
        a=a,
        b=b,
        index_a=csi.build(a),
        index_b=csi.build(b),
        facets_a=dfi.build(a),
        facets_b=dfi.build(b),
        prefixes={**a.prefixes, **b.prefixes},
        registry=registry,
        nsm_a=a.graph.namespace_manager,
        nsm_b=b.graph.namespace_manager,
        by_edge=_index_by_edge(layer0_changes),
        by_subject_n3=_index_by_subject_n3(layer0_changes),
    )

    changes: list[Change] = []
    changes.extend(_diff_class_sets(ctx))
    changes.extend(_diff_facets(ctx))
    changes.sort(key=lambda c: (_KIND_RANK[c.kind], c.subject or ""))
    return changes


# --------------------------------------------------------------------------- #
# Union / intersection class sets
# --------------------------------------------------------------------------- #


def _diff_class_sets(ctx: _Ctx) -> list[Change]:
    """Diff every ``(attached_to, via_predicate)`` key with a class set on either side."""
    keys = _class_set_keys(ctx)
    changes: list[Change] = []
    for attached_to, via in sorted(keys):
        change = _diff_one_class_set(ctx, attached_to, via)
        if change is not None:
            changes.append(change)
    return changes


def _class_set_keys(ctx: _Ctx) -> set[tuple[str, str]]:
    """All ``(attached_to, via)`` keys owned by a class set on either side.

    Derived from :func:`._class_set_index.owned_keys` (every union/intersection
    node, single-member ones included) so a key that normalized to bare on one
    side is still diffed and subsumed here rather than left as Layer 0 noise.
    """
    return csi.owned_keys(ctx.a, ctx.b)


def _diff_one_class_set(ctx: _Ctx, attached_to: str, via: str) -> Change | None:
    """Emit the single ``<context>_union_*`` change for one attachment key, if any."""
    attach_a = ctx.index_a.for_key(attached_to, via)
    attach_b = ctx.index_b.for_key(attached_to, via)
    via_term = _VIA_URIREF[via]

    members_a = _effective_members(ctx.a, attached_to, via_term)
    members_b = _effective_members(ctx.b, attached_to, via_term)
    removed = members_a - members_b
    added = members_b - members_a
    if not removed and not added:
        return None

    attach = attach_a or attach_b
    operator = attach.operator if attach is not None else "unionOf"
    shape = _shape_change(attach_a is not None, attach_b is not None)
    ctx_token = _CTX_BY_VIA[via]
    action = "changed" if (removed and added) else ("added" if added else "removed")
    kind = f"{ctx_token}_union_{action}"
    severity = _union_severity(ctx_token, action, operator)

    summary = _union_summary(
        ctx, ctx_token, attached_to, shape, action, members_a, members_b, added, removed
    )
    details: dict[str, object] = {
        "entity_iri": attached_to,
        "via_predicate": via,
        "operator": operator,
        "members_before": sorted(members_a),
        "members_after": sorted(members_b),
        "added_members": sorted(added),
        "removed_members": sorted(removed),
        "shape_change": shape,
    }
    subsumed = _class_set_subsumed(ctx, attached_to, via_term, removed=True)
    subsumed += _class_set_subsumed(ctx, attached_to, via_term, removed=False)
    return _finalize(ctx, kind, severity, attached_to, summary, details, subsumed)


def _shape_change(a_has_union: bool, b_has_union: bool) -> str:
    """``stable`` / ``flattened`` (union→bare) / ``unflattened`` (bare→union)."""
    if a_has_union and b_has_union:
        return "stable"
    if a_has_union and not b_has_union:
        return "flattened"
    return "unflattened"


def _union_severity(ctx_token: str, action: str, operator: str) -> Severity:
    """Severity for a union/intersection change (Q2: intersection inverts add/remove)."""
    if ctx_token == "equivalent_class":
        return "breaking"  # semantic identity shift, either direction
    if action == "changed":
        return "breaking"  # mixed add+remove → defensive
    if operator == "intersectionOf":
        # Adding to an intersection narrows (breaking); removing broadens (non_breaking).
        return "breaking" if action == "added" else "non_breaking"
    # unionOf: adding broadens (non_breaking); removing narrows (breaking).
    return "non_breaking" if action == "added" else "breaking"


def _union_summary(
    ctx: _Ctx,
    ctx_token: str,
    attached_to: str,
    shape: str,
    action: str,
    members_a: set[str],
    members_b: set[str],
    added: set[str],
    removed: set[str],
) -> str:
    """Build the human summary, with the flattening / unflattening special phrasings."""
    noun = _NOUN_BY_CTX[ctx_token]
    entity = ctx.short(attached_to)
    if shape == "flattened":
        now = _join_members(ctx, members_b)
        was = _brace_members(ctx, members_a)
        return f"{noun} simplified on {entity}: now {now} only (was union of {was})"
    if shape == "unflattened":
        now = _brace_members(ctx, members_b)
        was = _join_members(ctx, members_a)
        return f"{noun} extended on {entity}: now union of {now} (was {was})"
    verb = _VERB_BY_ACTION[action]
    return f"{noun} {verb} on {entity}: {_member_delta(ctx, added, removed)}"


def _member_delta(ctx: _Ctx, added: set[str], removed: set[str]) -> str:
    """``+ era:A, + era:B, - era:C`` notation for a stable-shape member change."""
    parts = [f"+ {ctx.short(m)}" for m in sorted(added)]
    parts += [f"- {ctx.short(m)}" for m in sorted(removed)]
    return ", ".join(parts)


def _join_members(ctx: _Ctx, members: set[str]) -> str:
    return ", ".join(ctx.short(m) for m in sorted(members)) or "(none)"


def _brace_members(ctx: _Ctx, members: set[str]) -> str:
    return "{" + ", ".join(ctx.short(m) for m in sorted(members)) + "}"


def _effective_members(snapshot: OntologySnapshot, subject: str, predicate: URIRef) -> set[str]:
    """The logical named member set ``subject`` relates to via ``predicate``.

    Unions and intersections contribute their named members; a bare named
    relation (including a single-member union normalized to bare) contributes
    itself. This is the "logical form" the diff compares across A and B,
    independent of whether either side spells it as a union or a bare class.
    """
    graph = snapshot.graph
    node_ids = csi.class_set_node_ids(graph)
    members: set[str] = set()
    for _, _, obj in graph.triples((URIRef(subject), predicate, None)):
        if str(obj) in node_ids:
            members |= _class_set_members(graph, obj)
        elif isinstance(obj, URIRef) and not str(obj).startswith(csi._SYNTHETIC_PREFIX):
            members.add(str(obj))
    return members


def _class_set_members(graph: object, node: Node) -> set[str]:
    """Named members of an anonymous class set node (union or intersection)."""
    members: set[str] = set()
    for op_predicate, _ in csi._OPERATORS:
        for head in graph.objects(node, op_predicate):  # type: ignore[attr-defined]
            members |= set(csi._read_named_members(graph, head))  # type: ignore[arg-type]
    return members


# --------------------------------------------------------------------------- #
# Datatype facets
# --------------------------------------------------------------------------- #


def _diff_facets(ctx: _Ctx) -> list[Change]:
    """Diff every property's datatype facet restriction across A and B."""
    changes: list[Change] = []
    for prop in sorted(set(ctx.facets_a) | set(ctx.facets_b)):
        fa = ctx.facets_a.get(prop)
        fb = ctx.facets_b.get(prop)
        if fa is None or fb is None:
            changes.extend(_facet_one_sided(ctx, prop, fa, fb))
            continue
        if fa.base_datatype != fb.base_datatype:
            changes.append(_base_changed(ctx, prop, fa, fb))
            continue
        changes.extend(_facet_value_changes(ctx, prop, fa, fb))
    return changes


def _facet_one_sided(
    ctx: _Ctx,
    prop: str,
    fa: dfi.DatatypeFacets | None,
    fb: dfi.DatatypeFacets | None,
) -> list[Change]:
    """Whole facet restriction appeared (B only) or disappeared (A only).

    Each present facet surfaces as ``datatype_facet_added`` / ``_removed``. A
    restriction that gained facets is a tightening (breaking); one that lost them
    relaxes (non_breaking).
    """
    facets = fb or fa
    if facets is None or not facets.present_facets():
        return []
    added = fb is not None
    changes: list[Change] = []
    for field, value in facets.present_facets().items():
        changes.append(_facet_single(ctx, prop, fa, fb, field, value, added=added))
    return changes


def _facet_value_changes(
    ctx: _Ctx, prop: str, fa: dfi.DatatypeFacets, fb: dfi.DatatypeFacets
) -> list[Change]:
    """Per-field add/remove/change for two same-base facet restrictions."""
    before = fa.present_facets()
    after = fb.present_facets()
    changes: list[Change] = []
    for field in sorted(set(before) | set(after), key=_facet_order):
        in_a, in_b = field in before, field in after
        if in_a and in_b:
            if before[field] != after[field]:
                changes.append(_facet_changed(ctx, prop, fa, fb, field))
        elif in_b:
            changes.append(_facet_single(ctx, prop, fa, fb, field, after[field], added=True))
        else:
            changes.append(_facet_single(ctx, prop, fa, fb, field, before[field], added=False))
    return changes


def _facet_order(field: str) -> int:
    return dfi._FIELD_ORDER.index(field)


def _facet_single(
    ctx: _Ctx,
    prop: str,
    fa: dfi.DatatypeFacets | None,
    fb: dfi.DatatypeFacets | None,
    field: str,
    value: object,
    *,
    added: bool,
) -> Change:
    """Emit ``datatype_facet_added`` (breaking) / ``datatype_facet_removed`` (non_breaking)."""
    verb = "added" if added else "removed"
    severity: Severity = "breaking" if added else "non_breaking"
    base = fb or fa
    base_label = ctx.short(base.base_datatype) if base is not None else "?"
    summary = (
        f"Range facet {verb} on {ctx.short(prop)}: {base_label} {_FACET_LABEL[field]} {_fmt(value)}"
    )
    details = _facet_details(prop, fa, fb, [field])
    subsumed = _facet_subsumed(ctx, prop, removed=True) + _facet_subsumed(ctx, prop, removed=False)
    return _finalize(ctx, f"datatype_facet_{verb}", severity, prop, summary, details, subsumed)


def _facet_changed(
    ctx: _Ctx, prop: str, fa: dfi.DatatypeFacets, fb: dfi.DatatypeFacets, field: str
) -> Change:
    """Emit ``datatype_facet_changed`` (tightened → breaking, relaxed → non_breaking)."""
    before = fa.present_facets()[field]
    after = fb.present_facets()[field]
    severity = _facet_change_severity(field, before, after)
    summary = (
        f"Range facet changed on {ctx.short(prop)}: "
        f"{_FACET_LABEL[field]} {_fmt(before)} → {_fmt(after)}"
    )
    details = _facet_details(prop, fa, fb, [field])
    subsumed = _facet_subsumed(ctx, prop, removed=True) + _facet_subsumed(ctx, prop, removed=False)
    return _finalize(ctx, "datatype_facet_changed", severity, prop, summary, details, subsumed)


def _base_changed(ctx: _Ctx, prop: str, fa: dfi.DatatypeFacets, fb: dfi.DatatypeFacets) -> Change:
    """Emit ``datatype_base_changed`` (breaking) — the underlying datatype swapped."""
    summary = (
        f"Range base changed on {ctx.short(prop)}: "
        f"{ctx.short(fa.base_datatype)} → {ctx.short(fb.base_datatype)}"
    )
    changed = sorted(
        set(fa.present_facets()) ^ set(fb.present_facets())
        | {
            f
            for f in set(fa.present_facets()) & set(fb.present_facets())
            if fa.present_facets()[f] != fb.present_facets()[f]
        },
        key=_facet_order,
    )
    details = _facet_details(prop, fa, fb, changed)
    subsumed = _facet_subsumed(ctx, prop, removed=True) + _facet_subsumed(ctx, prop, removed=False)
    return _finalize(ctx, "datatype_base_changed", "breaking", prop, summary, details, subsumed)


def _facet_change_severity(field: str, before: object, after: object) -> Severity:
    """Tightened bound → breaking; relaxed → non_breaking; length/pattern → breaking."""
    if field == "pattern" or field == "length":
        return "breaking"
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return "breaking"
    if field in _FACET_MIN_FIELDS:
        return "breaking" if after > before else "non_breaking"
    if field in _FACET_MAX_FIELDS:
        return "breaking" if after < before else "non_breaking"
    return "breaking"


def _facet_details(
    prop: str,
    fa: dfi.DatatypeFacets | None,
    fb: dfi.DatatypeFacets | None,
    changed_facets: list[str],
) -> dict[str, object]:
    """The shared ``details`` payload for every datatype-facet change kind."""
    return {
        "property_iri": prop,
        "base_before": fa.base_datatype if fa is not None else None,
        "base_after": fb.base_datatype if fb is not None else None,
        "facets_before": dict(fa.present_facets()) if fa is not None else {},
        "facets_after": dict(fb.present_facets()) if fb is not None else {},
        "changed_facets": changed_facets,
    }


def _fmt(value: object) -> str:
    """Render a facet value compactly (``327670`` not ``327670.0``)."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# --------------------------------------------------------------------------- #
# Subsumption
# --------------------------------------------------------------------------- #


def _class_set_subsumed(
    ctx: _Ctx, attached_to: str, predicate: URIRef, *, removed: bool
) -> list[Change]:
    """Layer 0 triples of one side's class-set attachment (edge + reified structure)."""
    snapshot = ctx.a if removed else ctx.b
    nsm = ctx.nsm_a if removed else ctx.nsm_b
    kind = "triple_removed" if removed else "triple_added"
    node_ids = csi.class_set_node_ids(snapshot.graph)
    triples: list[Change] = []
    for _, _, obj in snapshot.graph.triples((URIRef(attached_to), predicate, None)):
        if str(obj) in node_ids:
            triples += _match_edge(ctx, attached_to, str(predicate), obj, nsm, kind)
            triples += _structure_triples(ctx, snapshot, obj, nsm, kind)
        elif isinstance(obj, URIRef) and not str(obj).startswith(csi._SYNTHETIC_PREFIX):
            triples += _match_edge(ctx, attached_to, str(predicate), obj, nsm, kind)
    return triples


def _facet_subsumed(ctx: _Ctx, prop: str, *, removed: bool) -> list[Change]:
    """Layer 0 triples of one side's datatype facet restriction (edge + reified structure)."""
    snapshot = ctx.a if removed else ctx.b
    nsm = ctx.nsm_a if removed else ctx.nsm_b
    kind = "triple_removed" if removed else "triple_added"
    node = _datatype_node(snapshot, prop)
    if node is None:
        return []
    triples = _match_edge(ctx, prop, str(RDFS.range), node, nsm, kind)
    triples += _structure_triples(ctx, snapshot, node, nsm, kind)
    return triples


def _datatype_node(snapshot: OntologySnapshot, prop: str) -> Node | None:
    """The ``rdfs:Datatype`` facet node on ``prop``'s range, if any."""
    graph = snapshot.graph
    for _, _, node in graph.triples((URIRef(prop), RDFS.range, None)):
        if (node, RDF.type, RDFS.Datatype) in graph and list(graph.objects(node, OWL.onDatatype)):
            return node
    return None


def _structure_triples(
    ctx: _Ctx, snapshot: OntologySnapshot, target: Node, nsm: NamespaceManager, kind: str
) -> list[Change]:
    """All Layer 0 triples of a reified anonymous structure rooted at ``target``.

    Walks the structure spine — ``owl:unionOf`` / ``owl:intersectionOf`` /
    ``owl:withRestrictions`` into the list head, ``rdf:rest`` along the cells, and
    ``rdf:first`` *only* into blank-node facet leaves (never into named union
    members) — collecting every triple whose subject is a structure node.
    """
    triples: list[Change] = []
    for node in _structure_nodes(snapshot, target):
        triples += ctx.by_subject_n3.get((node.n3(nsm), kind), [])
    return triples


def _structure_nodes(snapshot: OntologySnapshot, target: Node) -> set[Node]:
    """The set of structure nodes (the target plus its list cells / facet leaves)."""
    graph = snapshot.graph
    nodes: set[Node] = set()
    pending: list[Node] = [target]
    while pending:
        node = pending.pop()
        if node in nodes or node == RDF.nil:
            continue
        nodes.add(node)
        for spine in (OWL.unionOf, OWL.intersectionOf, OWL.withRestrictions, RDF.rest):
            pending.extend(graph.objects(node, spine))
        for first in graph.objects(node, RDF.first):
            if isinstance(first, Node) and not isinstance(first, URIRef):
                pending.append(first)  # blank-node facet leaf, not a named member
    nodes.discard(RDF.nil)
    return nodes


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


def _index_by_subject_n3(layer0_changes: list[Change]) -> Layer0SubjectIndex:
    """Bucket Layer 0 changes by ``(subject_n3, kind)`` — matches URN *and* bnode subjects."""
    index: Layer0SubjectIndex = {}
    for change in layer0_changes:
        subject = change.details.get("subject")
        if isinstance(subject, str):
            index.setdefault((subject, change.kind), []).append(change)
    return index


def _match_edge(
    ctx: _Ctx, subject: str, predicate: str, obj: Node, nsm: NamespaceManager, kind: str
) -> list[Change]:
    """Layer 0 changes for the exact triple ``subject <predicate> obj``."""
    candidates = ctx.by_edge.get((subject, predicate, kind), [])
    target_n3 = obj.n3(nsm)
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
    """Attach subsumption + change_id to a class-set change and register it."""
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
        logger.debug("class-set change %s has no matching Layer 0 changes", change_id)
    return change
