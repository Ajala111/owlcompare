# Glossary

Domain and project-specific terms, used consistently across docs, code, and CLI output.

## Ontology domain terms

**Axiom**
A single logical statement in an OWL ontology. e.g., `Track rdf:type owl:Class`, `Track rdfs:subClassOf TransportInfrastructure`, `hasGauge rdfs:domain Track`. Roughly corresponds to a triple, but a single OWL axiom may be encoded as several triples (especially restrictions).

**Class**
A type. In OWL, an `owl:Class`. e.g., `era:Track`, `era:BaliseGroup`.

**Object property**
A property whose values are individuals (IRIs). e.g., `era:hasNextTrack`.

**Data property**
A property whose values are literals. e.g., `era:gaugeWidth`.

**Annotation property**
A property used for metadata, not logic. e.g., `rdfs:label`, `rdfs:comment`, `dcterms:created`.

**Individual**
An instance of a class. e.g., `era:track-NO-BN-01-001`.

**Restriction**
A class expression that constrains property usage. e.g., "every Track has at least one gauge" is a restriction on the `hasGauge` property applied to `Track`.

**Cardinality**
The numeric constraint on a property: `min`, `max`, `exact`. e.g., `hasGauge min 1`.

**Domain / Range**
The expected type at the source / target of a property. `domain(hasGauge) = Track`, `range(hasGauge) = xsd:decimal`.

**Subclass / Subproperty axiom**
A hierarchy edge. `subClassOf(A, B)` means every A is a B.

**Imports closure**
The transitive set of ontologies pulled in via `owl:imports`. Diffing across imports closures is *not* a v1 feature.

**Reasoner**
A tool that materializes inferences (entailments) from the asserted axioms. HermiT, Pellet, ELK, FaCT++. We integrate via `owlready2` (v2+).

**Materialization**
The set of triples produced by a reasoner from the asserted ontology. Diffing materializations is what we mean by "inferential diff."

**Punning**
The OWL 2 feature of using the same IRI for entities of different kinds (e.g., a class *and* an individual). Affects our entity index design — IRI alone is not a unique key.

## Project-specific terms

**Snapshot**
A loaded, canonicalized ontology in memory. Represented as `OntologySnapshot`. Not "version", not "instance".

**Canonicalization**
The normalization pass during loading: blank node renaming, restriction reification, list collapsing. Goal: make `loaded(a) == loaded(a_reformatted)` true.

**Change**
A single record in the diff output. Has a layer, kind, severity, subject, before/after, summary, details. The canonical name; not "diff", "delta", or "entry".

**Layer**
One of the four diff layers: syntactic (0), structural (1), inferential (2), impact (3).

**Severity**
The classification applied to a Change: `breaking`, `non_breaking`, `additive`, `info`. See DD-008.

**Rename**
A `Change` pair that we suspect represents a renaming rather than independent addition and deletion. Carries a `confidence` score.

**Fingerprint**
A structural signature of an entity used in rename detection: its set of incoming/outgoing axioms with IRIs elided to placeholders.

**Diff result**
The top-level output object containing all `Change` records, suspected renames, and metadata about the comparison.

**Report**
A rendered representation of the diff result. JSON, Markdown, HTML, or JUnit XML.

## Words we deliberately do *not* use

| Avoid | Use instead | Why |
|-------|-------------|-----|
| "Triple difference" | "Syntactic change" | "Triple" is too low-level; "syntactic" matches our layer name. |
| "Modification" | "Change" | Consistency. |
| "Delta" | "Change" | Vague; "change" is precise. |
| "Concept" | "Class" or "Entity" | "Concept" has SKOS-specific meaning. |
| "Term" | "Entity" | Ambiguous with vocabulary terms. |
| "Schema" | "Ontology" | "Schema" is RDFS/XSD-flavored; we work with full OWL. |
