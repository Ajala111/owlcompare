"""Component 10 — the severity classifier (Phase 2 polish pass).

Layers 0-1 each set a severity on the changes they emit, but only with the
context of their own slice. This component runs last, with every change in view,
and refines those severities using cross-cutting judgments (:mod:`_severity_rules`)
and user-supplied overrides (:mod:`owlcompare.severity_config`). It returns a new
:class:`DiffResult` with the same changes in the same order but possibly different
severities, and an audit trail of every change it made in
``metadata['severity_refinements']``.

User overrides are tried first (they win over built-ins); then the built-in rules
in order, first match wins. A refinement is only recorded when it actually changes
the severity (Q3) — a matching override that equals the original still suppresses
the built-ins, it just is not written to the audit trail. The exit-code policy is
unchanged: any ``breaking`` after refinement → exit 10, so an override that
demotes the last breaking change to ``info`` legitimately yields exit 0.
See ``specs/10-severity.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..severity_config import SeverityConfig, empty
from ._common import Change, DiffOptions, DiffResult, Severity


@dataclass(frozen=True, slots=True)
class SeverityRefinement:
    """A record of one severity change made by Component 10.

    Useful for debugging and for the ``--explain-severity`` output.
    """

    change_id: str
    original_severity: Severity
    refined_severity: Severity
    rule_id: str  # e.g., 'annotation-on-deprecated', 'user-override'
    rationale: str  # short human description


def refine(
    result: DiffResult,
    config: SeverityConfig | None = None,
    options: DiffOptions | None = None,
) -> DiffResult:
    """Apply cross-cutting severity rules and user overrides to a ``DiffResult``.

    Returns a new ``DiffResult`` with the same changes (in the same order) but
    possibly different severities. The list of refinements made is recorded in
    ``result.metadata['severity_refinements']`` (a tuple, possibly empty). The
    original ``DiffResult`` is not mutated.
    """
    del options  # reserved for future knobs; no behaviour yet
    config = config or empty()

    refinements: list[SeverityRefinement] = []
    new_changes: list[Change] = []
    for change in result.changes:
        refinement = _classify(change, result, config)
        if refinement is not None and refinement.refined_severity != change.severity:
            refinements.append(refinement)
            change = replace(change, severity=refinement.refined_severity)
        new_changes.append(change)

    new_metadata = dict(result.metadata)
    new_metadata["severity_refinements"] = tuple(refinements)
    return replace(result, changes=tuple(new_changes), metadata=new_metadata)


def _classify(
    change: Change, result: DiffResult, config: SeverityConfig
) -> SeverityRefinement | None:
    """Pick the winning refinement for one change: user override (Rule 1), else built-ins.

    Imported locally to break the ``severity`` <-> ``_severity_rules`` import
    cycle (the rules construct :class:`SeverityRefinement`, defined above).
    """
    from . import _severity_rules

    override = _severity_rules.rule_user_override(change, config)
    if override is not None:
        return override

    for rule in _severity_rules.BUILTIN_RULES:
        refinement = rule(change, result)
        if refinement is not None:
            return refinement
    return None
