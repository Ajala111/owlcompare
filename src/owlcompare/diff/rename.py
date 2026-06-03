"""Component 11 — rename detection and cascade consolidation (Phase 3).

A rename surfaces in a raw diff as a removed entity paired with an added entity
under a new IRI, plus a scatter of "consequence" changes elsewhere (a subclass
edge that now points at the new IRI, a domain/range or restriction filler that
was substituted). This component re-reads the post-Layer-1, *pre-severity*
:class:`DiffResult`, pairs the removed/added entities into a single ``*_renamed``
change, and subsumes the cascade consequences that are explained purely by the
IRI substitution.

Three confidence tiers, in priority order: ``certain`` (a user-supplied mapping —
:mod:`owlcompare.rename_mapping`), ``high`` (a shared ``rdfs:label``), and
``medium`` (a structural fingerprint match — :mod:`._rename_evidence`). The
``min_confidence`` argument is the floor a candidate must clear to be applied; it
also gates which heuristics run at all. See ``specs/11-rename-detection.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Literal

from owlcompare.model import shorten_iri
from owlcompare.rename_mapping import RenameMapping, empty

from ._common import Change, DiffOptions, DiffResult
from ._rename_evidence import (
    ACCEPT_THRESHOLD,
    SEPARATION_THRESHOLD,
    EntityFingerprint,
    build_fingerprint,
    score,
    shared_counts,
)
from ._subsumption import SubsumptionRegistry
from .structural._hierarchy_index import build as build_hierarchy

logger = logging.getLogger(__name__)

RenameConfidence = Literal["certain", "high", "medium", "low"]

# Entity kinds that can be renamed (individuals and datatypes are out of scope).
_RENAMEABLE_KINDS: tuple[str, ...] = (
    "class",
    "object_property",
    "data_property",
    "annotation_property",
)

# Confidence tiers ranked for the ``min_confidence`` floor: a candidate is
# applied iff its tier rank >= the floor's rank.
_TIER_RANK: dict[str, int] = {"certain": 3, "high": 2, "medium": 1, "low": 0}

# Human-facing noun per entity kind, for summaries.
_KIND_NOUN: dict[str, str] = {
    "class": "Class",
    "object_property": "Object property",
    "data_property": "Data property",
    "annotation_property": "Annotation property",
}

# Synthetic restriction/list URNs are never rename candidates.
_SYNTHETIC_PREFIX = "urn:owlcompare:"

# --------------------------------------------------------------------------- #
# Cascade family classification
# --------------------------------------------------------------------------- #

# Single before/after changes that become a no-op once the renamed IRI is
# substituted in (and are therefore pure cascade consequences).
_SINGLE_COLLAPSE_KINDS = frozenset(
    {
        "class_reparented",
        "property_reparented",
        "domain_changed",
        "range_changed",
        "complement_set",
        "restriction_changed",
    }
)

# Directional ``*_added`` / ``*_removed`` changes whose removed/added pair
# collapses when the pair differs only by the renamed IRI. Maps change kind to
# (family token, direction).
_PAIR_FAMILY: dict[str, tuple[str, str]] = {
    "class_parent_added": ("parent", "added"),
    "class_parent_removed": ("parent", "removed"),
    "property_parent_added": ("parent", "added"),
    "property_parent_removed": ("parent", "removed"),
    "equivalent_class_added": ("equivalent", "added"),
    "equivalent_class_removed": ("equivalent", "removed"),
    "disjoint_added": ("disjoint", "added"),
    "disjoint_removed": ("disjoint", "removed"),
    "domain_added": ("domain", "added"),
    "domain_removed": ("domain", "removed"),
    "range_added": ("range", "added"),
    "range_removed": ("range", "removed"),
    "restriction_added": ("restriction", "added"),
    "restriction_removed": ("restriction", "removed"),
}


@dataclass(frozen=True, slots=True)
class RenameCandidate:
    """An inferred or asserted rename pairing."""

    removed_iri: str  # IRI in A
    added_iri: str  # IRI in B
    entity_kind: str  # 'class', 'object_property', 'data_property', 'annotation_property'
    confidence: RenameConfidence
    evidence: tuple[str, ...]  # human-readable rationale lines
    score: float  # 0.0-1.0 normalized fingerprint match score


@dataclass(slots=True)
class _CandidateIndex:
    """Mutable inverted index over the diff's ``*_added`` / ``*_removed`` changes.

    Entries are consumed (popped) as candidates are accepted, so each later
    heuristic only sees still-unpaired entities.
    """

    removed_by_kind: dict[str, dict[str, Change]]
    added_by_kind: dict[str, dict[str, Change]]


def detect(
    result: DiffResult,
    mapping: RenameMapping | None = None,
    min_confidence: RenameConfidence = "high",
    options: DiffOptions | None = None,
) -> DiffResult:
    """Detect renames in a ``DiffResult`` and consolidate them with their cascades.

    Returns a new ``DiffResult`` where each accepted rename removes the paired
    ``*_removed`` / ``*_added`` changes, adds one ``*_renamed`` change, and
    subsumes any cascade consequences explained purely by the IRI substitution.
    The original ``DiffResult`` is not mutated.

    Args:
        result: A Layer-1 ``DiffResult`` (pre-severity) with ``*_added`` /
            ``*_removed`` changes to pair.
        mapping: A user-supplied mapping (highest priority, ``certain``).
        min_confidence: Minimum confidence to accept. ``high`` by default. Lower
            floors find more pairings but risk false positives; the floor also
            gates which heuristics run.
        options: Reserved for future knobs; unused.

    Returns:
        A new ``DiffResult`` with renames consolidated. ``metadata`` gains
        ``rename_candidates`` (all considered) and ``renames_applied`` (accepted).
    """
    del options  # reserved for future knobs
    mapping = mapping or empty()

    changes = list(result.changes)
    index = _build_candidate_index(changes)
    fingerprints = _build_fingerprints(result, index)

    considered: list[RenameCandidate] = []
    accepted: list[RenameCandidate] = []

    accepted.extend(_apply_mapping(mapping, index, considered))
    if _tier_ge("high", min_confidence):
        accepted.extend(_apply_label(index, fingerprints, considered))
    if _tier_ge("medium", min_confidence):
        accepted.extend(_apply_fingerprint(index, fingerprints, considered))

    applied = [c for c in accepted if _tier_ge(c.confidence, min_confidence)]
    new_changes = _consolidate(changes, applied, result)

    new_metadata = dict(result.metadata)
    new_metadata["rename_candidates"] = tuple(considered)
    new_metadata["renames_applied"] = tuple(applied)
    return replace(result, changes=tuple(new_changes), metadata=new_metadata)


# --------------------------------------------------------------------------- #
# Indexing & fingerprints
# --------------------------------------------------------------------------- #


def _build_candidate_index(changes: list[Change]) -> _CandidateIndex:
    """Bucket ``*_removed`` / ``*_added`` entity changes by kind and IRI."""
    removed: dict[str, dict[str, Change]] = {kind: {} for kind in _RENAMEABLE_KINDS}
    added: dict[str, dict[str, Change]] = {kind: {} for kind in _RENAMEABLE_KINDS}
    for change in changes:
        if change.subject is None or change.subject.startswith(_SYNTHETIC_PREFIX):
            continue
        parsed = _parse_entity_change(change.kind)
        if parsed is None:
            continue
        kind, direction = parsed
        bucket = removed[kind] if direction == "removed" else added[kind]
        bucket[change.subject] = change
    return _CandidateIndex(removed_by_kind=removed, added_by_kind=added)


def _parse_entity_change(kind: str) -> tuple[str, str] | None:
    """Map a change kind like ``class_removed`` to ``('class', 'removed')``."""
    for direction in ("removed", "added"):
        suffix = f"_{direction}"
        if kind.endswith(suffix):
            entity_kind = kind[: -len(suffix)]
            if entity_kind in _RENAMEABLE_KINDS:
                return entity_kind, direction
    return None


def _build_fingerprints(
    result: DiffResult, index: _CandidateIndex
) -> dict[tuple[str, str, str], EntityFingerprint]:
    """Fingerprint every candidate, keyed by ``(side, kind, iri)`` (side a/b)."""
    hierarchy_a = build_hierarchy(result.a)
    hierarchy_b = build_hierarchy(result.b)
    fps: dict[tuple[str, str, str], EntityFingerprint] = {}
    for kind in _RENAMEABLE_KINDS:
        for iri in index.removed_by_kind[kind]:
            fps[("a", kind, iri)] = build_fingerprint(result.a, iri, kind, hierarchy_a)
        for iri in index.added_by_kind[kind]:
            fps[("b", kind, iri)] = build_fingerprint(result.b, iri, kind, hierarchy_b)
    return fps


# --------------------------------------------------------------------------- #
# Step 3 — user mapping (certain)
# --------------------------------------------------------------------------- #


def _apply_mapping(
    mapping: RenameMapping, index: _CandidateIndex, considered: list[RenameCandidate]
) -> list[RenameCandidate]:
    """Apply the user mapping first; consumes matched entities from the index."""
    by_kind = {
        "class": mapping.classes,
        "object_property": mapping.object_properties,
        "data_property": mapping.data_properties,
        "annotation_property": mapping.annotation_properties,
    }
    cycles = _mapping_cycles(by_kind)
    accepted: list[RenameCandidate] = []
    for kind, pairs in by_kind.items():
        for old, new in pairs:
            if (old, new) in cycles:
                logger.warning("ignoring cyclic rename mapping entry %s -> %s", old, new)
                continue
            removed = index.removed_by_kind[kind]
            added = index.added_by_kind[kind]
            if old not in removed or new not in added:
                logger.info("rename mapping entry skipped (IRI not in diff): %s -> %s", old, new)
                continue
            del removed[old]
            del added[new]
            candidate = RenameCandidate(
                removed_iri=old,
                added_iri=new,
                entity_kind=kind,
                confidence="certain",
                evidence=("user-supplied mapping",),
                score=1.0,
            )
            considered.append(candidate)
            accepted.append(candidate)
    return accepted


def _mapping_cycles(
    by_kind: dict[str, tuple[tuple[str, str], ...]],
) -> set[tuple[str, str]]:
    """Detect ``A -> B`` AND ``B -> A`` entries (nonsensical); both get dropped."""
    pairs = {pair for entries in by_kind.values() for pair in entries}
    return {(old, new) for (old, new) in pairs if (new, old) in pairs}


# --------------------------------------------------------------------------- #
# Step 4 — label matching (high)
# --------------------------------------------------------------------------- #


def _apply_label(
    index: _CandidateIndex,
    fingerprints: dict[tuple[str, str, str], EntityFingerprint],
    considered: list[RenameCandidate],
) -> list[RenameCandidate]:
    """Pair entities that share at least one exact label, requiring uniqueness."""
    accepted: list[RenameCandidate] = []
    for kind in _RENAMEABLE_KINDS:
        removed_iris = sorted(index.removed_by_kind[kind])
        added_iris = sorted(index.added_by_kind[kind])

        # Build the bipartite label-overlap relation between removed and added.
        overlap: dict[str, list[str]] = {r: [] for r in removed_iris}
        reverse: dict[str, list[str]] = {a: [] for a in added_iris}
        for r in removed_iris:
            labels_r = set(fingerprints[("a", kind, r)].labels)
            for a in added_iris:
                if labels_r & set(fingerprints[("b", kind, a)].labels):
                    overlap[r].append(a)
                    reverse[a].append(r)

        for r in removed_iris:
            matches = overlap[r]
            # A high-confidence rename must be unique on *both* sides (Step 4).
            if len(matches) != 1:
                continue
            a = matches[0]
            if len(reverse[a]) != 1 or a not in index.added_by_kind[kind]:
                continue
            shared = sorted(
                set(fingerprints[("a", kind, r)].labels) & set(fingerprints[("b", kind, a)].labels)
            )
            evidence = tuple(_format_label(lang, text) for lang, text in shared)
            del index.removed_by_kind[kind][r]
            del index.added_by_kind[kind][a]
            candidate = RenameCandidate(
                removed_iri=r,
                added_iri=a,
                entity_kind=kind,
                confidence="high",
                evidence=evidence,
                score=1.0,
            )
            considered.append(candidate)
            accepted.append(candidate)
    return accepted


def _format_label(lang: str, text: str) -> str:
    rendered = f'"{text}"'
    if lang:
        rendered += f"@{lang}"
    return f"matching label {rendered}"


# --------------------------------------------------------------------------- #
# Step 5 — structural fingerprint matching (medium)
# --------------------------------------------------------------------------- #


def _apply_fingerprint(
    index: _CandidateIndex,
    fingerprints: dict[tuple[str, str, str], EntityFingerprint],
    considered: list[RenameCandidate],
) -> list[RenameCandidate]:
    """Pair still-unpaired entities by structural fingerprint similarity."""
    accepted: list[RenameCandidate] = []
    for kind in _RENAMEABLE_KINDS:
        for r in sorted(index.removed_by_kind[kind]):
            fp_r = fingerprints[("a", kind, r)]
            scored = sorted(
                ((score(fp_r, fingerprints[("b", kind, a)]), a) for a in index.added_by_kind[kind]),
                key=lambda pair: (-pair[0], pair[1]),
            )
            if not scored:
                continue
            best_score, best_a = scored[0]
            second_score = scored[1][0] if len(scored) > 1 else 0.0
            if best_score < ACCEPT_THRESHOLD:
                continue
            if best_score - second_score < SEPARATION_THRESHOLD:
                continue
            evidence = _fingerprint_evidence(fp_r, fingerprints[("b", kind, best_a)])
            candidate = RenameCandidate(
                removed_iri=r,
                added_iri=best_a,
                entity_kind=kind,
                confidence="medium",
                evidence=evidence,
                score=best_score,
            )
            considered.append(candidate)
            accepted.append(candidate)
            # Consume both so later removed candidates of this kind cannot re-pair them.
            index.removed_by_kind[kind].pop(r, None)
            index.added_by_kind[kind].pop(best_a, None)
    return accepted


def _fingerprint_evidence(left: EntityFingerprint, right: EntityFingerprint) -> tuple[str, ...]:
    """Build the human-readable rationale lines for a fingerprint match."""
    counts = shared_counts(left, right)
    lines: list[str] = []
    if counts["labels"]:
        lines.append(_plural(counts["labels"], "matching label"))
    if counts["parents"]:
        lines.append(_plural(counts["parents"], "shared parent"))
    if counts["incoming"]:
        lines.append(_plural(counts["incoming"], "shared incoming reference"))
    if counts["outgoing"]:
        lines.append(_plural(counts["outgoing"], "shared outgoing reference"))
    return tuple(lines)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


# --------------------------------------------------------------------------- #
# Step 6 — consolidation & cascade
# --------------------------------------------------------------------------- #


def _consolidate(
    changes: list[Change], accepted: list[RenameCandidate], result: DiffResult
) -> list[Change]:
    """Remove paired add/remove changes + cascade consequences; emit ``*_renamed``.

    Renames are applied in ``before_iri`` order; each consumes its primary pair
    and any cascade consequences from the working list before the next runs.
    """
    prefixes = {**result.a.prefixes, **result.b.prefixes}
    working = list(changes)
    rename_changes: list[Change] = []

    for cand in sorted(accepted, key=lambda c: c.removed_iri):
        removed_kind = f"{cand.entity_kind}_removed"
        added_kind = f"{cand.entity_kind}_added"
        subsumes: list[str] = []
        working = _remove_primary(working, removed_kind, cand.removed_iri, subsumes)
        working = _remove_primary(working, added_kind, cand.added_iri, subsumes)
        working, cascade_ids = _cascade(working, cand.removed_iri, cand.added_iri)
        rename_changes.append(_build_rename_change(cand, prefixes, subsumes, cascade_ids))

    return working + rename_changes


def _remove_primary(
    working: list[Change], kind: str, subject: str, subsumes: list[str]
) -> list[Change]:
    """Drop the ``kind`` change on ``subject`` (the rename's primary pair member)."""
    kept: list[Change] = []
    for change in working:
        if change.kind == kind and change.subject == subject:
            subsumes.append(_cid(change))
            continue
        kept.append(change)
    return kept


def _cascade(working: list[Change], old: str, new: str) -> tuple[list[Change], list[str]]:
    """Subsume changes explained purely by substituting ``old`` with ``new``.

    Two patterns (spec § Step 6): a single before/after change that collapses to
    a no-op after substitution, and a removed/added pair that differs only by the
    substitution. Anything else stays an independent change.
    """
    subsumed: set[int] = set()
    subsumed_ids: list[str] = []

    for change in working:
        if (
            change.layer == "structural"
            and change.kind in _SINGLE_COLLAPSE_KINDS
            and _single_collapses(change, old, new)
        ):
            subsumed.add(id(change))
            subsumed_ids.append(_cid(change))

    removed_by_fam: dict[str, list[Change]] = {}
    added_by_fam: dict[str, list[Change]] = {}
    for change in working:
        if change.layer != "structural" or id(change) in subsumed:
            continue
        family_dir = _PAIR_FAMILY.get(change.kind)
        if family_dir is None:
            continue
        family, direction = family_dir
        target = removed_by_fam if direction == "removed" else added_by_fam
        target.setdefault(family, []).append(change)

    consumed_added: set[int] = set()
    for family, removed_list in removed_by_fam.items():
        added_list = added_by_fam.get(family, [])
        for r in removed_list:
            original = _pair_signature(r, family, old, new, substitute=False)
            substituted = _pair_signature(r, family, old, new, substitute=True)
            if original == substituted:
                continue  # r does not reference the renamed IRI → not a cascade
            match = next(
                (
                    a
                    for a in added_list
                    if id(a) not in consumed_added
                    and _pair_signature(a, family, old, new, substitute=False) == substituted
                ),
                None,
            )
            if match is None:
                continue
            consumed_added.add(id(match))
            subsumed.add(id(r))
            subsumed.add(id(match))
            subsumed_ids.append(_cid(r))
            subsumed_ids.append(_cid(match))

    remaining = [change for change in working if id(change) not in subsumed]
    return remaining, subsumed_ids


def _single_collapses(change: Change, old: str, new: str) -> bool:
    """Whether a single before/after change is a no-op after the substitution."""
    details = change.details
    if change.kind in ("class_reparented", "property_reparented"):
        before_parents = {_subst(p, old, new) for p in details.get("parents_before", [])}
        after_parents = set(details.get("parents_after", []))
        return before_parents == after_parents
    if change.kind in ("domain_changed", "range_changed", "complement_set"):
        return _subst(details.get("before"), old, new) == details.get("after")
    if change.kind == "restriction_changed":
        before_dict = details.get("before") or {}
        after_dict = details.get("after") or {}
        return bool(
            _subst(before_dict.get("filler"), old, new) == after_dict.get("filler")
            and before_dict.get("kind") == after_dict.get("kind")
            and before_dict.get("cardinality") == after_dict.get("cardinality")
        )
    return False


def _pair_signature(change: Change, family: str, old: str, new: str, *, substitute: bool) -> object:
    """Direction-agnostic identity of a pair change, optionally substituting old→new."""

    def s(value: object) -> object:
        return _subst(value, old, new) if substitute else value

    details = change.details
    if family == "parent":
        return (details.get("entity_iri"), s(details.get("parent_iri")))
    if family == "equivalent":
        return (details.get("entity_iri"), s(details.get("other_iri")))
    if family == "disjoint":
        return frozenset({s(details.get("entity_iri")), s(details.get("other_iri"))})
    if family in ("domain", "range"):
        return (details.get("property_iri"), s(details.get("value")))
    # restriction: before holds the decoded dict for _removed, after for _added.
    decoded = details.get("before") or details.get("after") or {}
    return (
        details.get("entity_iri"),
        s(details.get("on_property")),
        s(decoded.get("filler")),
        decoded.get("kind"),
        decoded.get("cardinality"),
    )


def _subst(value: object, old: str, new: str) -> object:
    return new if value == old else value


def _build_rename_change(
    cand: RenameCandidate,
    prefixes: dict[str, str],
    subsumes: list[str],
    cascade_ids: list[str],
) -> Change:
    """Construct the single ``*_renamed`` change for an accepted candidate."""
    noun = _KIND_NOUN[cand.entity_kind]
    before_short = shorten_iri(cand.removed_iri, prefixes)
    after_short = shorten_iri(cand.added_iri, prefixes)
    summary = f"{noun} renamed: {before_short} → {after_short} ({_confidence_phrase(cand)})"
    details: dict[str, object] = {
        "before_iri": cand.removed_iri,
        "after_iri": cand.added_iri,
        "entity_kind": cand.entity_kind,
        "confidence": cand.confidence,
        "score": cand.score,
        "evidence": list(cand.evidence),
        "cascade_subsumes": sorted(cascade_ids),
        "subsumes": list(subsumes),
    }
    change = Change(
        layer="structural",
        kind=f"{cand.entity_kind}_renamed",
        severity="info",  # a rename without semantic change is informational by definition
        subject=cand.added_iri,
        summary=summary,
        details=details,
    )
    change.details["change_id"] = SubsumptionRegistry.change_id(change)
    return change


def _confidence_phrase(cand: RenameCandidate) -> str:
    """The ``(...)`` confidence clause of a rename summary."""
    if cand.confidence == "certain":
        return "certain"
    if cand.evidence:
        return f"{cand.confidence} confidence; {'; '.join(cand.evidence)}"
    return f"{cand.confidence} confidence"


def _tier_ge(tier: str, floor: str) -> bool:
    """Whether ``tier`` clears the ``floor`` (by confidence rank)."""
    return _TIER_RANK[tier] >= _TIER_RANK[floor]


def _cid(change: Change) -> str:
    """The change's stable id (computing it on the fly if not yet stored)."""
    stored = change.details.get("change_id")
    if isinstance(stored, str):
        return stored
    return SubsumptionRegistry.change_id(change)
