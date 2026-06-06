"""Layer 1 — entity-level structural diff.

Detects classes/properties/individuals/datatypes that were added, removed, or
changed in kind between two canonicalized snapshots, and links each structural
change back to the Layer 0 triples it explains (subsumption). This is the first
slice of semantic interpretation: "Class added: era:Platform" instead of three
scattered triple additions. See ``specs/06-structural-entities.md``.
"""

from __future__ import annotations

import logging

from rdflib import OWL, RDF, RDFS
from rdflib.namespace import DCTERMS

from owlcompare.exceptions import DiffError
from owlcompare.model import KIND_ORDER, Entity, EntityKind, OntologySnapshot, shorten_iri

from .._common import Change, DiffOptions, Severity
from .._subsumption import SubsumptionRegistry

logger = logging.getLogger(__name__)

# Severity for each ``<kind>_removed`` change. Additions are uniformly additive,
# so only removals need a table. Mirrors specs/06-structural-entities.md.
_REMOVED_SEVERITY: dict[EntityKind, Severity] = {
    "class": "breaking",
    "object_property": "breaking",
    "data_property": "breaking",
    "annotation_property": "non_breaking",  # annotations are not core semantics
    "individual": "non_breaking",  # data, not schema
    "datatype": "breaking",
}

# Human-facing noun for each entity kind, used to build summaries.
_KIND_NOUN: dict[EntityKind, str] = {
    "class": "Class",
    "object_property": "Object property",
    "data_property": "Data property",
    "annotation_property": "Annotation property",
    "individual": "Individual",
    "datatype": "Datatype",
}

# Layer 0 predicates considered "part of" an entity's declaration. A structural
# add/remove subsumes the Layer 0 triple changes on the same subject carrying one
# of these predicates (type declaration + initial annotations on the entity).
_SUBSUMED_PREDICATES: frozenset[str] = frozenset(
    {
        str(RDF.type),
        str(RDFS.label),
        str(RDFS.comment),
        str(OWL.deprecated),
        str(RDFS.isDefinedBy),
    }
)
_DCTERMS_NS = str(DCTERMS)


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    layer0_changes: list[Change],
    registry: SubsumptionRegistry,
    options: DiffOptions | None = None,
) -> list[Change]:
    """Compute Layer 1 entity-level differences.

    Updates ``registry`` in-place to mark Layer 0 changes that are now explained
    by the structural changes returned here.

    Args:
        a: Baseline snapshot (canonicalized).
        b: Comparison snapshot (canonicalized).
        layer0_changes: Component 05's output, used for subsumption tracking.
        registry: Shared subsumption registry, mutated in place.
        options: Reserved for future layer knobs; unused by this slice.

    Returns:
        A list of ``Change`` records with ``layer="structural"``. See the module
        docstring / spec for the full list of kinds.

    Raises:
        DiffError: if either snapshot is not canonicalized.
    """
    del options  # no entity-slice knobs yet; kept for a uniform layer signature
    if not a.canonical or not b.canonical:
        raise DiffError("inputs must be canonicalized first")

    buckets_a = a.entities.by_kind()
    buckets_b = b.entities.by_kind()

    added: dict[EntityKind, set[str]] = {}
    removed: dict[EntityKind, set[str]] = {}
    for kind in KIND_ORDER:
        iris_a = set(buckets_a[kind])
        iris_b = set(buckets_b[kind])
        removed[kind] = iris_a - iris_b
        added[kind] = iris_b - iris_a

    kind_changes = _resolve_kind_changes(added, removed)

    layer0_index = _index_layer0_by_subject(layer0_changes)
    changes: list[Change] = []

    for kind in KIND_ORDER:
        for iri in removed[kind]:
            entity = buckets_a[kind][iri]
            changes.append(
                _entity_change(iri, kind, entity, a, registry, layer0_index, added=False)
            )
        for iri in added[kind]:
            entity = buckets_b[kind][iri]
            changes.append(_entity_change(iri, kind, entity, b, registry, layer0_index, added=True))

    for iri, from_kind, to_kind in kind_changes:
        changes.append(_kind_changed_change(iri, from_kind, to_kind, a, registry, layer0_index))

    changes.sort(key=lambda c: (c.kind, c.subject or ""))
    return changes


def _resolve_kind_changes(
    added: dict[EntityKind, set[str]],
    removed: dict[EntityKind, set[str]],
) -> list[tuple[str, EntityKind, EntityKind]]:
    """Detect true "kind moves" and strip their add/remove entries in place.

    An IRI is a kind change only when it left *exactly one* kind and joined
    *exactly one* other kind (Q1: a true move, not punning becoming established
    nor a punned IRI merely losing one of its kinds). Mutates ``added`` and
    ``removed`` to drop the IRIs it claims so they don't double-emit.

    Returns:
        ``(iri, from_kind, to_kind)`` tuples.
    """
    removed_kinds: dict[str, list[EntityKind]] = {}
    added_kinds: dict[str, list[EntityKind]] = {}
    for kind in KIND_ORDER:
        for iri in removed[kind]:
            removed_kinds.setdefault(iri, []).append(kind)
        for iri in added[kind]:
            added_kinds.setdefault(iri, []).append(kind)

    moves: list[tuple[str, EntityKind, EntityKind]] = []
    for iri, from_kinds in removed_kinds.items():
        to_kinds = added_kinds.get(iri)
        if to_kinds is None or len(from_kinds) != 1 or len(to_kinds) != 1:
            continue
        from_kind, to_kind = from_kinds[0], to_kinds[0]
        moves.append((iri, from_kind, to_kind))
        removed[from_kind].discard(iri)
        added[to_kind].discard(iri)
    return moves


def _entity_change(
    iri: str,
    kind: EntityKind,
    entity: Entity,
    snapshot: OntologySnapshot,
    registry: SubsumptionRegistry,
    layer0_index: dict[str, list[Change]],
    *,
    added: bool,
) -> Change:
    """Build one ``<kind>_added`` / ``<kind>_removed`` change and record subsumption."""
    change_kind = f"{kind}_{'added' if added else 'removed'}"
    severity: Severity = "additive" if added else _REMOVED_SEVERITY[kind]
    label_text, language = _best_label(entity)

    summary = _summary(_KIND_NOUN[kind], added, iri, snapshot, label_text, language)
    details: dict[str, object] = {
        "entity_iri": iri,
        "entity_kind": kind,
        "label": label_text,
        "language": language,
    }
    subsumed = _matching_layer0(layer0_index, iri, added=added)
    return _finalize(change_kind, severity, iri, summary, details, subsumed, registry)


def _kind_changed_change(
    iri: str,
    from_kind: EntityKind,
    to_kind: EntityKind,
    a: OntologySnapshot,
    registry: SubsumptionRegistry,
    layer0_index: dict[str, list[Change]],
) -> Change:
    """Build the single ``entity_kind_changed`` change for a true kind move."""
    prefixed = shorten_iri(iri, a.prefixes)
    summary = f"Entity kind changed: {prefixed} ({from_kind} → {to_kind})"
    details: dict[str, object] = {
        "entity_iri": iri,
        "from_kind": from_kind,
        "to_kind": to_kind,
    }
    # A move touches the type declaration on both sides, so subsume both the
    # removed (old kind) and added (new kind) Layer 0 triples.
    subsumed = _matching_layer0(layer0_index, iri, added=None)
    return _finalize("entity_kind_changed", "breaking", iri, summary, details, subsumed, registry)


def _finalize(
    change_kind: str,
    severity: Severity,
    iri: str,
    summary: str,
    details: dict[str, object],
    subsumed: list[Change],
    registry: SubsumptionRegistry,
) -> Change:
    """Attach subsumption + change_id to a structural change and register it."""
    # Sorted for a deterministic JSON contract across processes (DD-021).
    details["subsumes"] = sorted(SubsumptionRegistry.change_id(c) for c in subsumed)
    change = Change(
        layer="structural",
        kind=change_kind,
        severity=severity,
        subject=iri,
        summary=summary,
        details=details,
    )
    change_id = SubsumptionRegistry.change_id(change)
    change.details["change_id"] = change_id
    if subsumed:
        registry.register(change_id, subsumed)
    else:
        logger.debug("structural change %s has no matching Layer 0 changes", change_id)
    return change


def _summary(
    noun: str,
    added: bool,
    iri: str,
    snapshot: OntologySnapshot,
    label_text: str | None,
    language: str | None,
) -> str:
    """Compose an ``<Noun> added/removed: prefix:local "label"@lang`` summary."""
    prefixed = shorten_iri(iri, snapshot.prefixes)
    verb = "added" if added else "removed"
    summary = f"{noun} {verb}: {prefixed}"
    if label_text is not None:
        rendered = f'"{label_text}"'
        if language is not None:
            rendered += f"@{language}"
        summary += f" {rendered}"
    return summary


def _best_label(entity: Entity) -> tuple[str | None, str | None]:
    """Return ``(text, language)`` for the most prominent label, or ``(None, None)``.

    Priority (Q2): ``en`` first, then the no-language-tag default, then
    alphabetical by language tag. ``entity.labels`` holds ``(lang, text)`` pairs.
    """
    if not entity.labels:
        return None, None
    best_lang, best_text = min(entity.labels, key=_label_rank)
    return best_text, (best_lang or None)


def _label_rank(pair: tuple[str, str]) -> tuple[int, str]:
    lang = pair[0]
    if lang == "en":
        return (0, "")
    if lang == "":
        return (1, "")
    return (2, lang)


def _index_layer0_by_subject(layer0_changes: list[Change]) -> dict[str, list[Change]]:
    """Bucket Layer 0 changes by their ``subject_iri`` for fast subsumption lookup."""
    index: dict[str, list[Change]] = {}
    for change in layer0_changes:
        subject_iri = change.details.get("subject_iri")
        if subject_iri is not None:
            index.setdefault(subject_iri, []).append(change)
    return index


def _matching_layer0(
    layer0_index: dict[str, list[Change]],
    iri: str,
    *,
    added: bool | None,
) -> list[Change]:
    """Layer 0 changes on ``iri`` whose predicate is part of the declaration.

    ``added=True`` matches only triple additions, ``added=False`` only removals,
    ``added=None`` (kind change) matches both directions.
    """
    matches: list[Change] = []
    for change in layer0_index.get(iri, ()):
        if added is True and change.kind != "triple_added":
            continue
        if added is False and change.kind != "triple_removed":
            continue
        if _is_declaration_predicate(change.details.get("predicate_iri")):
            matches.append(change)
    return matches


def _is_declaration_predicate(predicate_iri: str | None) -> bool:
    if predicate_iri is None:
        return False
    return predicate_iri in _SUBSUMED_PREDICATES or predicate_iri.startswith(_DCTERMS_NS)
