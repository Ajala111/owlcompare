"""Layer 1 — structural diff package.

Layer 1 interprets the raw triple delta into meaningful entity-level events:
"Class added", "Object property removed", "Track reparented", and so on. Each
slice lives in its own submodule; this package ships :mod:`entities`
(Component 06), :mod:`hierarchy` (Component 07), :mod:`restrictions`
(Component 08) and :mod:`annotations` (Component 09). See the matching specs in
``specs/``.

Note: this package intentionally omits ``from __future__ import annotations``.
That future import binds the module-global name ``annotations`` to a
``__future__._Feature`` object, which would shadow the :mod:`annotations`
submodule attribute on this package (Component 09). The file has no type
annotations of its own, so the future import is unnecessary here.
"""

from . import annotations, entities, hierarchy, restrictions

__all__ = ["annotations", "entities", "hierarchy", "restrictions"]
