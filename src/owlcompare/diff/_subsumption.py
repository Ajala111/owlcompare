"""Subsumption tracking shared across every Layer 1+ diff slice.

A higher-layer change (e.g. "Class added") *explains* — subsumes — the raw
Layer 0 triple changes that came along with it (the ``rdf:type`` declaration,
the initial ``rdfs:label``, ...). Renderers use this to hide the noise:
Layer 1 changes shown prominently, the triples they explain folded away.

The registry is mutable on purpose. The orchestrator threads one instance
through the layer pipeline (Components 06-09) so each slice can register the
Layer 0 changes it accounts for. See ``specs/06-structural-entities.md``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from ._common import Change

# Derived detail keys are *excluded* from the change-id hash: ``change_id`` would
# be self-referential (it is stored back into ``details`` after computation), and
# ``subsumes`` is itself derived from other changes. Hashing only the intrinsic
# content keeps the id stable regardless of when those keys are populated.
_DERIVED_DETAIL_KEYS = ("change_id", "subsumes")


@dataclass
class SubsumptionRegistry:
    """Tracks which Layer 0 changes are explained by which Layer 1+ changes.

    Mutable on purpose — built incrementally across Layer 1 components.
    The orchestrator passes one registry through the layer pipeline.
    """

    # Map from a Layer 0 change's identity to the list of higher-layer change IDs
    # that explain it.
    explained_by: dict[str, list[str]] = field(default_factory=dict)

    def register(self, higher_change_id: str, layer0_changes: list[Change]) -> None:
        """Mark each given Layer 0 change as subsumed by ``higher_change_id``."""
        for change in layer0_changes:
            key = self.change_id(change)
            explainers = self.explained_by.setdefault(key, [])
            if higher_change_id not in explainers:
                explainers.append(higher_change_id)

    def is_explained(self, layer0_change_id: str) -> bool:
        """Whether any higher-layer change has claimed this Layer 0 change."""
        return bool(self.explained_by.get(layer0_change_id))

    def explainers(self, layer0_change_id: str) -> tuple[str, ...]:
        """All higher-layer change ids that subsume the given Layer 0 change."""
        return tuple(self.explained_by.get(layer0_change_id, ()))

    @staticmethod
    def change_id(change: Change) -> str:
        """Stable identity for a Change record, used as the registry key.

        Format: ``'<layer>:<kind>:<sha1 of summary + sorted details>'``. The
        derived keys (``change_id``, ``subsumes``) are excluded from the hash so
        the id is identical whether or not they have been populated yet.
        """
        intrinsic = {
            key: value for key, value in change.details.items() if key not in _DERIVED_DETAIL_KEYS
        }
        payload = json.dumps(
            {"summary": change.summary, "details": intrinsic},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
        return f"{change.layer}:{change.kind}:{digest}"
