"""Ontology loader: resolved source → :class:`OntologySnapshot`.

See ``specs/02-loader.md`` for the contract. Canonicalization is NOT performed
here — that belongs to Component 04 (DD-007).
"""

from __future__ import annotations

import logging
from pathlib import Path

import rdflib
from rdflib import OWL, RDF, RDFS
from rdflib.term import Node

from owlcompare.exceptions import LoadError
from owlcompare.model import (
    Entity,
    EntityIndex,
    EntityKind,
    LoadOptions,
    OntologyMetadata,
    OntologySnapshot,
)
from owlcompare.sources import resolve

logger = logging.getLogger(__name__)

# Above this triple count we log an INFO heads-up; Phase 2 chunking is TBD.
_LARGE_ONTOLOGY_THRESHOLD = 500_000

# rdflib format string → our normalized public form (Q2 answer in spec).
_NORMALIZED_FORMAT: dict[str, str] = {
    "turtle": "turtle",
    "ttl": "turtle",
    "xml": "rdf-xml",
    "application/rdf+xml": "rdf-xml",
    "nt": "n-triples",
    "ntriples": "n-triples",
    "n3": "n3",
    "json-ld": "json-ld",
    "trig": "trig",
}

# Accepted CLI/library format hints → rdflib format string.
_FORMAT_HINT_TO_RDFLIB: dict[str, str] = {
    "turtle": "turtle",
    "ttl": "turtle",
    "xml": "xml",
    "rdf-xml": "xml",
    "n3": "n3",
    "nt": "nt",
    "n-triples": "nt",
    "json-ld": "json-ld",
    "jsonld": "json-ld",
    "trig": "trig",
}

# Triple-predicates handled explicitly; everything else under owl:Ontology
# becomes part of ``other_annotations``.
_KNOWN_ONTOLOGY_PREDICATES: frozenset[rdflib.URIRef] = frozenset(
    {
        RDF.type,
        RDFS.label,
        RDFS.comment,
        OWL.versionIRI,
        OWL.imports,
        OWL.versionInfo,
        OWL.priorVersion,
    }
)

_KIND_TO_TYPE_IRIS: dict[EntityKind, tuple[rdflib.URIRef, ...]] = {
    "class": (OWL.Class, RDFS.Class),
    "object_property": (OWL.ObjectProperty,),
    "data_property": (OWL.DatatypeProperty,),
    "annotation_property": (OWL.AnnotationProperty,),
    "individual": (OWL.NamedIndividual,),
    "datatype": (RDFS.Datatype,),
}


def _normalize_format(rdflib_format: str) -> str:
    return _NORMALIZED_FORMAT.get(rdflib_format, rdflib_format)


def _resolve_format(format_hint: str | None, detected: str | None) -> str:
    """Pick the rdflib format string to parse with.

    Priority: explicit hint > extension/content-type > default ``turtle``.
    """
    if format_hint:
        rdflib_fmt = _FORMAT_HINT_TO_RDFLIB.get(format_hint.lower())
        if rdflib_fmt is None:
            raise LoadError(
                f"unsupported format hint: {format_hint}",
                exit_code=2,
            )
        return rdflib_fmt
    if detected:
        return detected
    return "turtle"


def _literal_pairs(
    graph: rdflib.Graph, subject: Node, predicate: rdflib.URIRef
) -> tuple[tuple[str, str], ...]:
    """Sorted ``((lang_tag, value), ...)`` pairs for a (subject, predicate)."""
    pairs: list[tuple[str, str]] = []
    for obj in graph.objects(subject, predicate):
        if isinstance(obj, rdflib.Literal):
            pairs.append((obj.language or "", str(obj)))
        else:
            pairs.append(("", str(obj)))
    return tuple(sorted(pairs))


def _single_value(graph: rdflib.Graph, subject: Node, predicate: rdflib.URIRef) -> str | None:
    for obj in graph.objects(subject, predicate):
        return str(obj)
    return None


def _select_ontology_subject(
    graph: rdflib.Graph,
) -> tuple[Node | None, int]:
    """Return ``(chosen_subject, count_found)``.

    With multiple declarations, prefer one that carries ``owl:versionIRI``.
    """
    subjects = list(graph.subjects(RDF.type, OWL.Ontology))
    if not subjects:
        return None, 0
    if len(subjects) == 1:
        return subjects[0], 1
    for subject in subjects:
        if list(graph.objects(subject, OWL.versionIRI)):
            return subject, len(subjects)
    return subjects[0], len(subjects)


def _extract_metadata(graph: rdflib.Graph, subject: Node | None) -> OntologyMetadata:
    if subject is None:
        return OntologyMetadata(
            iri=None,
            version_iri=None,
            imports=(),
            labels=(),
            comments=(),
            version_info=None,
            prior_version=None,
            other_annotations=(),
        )

    iri: str | None = str(subject) if isinstance(subject, rdflib.URIRef) else None
    if iri is None:
        # Q1 answer: blank-node subject still yields useful metadata, only the
        # ontology IRI is unrecoverable.
        logger.info("owl:Ontology subject is a blank node; metadata.iri set to None")

    imports = tuple(
        sorted(
            str(obj)
            for obj in graph.objects(subject, OWL.imports)
            if isinstance(obj, rdflib.URIRef)
        )
    )
    others: list[tuple[str, str]] = []
    for predicate, obj in graph.predicate_objects(subject):
        if predicate in _KNOWN_ONTOLOGY_PREDICATES:
            continue
        others.append((str(predicate), str(obj)))

    return OntologyMetadata(
        iri=iri,
        version_iri=_single_value(graph, subject, OWL.versionIRI),
        imports=imports,
        labels=_literal_pairs(graph, subject, RDFS.label),
        comments=_literal_pairs(graph, subject, RDFS.comment),
        version_info=_single_value(graph, subject, OWL.versionInfo),
        prior_version=_single_value(graph, subject, OWL.priorVersion),
        other_annotations=tuple(sorted(others)),
    )


def _build_entity(graph: rdflib.Graph, iri: str, kind: EntityKind) -> Entity:
    subject = rdflib.URIRef(iri)
    is_deprecated = any(
        isinstance(obj, rdflib.Literal) and bool(obj.toPython())
        for obj in graph.objects(subject, OWL.deprecated)
    )
    return Entity(
        iri=iri,
        kind=kind,
        labels=_literal_pairs(graph, subject, RDFS.label),
        comments=_literal_pairs(graph, subject, RDFS.comment),
        is_deprecated=is_deprecated,
    )


def _build_index(graph: rdflib.Graph) -> EntityIndex:
    per_kind: dict[EntityKind, dict[str, Entity]] = {}
    for kind, type_iris in _KIND_TO_TYPE_IRIS.items():
        entities: dict[str, Entity] = {}
        for type_iri in type_iris:
            for subject in graph.subjects(RDF.type, type_iri):
                if not isinstance(subject, rdflib.URIRef):
                    continue
                iri = str(subject)
                if iri in entities:
                    continue
                entities[iri] = _build_entity(graph, iri, kind)
        per_kind[kind] = entities
    return EntityIndex(
        classes=per_kind["class"],
        object_properties=per_kind["object_property"],
        data_properties=per_kind["data_property"],
        annotation_properties=per_kind["annotation_property"],
        individuals=per_kind["individual"],
        datatypes=per_kind["datatype"],
    )


def _enforce_strict_ontology_count(description: str, num_ontologies: int, strict: bool) -> None:
    if not strict:
        if num_ontologies == 0:
            logger.info("No owl:Ontology declaration found in %s", description)
        elif num_ontologies > 1:
            logger.info(
                "Multiple owl:Ontology declarations in %s (%d found); selecting one",
                description,
                num_ontologies,
            )
        return
    if num_ontologies == 0:
        raise LoadError(f"no owl:Ontology declaration in {description} (strict)")
    if num_ontologies > 1:
        raise LoadError(
            f"multiple owl:Ontology declarations in {description} ({num_ontologies} found, strict)"
        )


def load(source: str | Path, options: LoadOptions | None = None) -> OntologySnapshot:
    """Load an ontology from a path or URL and return its snapshot.

    Raises:
        LoadError: bad source, parse failure, or strict-mode violation.
    """
    opts = options or LoadOptions()
    resolved = resolve(source, timeout_seconds=opts.timeout_seconds)
    rdflib_format = _resolve_format(opts.format_hint, resolved.detected_format)

    # bind_namespaces="none" suppresses rdflib's default core/rdflib prefix
    # auto-bindings (brick, csvw, dcat, etc.) so ``snapshot.prefixes`` contains
    # only what the parsed source actually declared.
    graph = rdflib.Graph(bind_namespaces="none")
    try:
        graph.parse(
            data=resolved.content,
            format=rdflib_format,
            publicID=opts.base_iri,
        )
    except LoadError:
        raise
    except Exception as exc:
        raise LoadError(
            f"failed to parse {resolved.description} as {rdflib_format}: {exc}"
        ) from exc

    if len(graph) == 0:
        raise LoadError(f"ontology contains no triples: {resolved.description}")

    if len(graph) > _LARGE_ONTOLOGY_THRESHOLD:
        logger.info(
            "Large ontology: %d triples (above %d threshold)",
            len(graph),
            _LARGE_ONTOLOGY_THRESHOLD,
        )

    subject, num_ontologies = _select_ontology_subject(graph)
    _enforce_strict_ontology_count(resolved.description, num_ontologies, opts.strict)

    metadata = _extract_metadata(graph, subject)
    entities = _build_index(graph)
    prefixes = {prefix: str(namespace) for prefix, namespace in graph.namespaces()}

    return OntologySnapshot(
        metadata=metadata,
        entities=entities,
        graph=graph,
        prefixes=prefixes,
        source=resolved.description,
        format=_normalize_format(rdflib_format),
    )
