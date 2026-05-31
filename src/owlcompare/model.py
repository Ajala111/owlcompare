"""Internal data model for loaded ontologies.

Downstream components (diff layers, renderers) consume ``OntologySnapshot``
without ever touching ``rdflib`` directly. See DD-006 (frozen dataclasses) and
``specs/02-loader.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import rdflib

EntityKind = Literal[
    "class",
    "object_property",
    "data_property",
    "annotation_property",
    "individual",
    "datatype",
]

# Canonical ordering used by lookup() and summary() so output is deterministic.
KIND_ORDER: tuple[EntityKind, ...] = (
    "class",
    "object_property",
    "data_property",
    "annotation_property",
    "individual",
    "datatype",
)


@dataclass(frozen=True, slots=True)
class Entity:
    """A single named entity in an ontology."""

    iri: str
    kind: EntityKind
    labels: tuple[tuple[str, str], ...]
    comments: tuple[tuple[str, str], ...]
    is_deprecated: bool


# NOTE: ``eq=False`` on EntityIndex is deliberate — the dataclass embeds
# mutable / non-hashable members (dicts); identity-based equality and hash
# are what we want. See Component 02 spec § Public API. Do NOT flip to
# eq=True: dataclasses would auto-generate __hash__/__eq__ that recurse into
# the dicts and break at runtime.
@dataclass(frozen=True, slots=True, eq=False)
class EntityIndex:
    """Indexed view of all entities in an ``OntologySnapshot``."""

    classes: dict[str, Entity]
    object_properties: dict[str, Entity]
    data_properties: dict[str, Entity]
    annotation_properties: dict[str, Entity]
    individuals: dict[str, Entity]
    datatypes: dict[str, Entity]

    def by_kind(self) -> dict[EntityKind, dict[str, Entity]]:
        """Return a fresh ``{kind: {iri: Entity}}`` mapping in ``KIND_ORDER``."""
        return {
            "class": self.classes,
            "object_property": self.object_properties,
            "data_property": self.data_properties,
            "annotation_property": self.annotation_properties,
            "individual": self.individuals,
            "datatype": self.datatypes,
        }

    def all_iris(self) -> set[str]:
        """Union of every IRI across all entity kinds."""
        result: set[str] = set()
        for bucket in self.by_kind().values():
            result.update(bucket.keys())
        return result

    def lookup(self, iri: str) -> Entity | None:
        """Return the first matching entity (by ``KIND_ORDER``) or ``None``.

        OWL 2 punning lets the same IRI live under multiple kinds; use
        :meth:`kinds_of` to enumerate them all.
        """
        buckets = self.by_kind()
        for kind in KIND_ORDER:
            ent = buckets[kind].get(iri)
            if ent is not None:
                return ent
        return None

    def kinds_of(self, iri: str) -> tuple[EntityKind, ...]:
        """All kinds the IRI is declared as. Empty tuple if not declared."""
        buckets = self.by_kind()
        return tuple(kind for kind in KIND_ORDER if iri in buckets[kind])

    def __len__(self) -> int:
        return sum(len(bucket) for bucket in self.by_kind().values())

    def counts(self) -> dict[EntityKind, int]:
        """Map of each ``EntityKind`` to its entity count."""
        return {kind: len(bucket) for kind, bucket in self.by_kind().items()}


# Number of sample IRIs shown per kind in ``OntologySnapshot.summary()`` and in
# the rich renderer. Tuned for "fits on one screen for a small ontology."
SAMPLE_LIMIT: int = 5


def shorten_iri(iri: str, prefixes: dict[str, str]) -> str:
    """Return ``prefix:local`` if any namespace prefixes ``iri``, else ``iri``.

    The longest matching namespace wins so nested prefix declarations don't
    truncate to the shorter alias.
    """
    best_prefix = ""
    best_namespace = ""
    for prefix, namespace in prefixes.items():
        if iri.startswith(namespace) and len(namespace) > len(best_namespace):
            best_prefix = prefix
            best_namespace = namespace
    if not best_namespace:
        return iri
    return f"{best_prefix}:{iri[len(best_namespace) :]}"


def sample_entity_iris(
    entities: dict[str, Entity],
    prefixes: dict[str, str],
    limit: int = SAMPLE_LIMIT,
) -> tuple[list[str], int]:
    """Return ``(formatted_samples, overflow_count)``.

    Each formatted sample is ``prefix:local  (full_iri)`` when shortening
    applies, otherwise the bare IRI. ``overflow_count`` is the number of IRIs
    beyond ``limit`` that were not included.
    """
    iris = sorted(entities)
    head = iris[:limit]
    formatted: list[str] = []
    for iri in head:
        short = shorten_iri(iri, prefixes)
        if short != iri:
            formatted.append(f"{short}  ({iri})")
        else:
            formatted.append(iri)
    return formatted, max(0, len(iris) - limit)


@dataclass(frozen=True, slots=True)
class OntologyMetadata:
    """Metadata extracted from the ``owl:Ontology`` declaration."""

    iri: str | None
    version_iri: str | None
    imports: tuple[str, ...]
    labels: tuple[tuple[str, str], ...]
    comments: tuple[tuple[str, str], ...]
    version_info: str | None
    prior_version: str | None
    other_annotations: tuple[tuple[str, str], ...]


# NOTE: ``eq=False`` on OntologySnapshot is deliberate — the dataclass embeds
# mutable / non-hashable members (rdflib.Graph, prefix dict); identity-based
# equality and hash are what we want. See Component 02 spec § Public API. Do
# NOT flip to eq=True: dataclasses would auto-generate __hash__/__eq__ that
# recurse into the graph and break at runtime.
@dataclass(frozen=True, eq=False)
class OntologySnapshot:
    """A loaded, indexed ontology. NOT yet canonicalized (Component 04)."""

    metadata: OntologyMetadata
    entities: EntityIndex
    graph: rdflib.Graph
    prefixes: dict[str, str]
    source: str
    format: str
    canonical: bool = False

    def axiom_count(self) -> int:
        """Triple count of the underlying graph (proxy for axiom count)."""
        return len(self.graph)

    def summary(self) -> str:
        """Plain-text human-readable summary.

        Returned as a plain string for the library API; the CLI routes
        rendering through ``owlcompare._render.render_summary`` so a TTY gets
        the rich-formatted version and non-TTYs fall back to this text.
        """
        lines: list[str] = []
        lines.append(f"Ontology: {self.metadata.iri or '<no ontology IRI declared>'}")
        if self.metadata.version_iri:
            lines.append(f"Version IRI: {self.metadata.version_iri}")
        if self.metadata.version_info:
            lines.append(f"Version info: {self.metadata.version_info}")
        lines.append(f"Source: {self.source}")
        lines.append(f"Format: {self.format}")
        lines.append(f"Axiom count (triples): {self.axiom_count()}")
        counts = self.entities.counts()
        buckets = self.entities.by_kind()
        lines.append("Entity counts:")
        for kind in KIND_ORDER:
            count = counts[kind]
            lines.append(f"  {kind}: {count}")
            if count == 0:
                continue
            samples, overflow = sample_entity_iris(buckets[kind], self.prefixes)
            for entry in samples:
                lines.append(f"    {entry}")
            if overflow:
                lines.append(f"    ...and {overflow} more")
        if self.metadata.imports:
            lines.append(f"Imports ({len(self.metadata.imports)}):")
            for import_iri in self.metadata.imports:
                lines.append(f"  {import_iri}")
        if self.prefixes:
            lines.append(f"Prefixes ({len(self.prefixes)}):")
            for prefix, namespace in sorted(self.prefixes.items()):
                lines.append(f"  {prefix or '(default)'}: {namespace}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class LoadOptions:
    """Knobs for :func:`owlcompare.loader.load`."""

    strict: bool = False
    base_iri: str | None = None
    timeout_seconds: float = 30.0
    format_hint: str | None = None
