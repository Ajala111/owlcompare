"""Indexed view of annotation triples per subject / predicate / language (Component 09).

Builds, per snapshot, a structured decoding of every annotation triple — labels,
comments, deprecation flags, metadata — keyed by ``(subject, predicate, language)``
so the diff can pair like-for-like across two snapshots. Language tags are
first-class: ``rdfs:label "Voie"@fr`` and ``rdfs:label "Track"@en`` live in
separate buckets and are never paired with each other.

Annotation properties recognized are the well-known vocabulary terms (``rdfs:``,
``owl:``, ``skos:``, ``dcterms:``/``dc:``, ``foaf:``, ``prov:wasGeneratedBy``)
plus any property the snapshot declares as ``rdf:type owl:AnnotationProperty``.
Restriction / list URN subjects (Component 08's territory) and blank-node
subjects are excluded. Annotations on the ``owl:Ontology`` subject itself are
collected separately into :attr:`AnnotationIndex.ontology_annotations`. See
``specs/09-structural-annotations.md`` § Step 1.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from rdflib import RDF, RDFS, Graph
from rdflib.namespace import DC, DCTERMS, FOAF, OWL, PROV, SKOS
from rdflib.term import Literal as RDFLiteral
from rdflib.term import URIRef

from owlcompare.model import OntologySnapshot

# Canonicalization (Component 04) mints synthetic URNs for reified restrictions
# and collapsed RDF lists; their annotations (if any) belong to Component 08, not
# here, so subjects under this prefix are excluded.
_SYNTHETIC_PREFIX = "urn:owlcompare:"

# Well-known annotation properties recognized by IRI. Namespace-wide families
# (dcterms, dc, foaf) are matched by prefix in ``_ANNOTATION_NAMESPACES`` instead.
_WELL_KNOWN_ANNOTATION_PROPERTIES: frozenset[str] = frozenset(
    {
        str(RDFS.label),
        str(RDFS.comment),
        str(RDFS.seeAlso),
        str(RDFS.isDefinedBy),
        str(OWL.versionInfo),
        str(OWL.priorVersion),
        str(OWL.deprecated),
        str(OWL.incompatibleWith),
        str(OWL.backwardCompatibleWith),
        str(SKOS.prefLabel),
        str(SKOS.altLabel),
        str(SKOS.hiddenLabel),
        str(SKOS.definition),
        str(SKOS.note),
        str(SKOS.scopeNote),
        str(SKOS.example),
        str(SKOS.editorialNote),
        str(SKOS.changeNote),
        str(SKOS.historyNote),
        str(PROV.wasGeneratedBy),
    }
)

# Every property in one of these namespaces counts as an annotation property.
_ANNOTATION_NAMESPACES: tuple[str, ...] = (str(DCTERMS), str(DC), str(FOAF))


@dataclass(frozen=True, slots=True)
class AnnotationValue:
    """A single annotation triple, normalized for diffing."""

    subject: str  # IRI (entity or ontology)
    predicate: str  # annotation property IRI
    language: str | None  # language tag for literals, else None
    value: str  # literal lexical form, or IRI string for resource values
    is_iri_value: bool  # True if the object is an IRI, False if a literal


@dataclass(frozen=True, slots=True)
class AnnotationIndex:
    """Structured view of one snapshot's annotation triples."""

    # subject IRI -> predicate IRI -> language -> tuple of AnnotationValues
    by_subject: dict[str, dict[str, dict[str | None, tuple[AnnotationValue, ...]]]]

    # All annotations whose subject is the ontology declaration itself.
    ontology_annotations: tuple[AnnotationValue, ...]

    # Flat list of every annotation in the index (entity + ontology).
    all_annotations: tuple[AnnotationValue, ...]


def build(snapshot: OntologySnapshot) -> AnnotationIndex:
    """Decode ``snapshot``'s annotation triples into an :class:`AnnotationIndex`.

    Args:
        snapshot: The (typically canonical) snapshot to index.

    Returns:
        An :class:`AnnotationIndex`. Entity annotations are grouped by
        ``(subject, predicate, language)``; annotations on the ``owl:Ontology``
        subject are collected separately. Restriction / list URN subjects and
        blank-node subjects are excluded.
    """
    graph = snapshot.graph
    recognized = _recognized_predicates(graph)
    ontology_iri = snapshot.metadata.iri

    nested: dict[str, dict[str, dict[str | None, list[AnnotationValue]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    ontology: list[AnnotationValue] = []
    everything: list[AnnotationValue] = []

    for subject, predicate, obj in graph:
        if not isinstance(predicate, URIRef):
            continue
        if not _is_annotation_predicate(str(predicate), recognized):
            continue
        if not isinstance(subject, URIRef):
            continue  # blank-node subjects are anonymous → skip (spec § Edge cases)
        subject_iri = str(subject)
        if subject_iri.startswith(_SYNTHETIC_PREFIX):
            continue  # restriction / list URNs belong to Component 08
        decoded = _value_of(subject_iri, str(predicate), obj)
        if decoded is None:
            continue  # blank-node value or otherwise undiffable
        everything.append(decoded)
        if ontology_iri is not None and subject_iri == ontology_iri:
            ontology.append(decoded)
        else:
            nested[subject_iri][str(predicate)][decoded.language].append(decoded)

    return AnnotationIndex(
        by_subject=_freeze(nested),
        ontology_annotations=tuple(sorted(ontology, key=_sort_key)),
        all_annotations=tuple(sorted(everything, key=_sort_key)),
    )


def _recognized_predicates(graph: Graph) -> frozenset[str]:
    """Well-known annotation properties plus user-declared ``owl:AnnotationProperty``."""
    declared = {
        str(subject)
        for subject in graph.subjects(RDF.type, OWL.AnnotationProperty)
        if isinstance(subject, URIRef)
    }
    return _WELL_KNOWN_ANNOTATION_PROPERTIES | declared


def _is_annotation_predicate(predicate_iri: str, recognized: frozenset[str]) -> bool:
    """Whether ``predicate_iri`` is recognized by IRI, namespace, or declaration."""
    if predicate_iri in recognized:
        return True
    return any(predicate_iri.startswith(ns) for ns in _ANNOTATION_NAMESPACES)


def _value_of(subject: str, predicate: str, obj: object) -> AnnotationValue | None:
    """Decode a triple object into an :class:`AnnotationValue`, or ``None`` to skip."""
    if isinstance(obj, URIRef):
        return AnnotationValue(subject, predicate, None, str(obj), True)
    if isinstance(obj, RDFLiteral):
        language = obj.language  # str for @lang literals, None otherwise
        return AnnotationValue(subject, predicate, language, str(obj), False)
    return None  # blank-node value — not meaningfully diffable


def _freeze(
    nested: dict[str, dict[str, dict[str | None, list[AnnotationValue]]]],
) -> dict[str, dict[str, dict[str | None, tuple[AnnotationValue, ...]]]]:
    """Convert the mutable nested defaultdicts into plain dicts of sorted tuples."""
    return {
        subject: {
            predicate: {
                language: tuple(sorted(values, key=_sort_key))
                for language, values in languages.items()
            }
            for predicate, languages in predicates.items()
        }
        for subject, predicates in nested.items()
    }


def _sort_key(value: AnnotationValue) -> tuple[str, str, str, bool]:
    """Deterministic ordering for annotation values."""
    return (value.subject, value.predicate, value.value, value.is_iri_value)
