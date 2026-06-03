"""Diff engine package.

Layer 0 (syntactic) and the first Layer 1 slice (structural entities) are
implemented and wired through :mod:`orchestrator`; remaining Layer 1 slices and
Layers 2-3 are planned.
"""

from __future__ import annotations

from . import orchestrator, severity, structural, syntactic
from ._common import Change, DiffLayer, DiffOptions, DiffResult, Severity
from ._subsumption import SubsumptionRegistry
from .severity import SeverityRefinement

__all__ = [
    "Change",
    "DiffLayer",
    "DiffOptions",
    "DiffResult",
    "Severity",
    "SeverityRefinement",
    "SubsumptionRegistry",
    "orchestrator",
    "severity",
    "structural",
    "syntactic",
]
