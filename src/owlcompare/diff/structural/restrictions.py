"""Layer 1 — restriction and class-axiom structural diff (Component 08).

Consolidates the 3-4 reified Layer 0 triples of an anonymous restriction into a
single meaningful event — *"Restriction changed on era:Track: era:hasMaxSpeed
max 1 → max 2"* — and likewise folds domain/range, equivalent-class, disjoint
and complement axiom edits into one ``Change`` each. Runs after the entity
(Component 06) and hierarchy (Component 07) slices, sharing one
:class:`SubsumptionRegistry`: a restriction on a class that was wholly added or
removed is deferred to that class's entity-level change rather than re-reported.
Filler / domain / range narrowing is decided from the *asserted* hierarchy
(Component 07's index); undecidable cases default to ``breaking``. See
``specs/08-structural-restrictions.md``.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from rdflib import OWL, RDF, RDFS
from rdflib.namespace import NamespaceManager
from rdflib.term import URIRef

from owlcompare.exceptions import DiffError
from owlcompare.model import OntologySnapshot, shorten_iri

from .._common import Change, DiffOptions, Severity, shorten_synthetic_iri
from .._subsumption import SubsumptionRegistry
from . import _class_expression as ce
from ._hierarchy_index import build as build_hierarchy
from ._restriction_index import DecodedRestriction, RestrictionIndex, build

logger = logging.getLogger(__name__)

_RESTRICTION_NS = "urn:owlcompare:restriction:"
_RDF_TYPE = str(RDF.type)
_DOMAIN = str(RDFS.domain)
_RANGE = str(RDFS.range)
_DISJOINT_WITH = str(OWL.disjointWith)
_COMPLEMENT_OF = str(OWL.complementOf)
_VIA_IRI: dict[str, str] = {
    "rdfs:subClassOf": str(RDFS.subClassOf),
    "owl:equivalentClass": str(OWL.equivalentClass),
}

_MAX_KINDS = frozenset({"max_cardinality", "max_qualified_cardinality"})
_MIN_KINDS = frozenset({"min_cardinality", "min_qualified_cardinality"})

# Ordering within the structural section (spec § Ordering): changed first, then
# added/removed, then domain/range, equivalence, disjointness, complement, and
# the opaque fallback last. Ties broken by subject then on_property.
_KIND_RANK: dict[str, int] = {
    "restriction_changed": 0,
    "restriction_added": 1,
    "restriction_removed": 2,
    "domain_changed": 3,
    "domain_added": 4,
    "domain_removed": 5,
    "range_changed": 6,
    "range_added": 7,
    "range_removed": 8,
    "equivalent_class_added": 9,
    "equivalent_class_removed": 10,
    "disjoint_added": 11,
    "disjoint_removed": 12,
    "complement_set": 13,
    "complement_unset": 14,
    "complex_class_expression_changed": 15,
}

Layer0SubjectIndex = dict[tuple[str, str], list[Change]]
Layer0EdgeIndex = dict[tuple[str | None, str | None, str], list[Change]]
ParentMap = dict[str, frozenset[str]]
Matcher = Callable[[DecodedRestriction, DecodedRestriction], bool]


@dataclass(slots=True)
class _Ctx:
    """Per-call state threaded through the restriction diff helpers."""

    a: OntologySnapshot
    b: OntologySnapshot
    index_a: RestrictionIndex
    index_b: RestrictionIndex
    parents: ParentMap
    prefixes: dict[str, str]
    registry: SubsumptionRegistry
    nsm_a: NamespaceManager
    nsm_b: NamespaceManager
    by_subject: Layer0SubjectIndex
    by_edge: Layer0EdgeIndex
    iris_a: set[str]
    iris_b: set[str]

    def short(self, iri: str) -> str:
        """Prefixed display form, also collapsing synthetic restriction/list URNs."""
        return shorten_synthetic_iri(shorten_iri(iri, self.prefixes))


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    layer0_changes: list[Change],
    registry: SubsumptionRegistry,
    options: DiffOptions | None = None,
) -> list[Change]:
    """Compute Layer 1 restriction-level differences.

    Emits ``restriction_added`` / ``restriction_removed`` / ``restriction_changed``
    for cardinality and value restrictions, ``domain_*`` / ``range_*`` for
    property domain/range, ``equivalent_class_*``, ``disjoint_*``,
    ``complement_set`` / ``complement_unset``, and ``complex_class_expression_changed``
    as the fallback for nested or malformed expressions.

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
    del options  # no restriction-slice knobs yet; kept for a uniform signature
    if not a.canonical or not b.canonical:
        raise DiffError("inputs must be canonicalized first")

    ctx = _Ctx(
        a=a,
        b=b,
        index_a=build(a),
        index_b=build(b),
        parents=_combined_parents(a, b),
        prefixes={**a.prefixes, **b.prefixes},
        registry=registry,
        nsm_a=a.graph.namespace_manager,
        nsm_b=b.graph.namespace_manager,
        by_subject=_index_by_subject(layer0_changes),
        by_edge=_index_by_edge(layer0_changes),
        iris_a=a.entities.all_iris(),
        iris_b=b.entities.all_iris(),
    )

    changes: list[Change] = []
    changes.extend(_diff_restrictions(ctx))
    changes.extend(_diff_domain_range(ctx, is_domain=True))
    changes.extend(_diff_domain_range(ctx, is_domain=False))
    changes.extend(_diff_equivalent(ctx))
    changes.extend(_diff_disjoint(ctx))
    changes.extend(_diff_complement(ctx))

    changes.sort(key=lambda c: (_KIND_RANK[c.kind], c.subject or "", _on_property(c)))
    return changes


# --------------------------------------------------------------------------- #
# Restrictions
# --------------------------------------------------------------------------- #


def _diff_restrictions(ctx: _Ctx) -> list[Change]:
    """Diff every named class's attached restrictions, grouped by (via, property)."""
    entities = sorted(set(ctx.index_a.by_attached_entity) | set(ctx.index_b.by_attached_entity))
    changes: list[Change] = []
    for entity in entities:
        list_a = ctx.index_a.by_attached_entity.get(entity, [])
        list_b = ctx.index_b.by_attached_entity.get(entity, [])
        if _defer_restrictions(ctx, entity, list_a, list_b):
            continue
        changes.extend(_diff_restriction_groups(ctx, list_a, list_b))
    return changes


def _diff_restriction_groups(
    ctx: _Ctx, list_a: list[DecodedRestriction], list_b: list[DecodedRestriction]
) -> list[Change]:
    """Match restrictions by (via, property) group and emit per-pair changes."""
    groups_a = _group(list_a)
    groups_b = _group(list_b)
    changes: list[Change] = []
    for key in sorted(set(groups_a) | set(groups_b)):
        pairs, removed, added = _match_group(groups_a.get(key, []), groups_b.get(key, []))
        for before, after in pairs:
            if before.urn == after.urn:
                continue  # identical post-canonicalization → no change
            changes.append(_changed_restriction(ctx, before, after))
        changes.extend(_removed_restriction(ctx, r) for r in removed)
        changes.extend(_added_restriction(ctx, r) for r in added)
    return changes


def _group(
    restrictions: list[DecodedRestriction],
) -> dict[tuple[str, str | None], list[DecodedRestriction]]:
    """Bucket restrictions by ``(via_predicate, on_property)`` (Q1: property first)."""
    groups: dict[tuple[str, str | None], list[DecodedRestriction]] = defaultdict(list)
    for restriction in restrictions:
        groups[(restriction.via_predicate, restriction.on_property)].append(restriction)
    return groups


def _match_group(
    list_a: list[DecodedRestriction], list_b: list[DecodedRestriction]
) -> tuple[
    list[tuple[DecodedRestriction, DecodedRestriction]],
    list[DecodedRestriction],
    list[DecodedRestriction],
]:
    """Pair restrictions within one group; surplus become removed / added.

    Pass 0 pairs content-identical restrictions (same URN), pass 1 pairs by
    matching kind (cardinality tuning / filler swap), pass 2 pairs leftovers
    across kinds (a kind change). Whatever remains on either side is surplus.
    """
    a_rem = list(list_a)
    b_rem = list(list_b)
    pairs: list[tuple[DecodedRestriction, DecodedRestriction]] = []

    def pair_by(matches: Matcher) -> None:
        for ra in list(a_rem):
            rb = next((cand for cand in b_rem if matches(ra, cand)), None)
            if rb is not None:
                pairs.append((ra, rb))
                a_rem.remove(ra)
                b_rem.remove(rb)

    pair_by(_same_urn)  # pass 0: content-identical restrictions
    pair_by(_same_kind)  # pass 1: same shape, different content
    while a_rem and b_rem:  # pass 2: leftovers paired across kinds (kind change)
        pairs.append((a_rem.pop(0), b_rem.pop(0)))
    return pairs, a_rem, b_rem


def _same_urn(left: DecodedRestriction, right: DecodedRestriction) -> bool:
    return left.urn == right.urn


def _same_kind(left: DecodedRestriction, right: DecodedRestriction) -> bool:
    return left.kind == right.kind


def _changed_restriction(
    ctx: _Ctx, before: DecodedRestriction, after: DecodedRestriction
) -> Change:
    """Emit ``restriction_changed`` (or ``complex_...`` for nested/opaque cases)."""
    nested_inner_only = (
        (_is_nested(before) or _is_nested(after))
        and before.kind == after.kind
        and before.cardinality == after.cardinality
    )
    if before.kind == "complex" or after.kind == "complex" or nested_inner_only:
        return _complex_change(ctx, before, after)

    severity = _changed_severity(before, after, ctx.parents)
    # ruff-bug-0.15.x: a lambda inside an implicitly-concatenated multi-line
    # f-string crashes `ruff format` ("Expected end tag of kind Group but found
    # Indent"). We pass the bound `ctx.short` and compute `phrase` on its own
    # line instead. Refactor back to an inline lambda when the bug is fixed and
    # the DD-017 pin is lifted. (No upstream issue located as of 2026-06.)
    phrase = ce.describe_change(before, after, ctx.short)
    summary = f"Restriction changed on {ctx.short(before.attached_to)}: {phrase}"
    details: dict[str, object] = {
        "entity_iri": before.attached_to,
        "via_predicate": before.via_predicate,
        "on_property": before.on_property,
        "before": _decoded_dict(before),
        "after": _decoded_dict(after),
    }
    subsumed = _chain_triples(ctx, before, removed=True) + _chain_triples(ctx, after, removed=False)
    return _finalize(
        ctx, "restriction_changed", severity, before.attached_to, summary, details, subsumed
    )


def _added_restriction(ctx: _Ctx, restriction: DecodedRestriction) -> Change:
    """Emit ``restriction_added`` (breaking) for a new restriction."""
    if restriction.kind == "complex":
        return _complex_change(ctx, None, restriction)
    phrase = ce.describe(restriction, ctx.short)
    summary = f"Restriction added on {ctx.short(restriction.attached_to)}: {phrase}"
    details: dict[str, object] = {
        "entity_iri": restriction.attached_to,
        "via_predicate": restriction.via_predicate,
        "on_property": restriction.on_property,
        "before": None,
        "after": _decoded_dict(restriction),
    }
    subsumed = _chain_triples(ctx, restriction, removed=False)
    return _finalize(
        ctx, "restriction_added", "breaking", restriction.attached_to, summary, details, subsumed
    )


def _removed_restriction(ctx: _Ctx, restriction: DecodedRestriction) -> Change:
    """Emit ``restriction_removed`` (non_breaking) for a dropped restriction."""
    if restriction.kind == "complex":
        return _complex_change(ctx, restriction, None)
    phrase = ce.describe(restriction, ctx.short)
    summary = f"Restriction removed from {ctx.short(restriction.attached_to)}: {phrase}"
    details: dict[str, object] = {
        "entity_iri": restriction.attached_to,
        "via_predicate": restriction.via_predicate,
        "on_property": restriction.on_property,
        "before": _decoded_dict(restriction),
        "after": None,
    }
    subsumed = _chain_triples(ctx, restriction, removed=True)
    return _finalize(
        ctx,
        "restriction_removed",
        "non_breaking",
        restriction.attached_to,
        summary,
        details,
        subsumed,
    )


def _complex_change(
    ctx: _Ctx, before: DecodedRestriction | None, after: DecodedRestriction | None
) -> Change:
    """Emit the opaque ``complex_class_expression_changed`` fallback."""
    anchor = before or after
    assert anchor is not None
    entity = anchor.attached_to
    depth = max(
        _nesting_depth(ctx.index_a, before) if before else 0,
        _nesting_depth(ctx.index_b, after) if after else 0,
    )
    summary = f"Complex class expression on {ctx.short(entity)} changed (deep)"
    details: dict[str, object] = {
        "entity_iri": entity,
        "depth": depth,
        "note": "Deep class expression change; structured diff deferred to v2.",
    }
    subsumed: list[Change] = []
    if before is not None:
        subsumed += _chain_triples(ctx, before, removed=True)
    if after is not None:
        subsumed += _chain_triples(ctx, after, removed=False)
    return _finalize(
        ctx, "complex_class_expression_changed", "breaking", entity, summary, details, subsumed
    )


def _defer_restrictions(
    ctx: _Ctx,
    entity: str,
    list_a: list[DecodedRestriction],
    list_b: list[DecodedRestriction],
) -> bool:
    """If ``entity`` was wholly added/removed by Component 06, defer its restrictions.

    The restriction triples are part of the class's introduction/removal, so they
    are subsumed under Component 06's ``class_*`` change instead of producing a
    standalone restriction change here (spec § Step 4).
    """
    added = _wholly_changed(ctx, entity)
    if added is None:
        return False
    restrictions = list_b if added else list_a
    change_id = _entity_change_id(ctx, entity, added=added)
    if change_id is not None:
        triples: list[Change] = []
        for restriction in restrictions:
            triples += _chain_triples(ctx, restriction, removed=not added)
        if triples:
            ctx.registry.register(change_id, triples)
    return True


# --------------------------------------------------------------------------- #
# Domain / range
# --------------------------------------------------------------------------- #


def _diff_domain_range(ctx: _Ctx, *, is_domain: bool) -> list[Change]:
    """Diff property domains (or ranges): single-swap → changed, else add/remove."""
    maps_a = ctx.index_a.domains if is_domain else ctx.index_a.ranges
    maps_b = ctx.index_b.domains if is_domain else ctx.index_b.ranges
    predicate = _DOMAIN if is_domain else _RANGE
    noun = "Domain" if is_domain else "Range"
    prefix = "domain" if is_domain else "range"

    changes: list[Change] = []
    for prop in sorted(set(maps_a) | set(maps_b)):
        values_a = maps_a.get(prop, frozenset())
        values_b = maps_b.get(prop, frozenset())
        removed = values_a - values_b
        added = values_b - values_a
        if not removed and not added:
            continue
        if _defer_axiom(ctx, prop, predicate, removed, added):
            continue
        if len(values_a) == 1 and len(values_b) == 1:
            changes.append(
                _dr_changed(
                    ctx, prop, predicate, noun, prefix, next(iter(values_a)), next(iter(values_b))
                )
            )
            continue
        changes.extend(
            _dr_single(ctx, prop, predicate, noun, prefix, value, added=True)
            for value in sorted(added)
        )
        changes.extend(
            _dr_single(ctx, prop, predicate, noun, prefix, value, added=False)
            for value in sorted(removed)
        )
    return changes


def _dr_changed(
    ctx: _Ctx,
    prop: str,
    predicate: str,
    noun: str,
    prefix: str,
    before: str,
    after: str,
) -> Change:
    """Emit ``domain_changed`` / ``range_changed`` for a single-value swap (breaking)."""
    summary = f"{noun} changed on {ctx.short(prop)}: {ctx.short(before)} → {ctx.short(after)}"
    details: dict[str, object] = {"property_iri": prop, "before": before, "after": after}
    subsumed = _match_edge(ctx, prop, predicate, before, removed=True) + _match_edge(
        ctx, prop, predicate, after, removed=False
    )
    return _finalize(ctx, f"{prefix}_changed", "breaking", prop, summary, details, subsumed)


def _dr_single(
    ctx: _Ctx,
    prop: str,
    predicate: str,
    noun: str,
    prefix: str,
    value: str,
    *,
    added: bool,
) -> Change:
    """Emit ``domain_added`` / ``range_removed`` etc. (all non_breaking)."""
    verb = "added" if added else "removed"
    summary = f"{noun} {verb} on {ctx.short(prop)}: {ctx.short(value)}"
    details: dict[str, object] = {"property_iri": prop, "value": value}
    subsumed = _match_edge(ctx, prop, predicate, value, removed=not added)
    return _finalize(ctx, f"{prefix}_{verb}", "non_breaking", prop, summary, details, subsumed)


# --------------------------------------------------------------------------- #
# Equivalent class / disjoint / complement
# --------------------------------------------------------------------------- #


def _diff_equivalent(ctx: _Ctx) -> list[Change]:
    """Diff named ``owl:equivalentClass`` sets per class."""
    predicate = str(OWL.equivalentClass)
    classes = sorted(
        set(ctx.index_a.equivalent_class_sets) | set(ctx.index_b.equivalent_class_sets)
    )
    changes: list[Change] = []
    for cls in classes:
        set_a = ctx.index_a.equivalent_class_sets.get(cls, frozenset())
        set_b = ctx.index_b.equivalent_class_sets.get(cls, frozenset())
        removed = set_a - set_b
        added = set_b - set_a
        if not removed and not added:
            continue
        if _defer_axiom(ctx, cls, predicate, removed, added):
            continue
        changes.extend(_equivalent_change(ctx, cls, other, added=True) for other in sorted(added))
        changes.extend(
            _equivalent_change(ctx, cls, other, added=False) for other in sorted(removed)
        )
    return changes


def _equivalent_change(ctx: _Ctx, cls: str, other: str, *, added: bool) -> Change:
    """Emit ``equivalent_class_added`` (non_breaking) / ``_removed`` (breaking)."""
    verb = "added" if added else "removed"
    severity: Severity = "non_breaking" if added else "breaking"
    summary = f"{ctx.short(cls)} equivalent class {verb}: {ctx.short(other)}"
    details: dict[str, object] = {"entity_iri": cls, "other_iri": other}
    subsumed = _match_edge(ctx, cls, str(OWL.equivalentClass), other, removed=not added)
    return _finalize(ctx, f"equivalent_class_{verb}", severity, cls, summary, details, subsumed)


def _diff_disjoint(ctx: _Ctx) -> list[Change]:
    """Diff symmetric disjointness, emitting one change per unordered pair."""
    pairs_a = _disjoint_pairs(ctx.index_a.disjoint_sets)
    pairs_b = _disjoint_pairs(ctx.index_b.disjoint_sets)
    changes: list[Change] = []
    for pair in sorted(pairs_b - pairs_a, key=sorted):
        changes.append(_disjoint_change(ctx, pair, added=True))
    for pair in sorted(pairs_a - pairs_b, key=sorted):
        changes.append(_disjoint_change(ctx, pair, added=False))
    return changes


def _disjoint_pairs(disjoint_sets: dict[str, frozenset[str]]) -> set[frozenset[str]]:
    """Unordered ``{a, b}`` pairs from a symmetric disjointness map."""
    return {
        frozenset({cls, other})
        for cls, others in disjoint_sets.items()
        for other in others
        if cls != other
    }


def _disjoint_change(ctx: _Ctx, pair: frozenset[str], *, added: bool) -> Change:
    """Emit ``disjoint_added`` (breaking) / ``disjoint_removed`` (non_breaking)."""
    subject, other = sorted(pair)
    verb = "added" if added else "removed"
    severity: Severity = "breaking" if added else "non_breaking"
    summary = f"{ctx.short(subject)} disjoint with {verb}: {ctx.short(other)}"
    details: dict[str, object] = {"entity_iri": subject, "other_iri": other}
    subsumed = _match_edge(ctx, subject, _DISJOINT_WITH, other, removed=not added) + _match_edge(
        ctx, other, _DISJOINT_WITH, subject, removed=not added
    )
    return _finalize(ctx, f"disjoint_{verb}", severity, subject, summary, details, subsumed)


def _diff_complement(ctx: _Ctx) -> list[Change]:
    """Diff ``owl:complementOf`` targets per class (set / unset / target swap)."""
    classes = sorted(set(ctx.index_a.complement_targets) | set(ctx.index_b.complement_targets))
    changes: list[Change] = []
    for cls in classes:
        before = ctx.index_a.complement_targets.get(cls)
        after = ctx.index_b.complement_targets.get(cls)
        if before == after:
            continue
        if _wholly_changed(ctx, cls) is not None:
            _defer_complement(ctx, cls, before, after)
            continue
        changes.append(_complement_change(ctx, cls, before, after))
    return changes


def _complement_change(ctx: _Ctx, cls: str, before: str | None, after: str | None) -> Change:
    """Emit ``complement_set`` (breaking) or ``complement_unset`` (non_breaking)."""
    subsumed: list[Change] = []
    if before is not None:
        subsumed += _match_edge(ctx, cls, _COMPLEMENT_OF, before, removed=True)
    if after is not None:
        subsumed += _match_edge(ctx, cls, _COMPLEMENT_OF, after, removed=False)
    details: dict[str, object] = {"entity_iri": cls, "before": before, "after": after}
    if after is not None:
        arrow = f"{ctx.short(before)} → {ctx.short(after)}" if before else ctx.short(after)
        summary = f"{ctx.short(cls)} complement of: {arrow}"
        return _finalize(ctx, "complement_set", "breaking", cls, summary, details, subsumed)
    summary = f"{ctx.short(cls)} complement of {ctx.short(before or '')} removed"
    return _finalize(ctx, "complement_unset", "non_breaking", cls, summary, details, subsumed)


def _defer_complement(ctx: _Ctx, cls: str, before: str | None, after: str | None) -> None:
    """Subsume a complement edit under Component 06's change for a wholly-changed class."""
    added = _wholly_changed(ctx, cls)
    if added is None:
        return
    change_id = _entity_change_id(ctx, cls, added=added)
    if change_id is None:
        return
    target = after if added else before
    if target is None:
        return
    triples = _match_edge(ctx, cls, _COMPLEMENT_OF, target, removed=not added)
    if triples:
        ctx.registry.register(change_id, triples)


# --------------------------------------------------------------------------- #
# Coordination with Component 06
# --------------------------------------------------------------------------- #


def _wholly_changed(ctx: _Ctx, iri: str) -> bool | None:
    """``True`` if ``iri`` was wholly added, ``False`` if wholly removed, else ``None``."""
    in_a = iri in ctx.iris_a
    in_b = iri in ctx.iris_b
    if in_a == in_b:
        return None  # present on both sides (normal) or neither (synthetic) → no deferral
    return in_b


def _entity_change_id(ctx: _Ctx, iri: str, *, added: bool) -> str | None:
    """Component 06's change id explaining ``iri``'s ``rdf:type`` triple, if any."""
    triple_kind = "triple_added" if added else "triple_removed"
    for change in ctx.by_edge.get((iri, _RDF_TYPE, triple_kind), []):
        explainers = ctx.registry.explainers(SubsumptionRegistry.change_id(change))
        if explainers:
            return explainers[0]
    return None


def _defer_axiom(
    ctx: _Ctx, subject: str, predicate: str, removed: frozenset[str], added: frozenset[str]
) -> bool:
    """Defer a domain/range/equivalent edit on a wholly added/removed entity.

    Subsumes the affected edge triples under Component 06's change for the entity
    and returns ``True`` so the caller skips standalone emission.
    """
    changed = _wholly_changed(ctx, subject)
    if changed is None:
        return False
    change_id = _entity_change_id(ctx, subject, added=changed)
    if change_id is not None:
        targets = added if changed else removed
        triples: list[Change] = []
        for value in targets:
            triples += _match_edge(ctx, subject, predicate, value, removed=not changed)
        if triples:
            ctx.registry.register(change_id, triples)
    return True


# --------------------------------------------------------------------------- #
# Severity (asserted-hierarchy aware, cautious by default)
# --------------------------------------------------------------------------- #


def _changed_severity(
    before: DecodedRestriction, after: DecodedRestriction, parents: ParentMap
) -> Severity:
    """Severity for a ``restriction_changed`` (kind / cardinality / filler aware)."""
    if before.kind != after.kind:
        return "breaking"  # e.g. someValuesFrom → allValuesFrom, min → exact
    verdicts: list[Severity] = []
    if before.cardinality != after.cardinality:
        verdicts.append(_cardinality_severity(before.kind, before.cardinality, after.cardinality))
    if before.filler != after.filler:
        verdicts.append(_filler_severity(before.filler, after.filler, parents))
    if not verdicts:
        return "breaking"  # content differs but is undecidable → cautious
    return "breaking" if "breaking" in verdicts else "non_breaking"


def _cardinality_severity(kind: str, before: int | None, after: int | None) -> Severity:
    """Tightened cardinality is breaking; relaxed is non_breaking; exact is cautious."""
    if before is None or after is None:
        return "breaking"
    if kind in _MAX_KINDS:
        return "breaking" if after < before else "non_breaking"
    if kind in _MIN_KINDS:
        return "breaking" if after > before else "non_breaking"
    return "breaking"  # exact cardinality change is both-directional → breaking


def _filler_severity(before: str | None, after: str | None, parents: ParentMap) -> Severity:
    """Narrowed filler (new ⊏ old) is breaking; widened (new ⊐ old) is non_breaking."""
    if before is None or after is None:
        return "breaking"
    if _is_descendant(after, before, parents):
        return "breaking"  # narrowed: new filler is a subclass of the old
    if _is_descendant(before, after, parents):
        return "non_breaking"  # widened: new filler is a superclass of the old
    return "breaking"  # incomparable swap → cautious (asserted-only; see spec)


def _is_descendant(node: str, ancestor: str, parents: ParentMap) -> bool:
    """Whether ``ancestor`` is reachable walking ``node``'s asserted parents up."""
    seen = {node}
    stack = [node]
    while stack:
        current = stack.pop()
        for parent in parents.get(current, frozenset()):
            if parent == ancestor:
                return True
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return False


def _combined_parents(a: OntologySnapshot, b: OntologySnapshot) -> ParentMap:
    """Union of asserted class-parent edges from both snapshots (Q3: asserted only)."""
    merged: dict[str, set[str]] = defaultdict(set)
    for index in (build_hierarchy(a), build_hierarchy(b)):
        for child, parents in index.class_parents.items():
            merged[child] |= set(parents)
    return {child: frozenset(parents) for child, parents in merged.items()}


# --------------------------------------------------------------------------- #
# Layer 0 matching + subsumption
# --------------------------------------------------------------------------- #


def _index_by_subject(layer0_changes: list[Change]) -> Layer0SubjectIndex:
    """Bucket Layer 0 changes by ``(subject_iri, kind)`` (for restriction-URN triples)."""
    index: Layer0SubjectIndex = defaultdict(list)
    for change in layer0_changes:
        subject = change.details.get("subject_iri")
        if subject is not None:
            index[(subject, change.kind)].append(change)
    return index


def _index_by_edge(layer0_changes: list[Change]) -> Layer0EdgeIndex:
    """Bucket Layer 0 changes by ``(subject_iri, predicate_iri, kind)`` (for edges)."""
    index: Layer0EdgeIndex = defaultdict(list)
    for change in layer0_changes:
        key = (
            change.details.get("subject_iri"),
            change.details.get("predicate_iri"),
            change.kind,
        )
        index[key].append(change)
    return index


def _match_edge(
    ctx: _Ctx, subject: str, predicate: str, obj: str, *, removed: bool
) -> list[Change]:
    """Layer 0 changes for the exact triple ``subject <predicate> obj``."""
    triple_kind = "triple_removed" if removed else "triple_added"
    nsm = ctx.nsm_a if removed else ctx.nsm_b
    candidates = ctx.by_edge.get((subject, predicate, triple_kind), [])
    target_n3 = URIRef(obj).n3(nsm)
    return [c for c in candidates if c.details.get("object") == target_n3]


def _chain_triples(ctx: _Ctx, restriction: DecodedRestriction, *, removed: bool) -> list[Change]:
    """All Layer 0 triples of a restriction (its URN + attachment edge + nested URNs)."""
    triple_kind = "triple_removed" if removed else "triple_added"
    index = ctx.index_a if removed else ctx.index_b
    triples: list[Change] = list(ctx.by_subject.get((restriction.urn, triple_kind), []))
    if restriction.attached_to and restriction.via_predicate:
        via = _VIA_IRI[restriction.via_predicate]
        triples += _match_edge(ctx, restriction.attached_to, via, restriction.urn, removed=removed)

    seen: set[str] = {restriction.urn}
    pending = [restriction.filler]
    while pending:
        filler = pending.pop()
        if filler is None or not filler.startswith(_RESTRICTION_NS) or filler in seen:
            continue
        seen.add(filler)
        triples += ctx.by_subject.get((filler, triple_kind), [])
        inner = index.by_urn.get(filler)
        if inner is not None:
            pending.append(inner.filler)
    return triples


def _finalize(
    ctx: _Ctx,
    kind: str,
    severity: Severity,
    subject: str,
    summary: str,
    details: dict[str, object],
    subsumed: list[Change],
) -> Change:
    """Attach subsumption + change_id to a restriction change and register it."""
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
        logger.debug("restriction change %s has no matching Layer 0 changes", change_id)
    return change


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _decoded_dict(restriction: DecodedRestriction) -> dict[str, object]:
    """The ``before`` / ``after`` payload for a restriction in ``details``."""
    return {
        "kind": restriction.kind,
        "cardinality": restriction.cardinality,
        "filler": restriction.filler,
        "urn": restriction.urn,
    }


def _is_nested(restriction: DecodedRestriction) -> bool:
    """Whether the restriction's filler is itself a reified restriction URN."""
    return restriction.filler is not None and restriction.filler.startswith(_RESTRICTION_NS)


def _nesting_depth(index: RestrictionIndex, restriction: DecodedRestriction) -> int:
    """Number of nested restriction levels rooted at ``restriction`` (cycle-safe)."""
    depth = 1
    seen: set[str] = {restriction.urn}
    filler = restriction.filler
    while filler is not None and filler.startswith(_RESTRICTION_NS) and filler not in seen:
        seen.add(filler)
        depth += 1
        inner = index.by_urn.get(filler)
        filler = inner.filler if inner is not None else None
    return depth


def _on_property(change: Change) -> str:
    value = change.details.get("on_property")
    return value if isinstance(value, str) else ""
