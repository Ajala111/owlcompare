"""Layer 1 — structural diff package.

Layer 1 interprets the raw triple delta into meaningful entity-level events:
"Class added", "Object property removed", and so on. Each slice lives in its own
submodule; this component ships :mod:`entities`. Later slices (hierarchy,
restrictions, annotations) join the same package. See
``specs/06-structural-entities.md``.
"""

from __future__ import annotations

from . import entities

__all__ = ["entities"]
