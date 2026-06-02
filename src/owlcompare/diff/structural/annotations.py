"""Layer 1 — annotation structural diff (Component 09, final Layer 1 slice).

Consolidates add+remove pairs of annotation triples that share a subject,
predicate and language tag into single, human-readable events — *"Label changed
on era:Track (fr): 'Voie' → 'Voie ferrée'"* — and folds version bumps and other
ontology-level metadata edits into one ``ontology_metadata_changed`` each. Runs
last in the Layer 1 pipeline (entities → hierarchy → restrictions → annotations),
sharing one :class:`SubsumptionRegistry`: an annotation on a class that was
wholly added or removed is deferred to that class's Component 06 change rather
than re-reported.

Two values special-case out of the generic annotation handling: ``owl:deprecated
true`` becomes ``entity_deprecated`` / ``entity_undeprecated`` (its own
semantics, not a label edit), and any annotation on the ``owl:Ontology`` subject
becomes ``ontology_metadata_changed``. See ``specs/09-structural-annotations.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rdflib import OWL, RDF
from rdflib.namespace import DC, DCTERMS, FOAF, PROV, RDFS, SKOS, NamespaceManager
from rdflib.term import Literal as RDFLiteral
from rdflib.term import URIRef

from owlcompare.exceptions import DiffError
from owlcompare.model import OntologySnapshot, shorten_iri

from .._common import Change, DiffOptions, Severity
from .._subsumption import SubsumptionRegistry
from ._annotation_index import AnnotationIndex, AnnotationValue
from ._annotation_index import build as build_index

logger = logging.getLogger(__name__)

_RDF_TYPE = str(RDF.type)
_DEPRECATED = str(OWL.deprecated)
_COMMENT = str(RDFS.comment)

# Namespaces whose local name is a good short display form for the predicate.
_KNOWN_NAMESPACES: tuple[str, ...] = (
    str(RDFS),
    str(OWL),
    str(SKOS),
    str(DCTERMS),
    str(DC),
    str(FOAF),
    str(PROV),
)

# Comment-style annotations whose (often long) value is omitted from the summary
# (Q1). The full before/after text is always available in ``details``.
_COMMENT_LIKE: frozenset[str] = frozenset(
    {
        _COMMENT,
        str(SKOS.definition),
        str(SKOS.note),
        str(SKOS.scopeNote),
        str(SKOS.example),
        str(SKOS.editorialNote),
        str(SKOS.changeNote),
        str(SKOS.historyNote),
    }
)

# Ordering within the structural section (spec § Ordering): changed first, then
# added/removed, then deprecation, then ontology metadata. Ties broken by
# subject, predicate, then language (None first).
_KIND_RANK: dict[str, int] = {
    "annotation_changed": 0,
    "annotation_added": 1,
    "annotation_removed": 2,
    "entity_deprecated": 3,
    "entity_undeprecated": 4,
    "ontology_metadata_changed": 5,
}

# (value, is_iri_value) pair — the part of an AnnotationValue that varies within
# a single (subject, predicate, language) bucket.
_ValueKey = tuple[str, bool]

Layer0EdgeIndex = dict[tuple[str | None, str | None, str], list[Change]]


@dataclass(slots=True)
class _Ctx:
    """Per-call state threaded through the annotation diff helpers."""

    index_a: AnnotationIndex
    index_b: AnnotationIndex
    prefixes: dict[str, str]
    registry: SubsumptionRegistry
    nsm_a: NamespaceManager
    nsm_b: NamespaceManager
    by_edge: Layer0EdgeIndex
    iris_a: set[str]
    iris_b: set[str]
    ontology_iri: str | None

    def short(self, iri: str) -> str:
        """Prefixed display form for an IRI."""
        return shorten_iri(iri, self.prefixes)


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    layer0_changes: list[Change],
    registry: SubsumptionRegistry,
    options: DiffOptions | None = None,
) -> list[Change]:
    """Compute Layer 1 annotation-level differences.

    Emits ``annotation_changed`` / ``annotation_added`` / ``annotation_removed``
    for label/comment/metadata edits on existing entities, ``entity_deprecated``
    / ``entity_undeprecated`` for ``owl:deprecated true`` flips, and
    ``ontology_metadata_changed`` for annotation edits on the ``owl:Ontology``
    subject itself.

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
    del options  # no annotation-slice knobs yet; kept for a uniform signature
    if not a.canonical or not b.canonical:
        raise DiffError("inputs must be canonicalized first")

    ctx = _Ctx(
        index_a=build_index(a),
        index_b=build_index(b),
        prefixes={**a.prefixes, **b.prefixes},
        registry=registry,
        nsm_a=a.graph.namespace_manager,
        nsm_b=b.graph.namespace_manager,
        by_edge=_index_by_edge(layer0_changes),
        iris_a=a.entities.all_iris(),
        iris_b=b.entities.all_iris(),
        ontology_iri=a.metadata.iri or b.metadata.iri,
    )

    changes: list[Change] = []
    changes.extend(_diff_entities(ctx))
    changes.extend(_diff_ontology(ctx))

    changes.sort(key=_sort_key)
    return changes


# --------------------------------------------------------------------------- #
# Per-entity annotation diff
# --------------------------------------------------------------------------- #


def _diff_entities(ctx: _Ctx) -> list[Change]:
    """Diff every entity subject's annotations, grouped by predicate and language."""
    subjects = sorted(set(ctx.index_a.by_subject) | set(ctx.index_b.by_subject))
    changes: list[Change] = []
    for subject in subjects:
        preds_a = ctx.index_a.by_subject.get(subject, {})
        preds_b = ctx.index_b.by_subject.get(subject, {})
        if _defer_entity(ctx, subject, preds_a, preds_b):
            continue
        changes.extend(_diff_deprecated(ctx, subject, preds_a, preds_b))
        changes.extend(_diff_predicates(ctx, subject, preds_a, preds_b))
    return changes


def _diff_predicates(
    ctx: _Ctx,
    subject: str,
    preds_a: dict[str, dict[str | None, tuple[AnnotationValue, ...]]],
    preds_b: dict[str, dict[str | None, tuple[AnnotationValue, ...]]],
) -> list[Change]:
    """Diff every (predicate, language) bucket for one subject (deprecated excluded)."""
    changes: list[Change] = []
    for predicate in sorted(set(preds_a) | set(preds_b)):
        if predicate == _DEPRECATED:
            continue  # handled by _diff_deprecated
        langs_a = preds_a.get(predicate, {})
        langs_b = preds_b.get(predicate, {})
        for language in sorted(set(langs_a) | set(langs_b), key=_language_rank):
            values_a = langs_a.get(language, ())
            values_b = langs_b.get(language, ())
            changes.extend(_diff_bucket(ctx, subject, predicate, language, values_a, values_b))
    return changes


def _diff_bucket(
    ctx: _Ctx,
    subject: str,
    predicate: str,
    language: str | None,
    values_a: tuple[AnnotationValue, ...],
    values_b: tuple[AnnotationValue, ...],
) -> list[Change]:
    """Classify one (subject, predicate, language) bucket into add/remove/change."""
    set_a = {(v.value, v.is_iri_value) for v in values_a}
    set_b = {(v.value, v.is_iri_value) for v in values_b}
    if set_a == set_b:
        return []
    # annotation_changed only for the unambiguous single-value-each case (Q2).
    if len(set_a) == 1 and len(set_b) == 1:
        return [_changed_annotation(ctx, subject, predicate, language, set_a, set_b)]
    changes: list[Change] = []
    for value_key in sorted(set_a - set_b):
        changes.append(
            _single_annotation(ctx, subject, predicate, language, value_key, added=False)
        )
    for value_key in sorted(set_b - set_a):
        changes.append(_single_annotation(ctx, subject, predicate, language, value_key, added=True))
    return changes


def _changed_annotation(
    ctx: _Ctx,
    subject: str,
    predicate: str,
    language: str | None,
    set_a: set[_ValueKey],
    set_b: set[_ValueKey],
) -> Change:
    """Emit ``annotation_changed`` for a single-value swap (info severity)."""
    before_value, before_iri = next(iter(set_a))
    after_value, after_iri = next(iter(set_b))
    short = _predicate_short(predicate)
    noun = _predicate_noun(short)
    summary = f"{noun} changed on {ctx.short(subject)}{_lang_paren(language)}"
    if predicate not in _COMMENT_LIKE:
        summary += (
            f": {_render(ctx, before_value, before_iri)} → {_render(ctx, after_value, after_iri)}"
        )
    details: dict[str, object] = {
        "entity_iri": subject,
        "predicate_iri": predicate,
        "predicate_short": short,
        "language": language,
        "before": {"value": before_value, "is_iri_value": before_iri},
        "after": {"value": after_value, "is_iri_value": after_iri},
    }
    subsumed = _match_value(
        ctx, subject, predicate, before_value, before_iri, language, removed=True
    ) + _match_value(ctx, subject, predicate, after_value, after_iri, language, removed=False)
    return _finalize(ctx, "annotation_changed", "info", subject, summary, details, subsumed)


def _single_annotation(
    ctx: _Ctx,
    subject: str,
    predicate: str,
    language: str | None,
    value_key: _ValueKey,
    *,
    added: bool,
) -> Change:
    """Emit ``annotation_added`` / ``annotation_removed`` (both info severity)."""
    value, is_iri = value_key
    short = _predicate_short(predicate)
    noun = _predicate_noun(short)
    verb = "added" if added else "removed"
    preposition = "on" if added else "from"
    summary = f"{noun} {verb} {preposition} {ctx.short(subject)}{_lang_paren(language)}"
    if predicate not in _COMMENT_LIKE:
        summary += f": {_render(ctx, value, is_iri)}"
    details: dict[str, object] = {
        "entity_iri": subject,
        "predicate_iri": predicate,
        "predicate_short": short,
        "language": language,
        "value": value,
        "is_iri_value": is_iri,
    }
    subsumed = _match_value(ctx, subject, predicate, value, is_iri, language, removed=not added)
    return _finalize(ctx, f"annotation_{verb}", "info", subject, summary, details, subsumed)


# --------------------------------------------------------------------------- #
# owl:deprecated special case
# --------------------------------------------------------------------------- #


def _diff_deprecated(
    ctx: _Ctx,
    subject: str,
    preds_a: dict[str, dict[str | None, tuple[AnnotationValue, ...]]],
    preds_b: dict[str, dict[str | None, tuple[AnnotationValue, ...]]],
) -> list[Change]:
    """Emit ``entity_deprecated`` / ``entity_undeprecated`` for ``owl:deprecated true`` flips."""
    dep_a = _is_deprecated(preds_a)
    dep_b = _is_deprecated(preds_b)
    if dep_a == dep_b:
        return []
    kind: str
    severity: Severity
    if dep_b:
        summary = f"{ctx.short(subject)} marked deprecated"
        kind, severity = "entity_deprecated", "non_breaking"
        subsumed = _match_deprecated(ctx, subject, removed=False)
    else:
        summary = f"{ctx.short(subject)} unmarked deprecated"
        kind, severity = "entity_undeprecated", "info"
        subsumed = _match_deprecated(ctx, subject, removed=True)
    details: dict[str, object] = {"entity_iri": subject}
    return [_finalize(ctx, kind, severity, subject, summary, details, subsumed)]


def _is_deprecated(
    preds: dict[str, dict[str | None, tuple[AnnotationValue, ...]]],
) -> bool:
    """Whether the subject carries ``owl:deprecated true`` among ``preds``."""
    for values in preds.get(_DEPRECATED, {}).values():
        if any(value.value == "true" for value in values):
            return True
    return False


def _match_deprecated(ctx: _Ctx, subject: str, *, removed: bool) -> list[Change]:
    """Layer 0 changes for the subject's ``owl:deprecated`` triple (object-agnostic)."""
    triple_kind = "triple_removed" if removed else "triple_added"
    return list(ctx.by_edge.get((subject, _DEPRECATED, triple_kind), []))


# --------------------------------------------------------------------------- #
# Ontology-level metadata diff
# --------------------------------------------------------------------------- #


def _diff_ontology(ctx: _Ctx) -> list[Change]:
    """Diff annotations on the ``owl:Ontology`` subject into ``ontology_metadata_changed``."""
    if ctx.ontology_iri is None:
        return []
    buckets_a = _ontology_buckets(ctx.index_a)
    buckets_b = _ontology_buckets(ctx.index_b)
    changes: list[Change] = []
    for key in sorted(set(buckets_a) | set(buckets_b), key=lambda k: (k[0], _language_rank(k[1]))):
        predicate, language = key
        set_a = buckets_a.get(key, set())
        set_b = buckets_b.get(key, set())
        if set_a == set_b:
            continue
        if len(set_a) == 1 and len(set_b) == 1:
            changes.append(
                _ontology_change(ctx, predicate, language, next(iter(set_a)), next(iter(set_b)))
            )
            continue
        for value_key in sorted(set_a - set_b):
            changes.append(_ontology_change(ctx, predicate, language, value_key, None))
        for value_key in sorted(set_b - set_a):
            changes.append(_ontology_change(ctx, predicate, language, None, value_key))
    return changes


def _ontology_buckets(index: AnnotationIndex) -> dict[tuple[str, str | None], set[_ValueKey]]:
    """Group the ontology annotations by ``(predicate, language)`` → set of value keys."""
    buckets: dict[tuple[str, str | None], set[_ValueKey]] = {}
    for value in index.ontology_annotations:
        buckets.setdefault((value.predicate, value.language), set()).add(
            (value.value, value.is_iri_value)
        )
    return buckets


def _ontology_change(
    ctx: _Ctx,
    predicate: str,
    language: str | None,
    before: _ValueKey | None,
    after: _ValueKey | None,
) -> Change:
    """Emit one ``ontology_metadata_changed`` (info) for a changed metadata property."""
    assert ctx.ontology_iri is not None
    pred_display = ctx.short(predicate)
    summary = f"Ontology metadata: {pred_display} {_ontology_phrase(ctx, before, after)}"
    details: dict[str, object] = {
        "ontology_iri": ctx.ontology_iri,
        "predicate_iri": predicate,
        "predicate_short": _predicate_short(predicate),
        "language": language,
        "before": {"value": before[0], "is_iri_value": before[1]} if before else None,
        "after": {"value": after[0], "is_iri_value": after[1]} if after else None,
    }
    subsumed: list[Change] = []
    if before is not None:
        subsumed += _match_value(
            ctx, ctx.ontology_iri, predicate, before[0], before[1], language, removed=True
        )
    if after is not None:
        subsumed += _match_value(
            ctx, ctx.ontology_iri, predicate, after[0], after[1], language, removed=False
        )
    return _finalize(
        ctx, "ontology_metadata_changed", "info", ctx.ontology_iri, summary, details, subsumed
    )


def _ontology_phrase(ctx: _Ctx, before: _ValueKey | None, after: _ValueKey | None) -> str:
    """Render the ``'old' → 'new'`` / ``'x' added`` / ``'x' removed`` value phrase."""
    if before is not None and after is not None:
        return f"{_render(ctx, *before)} → {_render(ctx, *after)}"
    if after is not None:
        return f"{_render(ctx, *after)} added"
    assert before is not None
    return f"{_render(ctx, *before)} removed"


# --------------------------------------------------------------------------- #
# Coordination with Component 06
# --------------------------------------------------------------------------- #


def _defer_entity(
    ctx: _Ctx,
    subject: str,
    preds_a: dict[str, dict[str | None, tuple[AnnotationValue, ...]]],
    preds_b: dict[str, dict[str | None, tuple[AnnotationValue, ...]]],
) -> bool:
    """If ``subject`` was wholly added/removed by Component 06, defer its annotations.

    The annotation triples are part of the entity's introduction/removal, so they
    are subsumed under Component 06's ``class_*`` / ``*_property_*`` /
    ``individual_*`` change instead of producing standalone annotation changes
    here (spec § Step 2.1). Punning is respected: an IRI that still exists as some
    entity kind on both sides is *not* deferred — its annotations remain attached.
    """
    added = _wholly_changed(ctx, subject)
    if added is None:
        return False
    change_id = _entity_change_id(ctx, subject, added=added)
    if change_id is not None:
        preds = preds_b if added else preds_a
        triples: list[Change] = []
        for predicate, languages in preds.items():
            for language, values in languages.items():
                for value in values:
                    triples += _match_value(
                        ctx,
                        subject,
                        predicate,
                        value.value,
                        value.is_iri_value,
                        language,
                        removed=not added,
                    )
        if triples:
            ctx.registry.register(change_id, triples)
    return True


def _wholly_changed(ctx: _Ctx, iri: str) -> bool | None:
    """``True`` if ``iri`` was wholly added, ``False`` if wholly removed, else ``None``."""
    in_a = iri in ctx.iris_a
    in_b = iri in ctx.iris_b
    if in_a == in_b:
        return None  # present on both sides (or neither) → process normally
    return in_b


def _entity_change_id(ctx: _Ctx, iri: str, *, added: bool) -> str | None:
    """Component 06's change id explaining ``iri``'s ``rdf:type`` triple, if any."""
    triple_kind = "triple_added" if added else "triple_removed"
    for change in ctx.by_edge.get((iri, _RDF_TYPE, triple_kind), []):
        explainers = ctx.registry.explainers(SubsumptionRegistry.change_id(change))
        if explainers:
            return explainers[0]
    return None


# --------------------------------------------------------------------------- #
# Layer 0 matching + subsumption
# --------------------------------------------------------------------------- #


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


def _match_value(
    ctx: _Ctx,
    subject: str,
    predicate: str,
    value: str,
    is_iri: bool,
    language: str | None,
    *,
    removed: bool,
) -> list[Change]:
    """Layer 0 changes for the exact annotation triple ``subject <predicate> value``."""
    triple_kind = "triple_removed" if removed else "triple_added"
    nsm = ctx.nsm_a if removed else ctx.nsm_b
    candidates = ctx.by_edge.get((subject, predicate, triple_kind), [])
    if is_iri:
        target = URIRef(value).n3(nsm)
    elif language is not None:
        target = RDFLiteral(value, lang=language).n3(nsm)
    else:
        target = RDFLiteral(value).n3(nsm)
    return [c for c in candidates if c.details.get("object") == target]


def _finalize(
    ctx: _Ctx,
    kind: str,
    severity: Severity,
    subject: str,
    summary: str,
    details: dict[str, object],
    subsumed: list[Change],
) -> Change:
    """Attach subsumption + change_id to an annotation change and register it."""
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
        logger.debug("annotation change %s has no matching Layer 0 changes", change_id)
    return change


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _predicate_short(predicate_iri: str) -> str:
    """Short local-name form for a recognized namespace, else the full IRI."""
    for namespace in _KNOWN_NAMESPACES:
        if predicate_iri.startswith(namespace):
            return predicate_iri[len(namespace) :]
    return predicate_iri


def _predicate_noun(predicate_short: str) -> str:
    """Leading summary noun: capitalized for label/comment, else the short form."""
    if predicate_short == "label":
        return "Label"
    if predicate_short == "comment":
        return "Comment"
    return predicate_short


def _render(ctx: _Ctx, value: str, is_iri: bool) -> str:
    """Display a value: prefixed IRI for resources, single-quoted text for literals."""
    return ctx.short(value) if is_iri else f"'{value}'"


def _lang_paren(language: str | None) -> str:
    """`` (fr)`` when a language tag is present, empty string otherwise."""
    return f" ({language})" if language is not None else ""


def _language_rank(language: str | None) -> tuple[bool, str]:
    """Sort key putting ``None`` first, then languages alphabetically."""
    return (language is not None, language or "")


def _sort_key(change: Change) -> tuple[int, str, str, tuple[bool, str]]:
    """Ordering: kind, subject, predicate IRI, then language (None first)."""
    details = change.details
    predicate = details.get("predicate_iri")
    language = details.get("language")
    return (
        _KIND_RANK[change.kind],
        change.subject or "",
        predicate if isinstance(predicate, str) else "",
        _language_rank(language if isinstance(language, str) else None),
    )
