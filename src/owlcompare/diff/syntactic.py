"""Layer 0 — syntactic (triple-set) diff.

After canonicalization two ontologies are two sets of triples; this layer is the
asymmetric difference between them, with no semantic interpretation. It is the
safety net beneath every higher layer: it never silently misses a change. See
``specs/05-syntactic-diff.md``.
"""

from __future__ import annotations

from rdflib import OWL, RDF, RDFS, SKOS
from rdflib.namespace import DCTERMS, NamespaceManager
from rdflib.term import Node, URIRef

from owlcompare.exceptions import DiffError
from owlcompare.model import OntologySnapshot

from ._common import Change, DiffOptions, Severity, shorten_synthetic_iri

# Coarse, RDF-only severity defaults keyed by predicate IRI: ``(removed, added)``.
# Layer 1 overrides these with per-entity classifications; here they are a
# fallback. Predicates absent from the table fall through to ``_DEFAULT_SEVERITY``.
# Mirrors the table in specs/05-syntactic-diff.md § Severity rules.
_SEVERITY_BY_PREDICATE: dict[str, tuple[Severity, Severity]] = {
    str(RDF.type): ("breaking", "additive"),
    str(RDFS.subClassOf): ("breaking", "additive"),
    str(RDFS.subPropertyOf): ("breaking", "additive"),
    str(RDFS.domain): ("breaking", "non_breaking"),
    str(RDFS.range): ("breaking", "non_breaking"),
    # owl:deprecated added → info ("now deprecated"); removed has no row in the
    # spec table ("n/a"), so it falls back to the non_breaking default.
    str(OWL.deprecated): ("non_breaking", "info"),
    str(RDFS.label): ("info", "info"),
    str(RDFS.comment): ("info", "info"),
    str(SKOS.prefLabel): ("info", "info"),
    str(SKOS.altLabel): ("info", "info"),
    str(OWL.imports): ("non_breaking", "non_breaking"),
    str(OWL.versionIRI): ("info", "info"),
    str(OWL.versionInfo): ("info", "info"),
}

_DEFAULT_SEVERITY: tuple[Severity, Severity] = ("non_breaking", "non_breaking")

# Any predicate inside the Dublin Core Terms namespace is annotation metadata.
_DCTERMS_NS = str(DCTERMS)

_SUMMARY_MAX_LEN = 120

# Removals sort before additions: a diff reads "what's gone, then what's new".
_KIND_RANK: dict[str, int] = {"triple_removed": 0, "triple_added": 1}


def diff(
    a: OntologySnapshot,
    b: OntologySnapshot,
    options: DiffOptions | None = None,
) -> list[Change]:
    """Compute Layer 0 (syntactic / triple-set) differences between two snapshots.

    Preconditions:
        ``a.canonical`` and ``b.canonical`` must both be ``True``.

    Args:
        a: Baseline snapshot (canonicalized).
        b: Comparison snapshot (canonicalized).
        options: Reserved for future layer knobs; unused by Layer 0.

    Returns:
        A list of ``Change`` records with ``layer="syntactic"``. Empty if the
        snapshots are triple-set-equal. Ordering is deterministic across runs
        for identical inputs.

    Raises:
        DiffError: if either snapshot is not canonicalized.
    """
    del options  # no Layer 0 knobs yet; kept for a uniform layer signature
    if a is b:
        return []
    if not a.canonical or not b.canonical:
        raise DiffError("inputs must be canonicalized first")

    triples_a = set(a.graph)
    triples_b = set(b.graph)
    removed = triples_a - triples_b
    added = triples_b - triples_a

    nsm_a = a.graph.namespace_manager
    nsm_b = b.graph.namespace_manager

    changes: list[Change] = [_make_change(triple, removed=True, nsm=nsm_a) for triple in removed]
    changes += [_make_change(triple, removed=False, nsm=nsm_b) for triple in added]
    changes.sort(key=_sort_key)
    return changes


def _make_change(
    triple: tuple[Node, Node, Node], *, removed: bool, nsm: NamespaceManager
) -> Change:
    """Build one ``Change`` from an added/removed triple."""
    subject, predicate, obj = triple
    kind = "triple_removed" if removed else "triple_added"
    severity = _severity_for(str(predicate), removed=removed)

    subject_n3 = subject.n3(nsm)
    predicate_n3 = predicate.n3(nsm)
    object_n3 = obj.n3(nsm)

    # Display-only: collapse 64-hex synthetic URNs so they don't dominate the
    # row. details below keeps the full n3 form for machine consumers.
    verb = "Removed" if removed else "Added"
    summary_terms = " ".join(
        _shorten_term_for_display(term, term_n3)
        for term, term_n3 in ((subject, subject_n3), (predicate, predicate_n3), (obj, object_n3))
    )
    summary = _truncate(f"{verb}: {summary_terms}", _SUMMARY_MAX_LEN)

    details = {
        "subject": subject_n3,
        "predicate": predicate_n3,
        "object": object_n3,
        "subject_iri": str(subject) if isinstance(subject, URIRef) else None,
        "predicate_iri": str(predicate) if isinstance(predicate, URIRef) else None,
    }
    return Change(
        layer="syntactic",
        kind=kind,
        severity=severity,
        subject=str(subject) if isinstance(subject, URIRef) else None,
        summary=summary,
        details=details,
    )


def _shorten_term_for_display(term: Node, term_n3: str) -> str:
    """Return the synthetic-shortened form of a term, else its n3 serialization.

    Only URIRefs can be synthetic URNs; their n3 form wraps the URN in angle
    brackets, so we shorten from the raw IRI and fall back to n3 otherwise.
    """
    if isinstance(term, URIRef):
        shortened = shorten_synthetic_iri(str(term))
        if shortened != str(term):
            return shortened
    return term_n3


def _severity_for(predicate_iri: str, *, removed: bool) -> Severity:
    """Look up the coarse Layer 0 severity for a predicate."""
    pair = _SEVERITY_BY_PREDICATE.get(predicate_iri)
    if pair is None and predicate_iri.startswith(_DCTERMS_NS):
        pair = ("info", "info")
    if pair is None:
        pair = _DEFAULT_SEVERITY
    return pair[0] if removed else pair[1]


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _sort_key(change: Change) -> tuple[int, tuple[bool, str], tuple[bool, str], str]:
    """Deterministic ordering: kind, then subject IRI, predicate IRI, full triple.

    ``None`` IRIs sort last within their group via the leading boolean.
    """
    subject_iri = change.details.get("subject_iri")
    predicate_iri = change.details.get("predicate_iri")
    triple_repr = (
        f"{change.details['subject']} {change.details['predicate']} {change.details['object']}"
    )
    return (
        _KIND_RANK[change.kind],
        (subject_iri is None, subject_iri or ""),
        (predicate_iri is None, predicate_iri or ""),
        triple_repr,
    )
