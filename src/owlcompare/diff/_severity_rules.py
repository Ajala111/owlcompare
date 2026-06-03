"""Cross-cutting severity rules for Component 10's classifier.

Each rule is a small pure function that inspects one :class:`Change` against the
whole :class:`DiffResult` (the cross-cutting context a single Layer 1 slice never
has) and returns a :class:`SeverityRefinement` when it wants to change that
change's severity, or ``None`` to abstain. :func:`owlcompare.diff.severity.refine`
drives them; it tries the user-override rule first, then the built-ins in
:data:`BUILTIN_RULES` order, first match wins.

The point is not to have many rules — it is to encode the handful of judgments
that need the full picture: an editorial edit on an entity that is being
deprecated, a restriction that only fell away because its property did, a
domain/range whose widening only became decidable once all hierarchy edits were
applied, a class that moved *and* gained a constraint, and the always-on
normalization of subsumed Layer 0 noise. See ``specs/10-severity.md``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from ..severity_config import SeverityConfig
from ..severity_config import matches as _override_matches
from ._common import Change, DiffResult, Severity
from .severity import SeverityRefinement
from .structural._hierarchy_index import build as build_hierarchy

# A built-in cross-cutting rule: classify one change against the full diff, or
# abstain (None). Rule 1 (user overrides) has a different signature — it needs the
# config, not the DiffResult — so refine() invokes it first, separately, and it is
# not part of :data:`BUILTIN_RULES`.
Rule = Callable[[Change, DiffResult], "SeverityRefinement | None"]

_PROPERTY_REMOVED_SUFFIX = "_property_removed"
_ANNOTATION_KINDS = frozenset({"annotation_changed", "annotation_added", "annotation_removed"})
_DOMAIN_RANGE_KINDS = frozenset({"domain_changed", "range_changed"})


def _refinement(
    change: Change, refined: Severity, rule_id: str, rationale: str
) -> SeverityRefinement:
    """Build a refinement record, reading change_id/original from ``change`` itself.

    A change missing ``change_id`` in details (a bug in an earlier component)
    falls back to the empty string; the refinement still applies (spec § Edge
    cases).
    """
    return SeverityRefinement(
        change_id=str(change.details.get("change_id", "")),
        original_severity=change.severity,
        refined_severity=refined,
        rule_id=rule_id,
        rationale=rationale,
    )


# --------------------------------------------------------------------------- #
# Rule 1 — user overrides (config-driven; tried first, wins over the built-ins)
# --------------------------------------------------------------------------- #


def rule_user_override(change: Change, config: SeverityConfig) -> SeverityRefinement | None:
    """Force ``change``'s severity from the first matching config override, if any.

    Returns a refinement even when the override's target equals the original
    severity — so a matching override still *wins* over the built-in rules; the
    caller decides not to record a no-op (Q3).
    """
    for override in config.overrides:
        if _override_matches(change, override):
            return SeverityRefinement(
                change_id=str(change.details.get("change_id", "")),
                original_severity=change.severity,
                refined_severity=override.severity,
                rule_id="user-override",
                rationale=f"matched pattern '{override.kind_pattern}'",
            )
    return None


# --------------------------------------------------------------------------- #
# Rule 2 — annotation on a deprecated entity → info
# --------------------------------------------------------------------------- #


def rule_annotation_on_deprecated(change: Change, result: DiffResult) -> SeverityRefinement | None:
    """Demote an annotation edit to ``info`` when its entity is being deprecated."""
    if change.kind not in _ANNOTATION_KINDS:
        return None
    entity = change.details.get("entity_iri")
    if entity is None:
        return None
    for other in result.changes:
        if other.kind == "entity_deprecated" and other.details.get("entity_iri") == entity:
            return _refinement(
                change,
                "info",
                "annotation-on-deprecated",
                "editorial change on entity being deprecated; reduced significance",
            )
    return None


# --------------------------------------------------------------------------- #
# Rule 3 — restriction removal that is a consequence of property removal → info
# --------------------------------------------------------------------------- #


def rule_restriction_consequential_property_removed(
    change: Change, result: DiffResult
) -> SeverityRefinement | None:
    """Demote a ``restriction_removed`` to ``info`` when its property was removed."""
    if change.kind != "restriction_removed":
        return None
    on_property = change.details.get("on_property")
    if on_property is None:
        return None
    for other in result.changes:
        if other.kind.endswith(_PROPERTY_REMOVED_SUFFIX) and other.subject == on_property:
            return _refinement(
                change,
                "info",
                "restriction-consequential-property-removed",
                "restriction removal is consequence of property removal",
            )
    return None


# --------------------------------------------------------------------------- #
# Rule 4 — domain/range widening only decidable after all Layer 1 edits → demote
# --------------------------------------------------------------------------- #


def rule_domain_range_widening_late(
    change: Change, result: DiffResult
) -> SeverityRefinement | None:
    """Demote a breaking ``domain_changed`` / ``range_changed`` proven to widen.

    Component 08 defaults a single-value domain/range swap to ``breaking`` because
    its narrowing/widening check can be inconclusive on the asserted hierarchy of
    one side. Once every Layer 1 change is in view, the *combined* asserted
    hierarchy (both snapshots) may include a freshly-added ``subClassOf`` edge
    that makes the comparison decidable: if the new value is an ancestor of the
    old, the property's domain/range widened — non-breaking for existing data.
    """
    if change.kind not in _DOMAIN_RANGE_KINDS or change.severity != "breaking":
        return None
    before = change.details.get("before")
    after = change.details.get("after")
    if not isinstance(before, str) or not isinstance(after, str):
        return None
    parents = _combined_class_parents(result)
    if _is_ancestor(after, before, parents):
        return _refinement(
            change,
            "non_breaking",
            "dr-widening-detected-late",
            "domain/range widened (asserted-hierarchy check after all Layer 1 changes applied)",
        )
    return None


def _combined_class_parents(result: DiffResult) -> dict[str, frozenset[str]]:
    """Union of asserted subClassOf parent edges across both snapshots.

    Mirrors Component 08's ``_combined_parents``: the union is what makes a
    late-added edge (present only in B) visible to the widening check.
    """
    merged: dict[str, set[str]] = defaultdict(set)
    for snapshot in (result.a, result.b):
        for child, parents in build_hierarchy(snapshot).class_parents.items():
            merged[child] |= set(parents)
    return {child: frozenset(parents) for child, parents in merged.items()}


def _is_ancestor(ancestor: str, node: str, parents: dict[str, frozenset[str]]) -> bool:
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


# --------------------------------------------------------------------------- #
# Rule 5 — class reparented *and* gained a restriction → breaking
# --------------------------------------------------------------------------- #


def rule_reparent_with_restriction(change: Change, result: DiffResult) -> SeverityRefinement | None:
    """Upgrade a ``class_reparented`` to ``breaking`` when the class also gained a restriction."""
    if change.kind != "class_reparented":
        return None
    entity = change.subject
    if entity is None:
        return None
    for other in result.changes:
        if other.kind == "restriction_added" and other.subject == entity:
            return _refinement(
                change,
                "breaking",
                "reparent-with-new-restriction",
                "class moved with new constraints; combined breaking change",
            )
    return None


# --------------------------------------------------------------------------- #
# Rule 6 — subsumed Layer 0 change → info (always on)
# --------------------------------------------------------------------------- #


def rule_subsumed_layer0(change: Change, result: DiffResult) -> SeverityRefinement | None:
    """Demote any Layer 0 change already explained by a Layer 1 change to ``info``.

    This fires whenever subsumption happened — i.e. on almost every real-world
    diff — so refinement lists are routinely long, but the entries are
    overwhelmingly this low-noise normalization.
    """
    if change.layer != "syntactic":
        return None
    registry = result.metadata.get("subsumption_registry")
    if registry is None:
        return None
    change_id = str(change.details.get("change_id", ""))
    if not change_id or not registry.is_explained(change_id):
        return None
    return _refinement(
        change,
        "info",
        "subsumed-layer0-info",
        "Layer 0 change subsumed by a Layer 1 change",
    )


# Order matters: the first built-in to return a refinement wins for that change.
# It is the spec order (Rules 2 → 6). The cross-cutting rules target disjoint
# change kinds (annotation / restriction_removed / domain-range / reparent /
# syntactic), so they do not in practice contend for the same change; the fixed
# order makes that guarantee explicit and testable. Rule 1 (user overrides) is
# applied ahead of all of these by refine() and is not listed here.
BUILTIN_RULES: tuple[Rule, ...] = (
    rule_annotation_on_deprecated,
    rule_restriction_consequential_property_removed,
    rule_domain_range_widening_late,
    rule_reparent_with_restriction,
    rule_subsumed_layer0,
)
