"""Layer 1 — structural diff package.

Layer 1 interprets the raw triple delta into meaningful entity-level events:
"Class added", "Object property removed", "Track reparented", and so on. Each
slice lives in its own submodule; this package ships :mod:`entities`
(Component 06) and :mod:`hierarchy` (Component 07). Later slices (restrictions,
annotations) join the same package. See ``specs/06-structural-entities.md`` and
``specs/07-structural-hierarchy.md``.
"""

from __future__ import annotations

from . import entities, hierarchy

__all__ = ["entities", "hierarchy"]
