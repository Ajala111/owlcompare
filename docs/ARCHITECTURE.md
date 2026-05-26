# Architecture

## High-level data flow

```
   ontology A ──┐
                ├──> [Loader] ──> [Internal Model] ──┐
   ontology B ──┘                                    │
                                                     ├──> [Diff Engine] ──> [Diff Result]
                                                     │           ▲
   options   ──────────────────────────────────────  ┘           │
                                                                 │
                                            ┌────────────────────┤
                                            │                    │
                                            ▼                    ▼
                                  [Rename Detector]      [Report Renderers]
                                                          │   │   │   │
                                                          ▼   ▼   ▼   ▼
                                                        HTML JSON MD CI/JUnit
```

## Components

### Loader (`src/owlcompare/loader.py`)

**Responsibility:** Read an ontology from a file path, URL, or Git ref, in any common RDF serialization, and produce a normalized internal representation.

**Inputs:**
- File path (`a.ttl`, `a.rdf`, `a.owl`, `a.jsonld`, `a.nt`)
- URL (`http(s)://...`)
- Git ref shorthand (`git:main:path/to/onto.ttl`, `git:HEAD~1:path/to/onto.ttl`)

**Outputs:** An `OntologySnapshot` (see Model) with:
- Parsed RDF graph (rdflib `Graph`)
- Indexed entities (classes, properties, individuals, datatypes)
- Axioms grouped by entity
- Metadata (ontology IRI, version IRI, imports closure, prefixes)

**Key decisions:**
- Use `rdflib` for parsing (broadest format support, pure Python, mature).
- Imports closure is **not** resolved by default in v1 (configurable later). Diffing imports is its own concern.
- All loaded ontologies are normalized: blank nodes get stable labels via canonicalization, lists are collapsed, anonymous restrictions are reified consistently. Without this, trivial reordering produces spurious diffs.

### Internal Model (`src/owlcompare/model.py`)

**Responsibility:** Define the dataclasses that flow between components.

**Key types:**

```python
@dataclass(frozen=True)
class OntologySnapshot:
    iri: str | None
    version_iri: str | None
    graph: rdflib.Graph
    entities: EntityIndex
    prefixes: dict[str, str]
    source: str  # human-readable origin description

@dataclass(frozen=True)
class Entity:
    iri: str
    kind: Literal["class", "object_property", "data_property",
                  "annotation_property", "individual", "datatype"]
    labels: dict[str, str]      # language tag -> label
    annotations: dict[str, list[str]]

@dataclass(frozen=True)
class Change:
    layer: Literal["syntactic", "structural", "inferential", "impact"]
    kind: str                    # e.g., "entity_added", "cardinality_changed"
    severity: Literal["breaking", "non_breaking", "additive", "info"]
    subject: str | None          # IRI of the affected entity, when applicable
    before: Any | None
    after: Any | None
    summary: str                 # one-line human description
    details: dict[str, Any]      # structured details for rendering

@dataclass(frozen=True)
class DiffResult:
    a: OntologySnapshot
    b: OntologySnapshot
    changes: list[Change]
    suspected_renames: list[Rename]
    metadata: dict[str, Any]
```

All public types are frozen dataclasses. Mutability is a footgun for parallel rendering.

### Diff Engine (`src/owlcompare/diff/`)

Four sub-modules, one per layer. Each exposes a single function:

```python
def diff(a: OntologySnapshot, b: OntologySnapshot, opts: DiffOptions) -> list[Change]: ...
```

**Layer 0 — Syntactic (`syntactic.py`):**
- Direct axiom-set difference after canonicalization.
- Cheapest, runs always, used as baseline.

**Layer 1 — Structural (`structural.py`):**
- Entity-level changes: added, removed, type-changed, deprecated.
- Hierarchy: subclass/subproperty edges added/removed.
- Restrictions: cardinality, value restrictions, domain/range.
- Annotations: label, comment, version, deprecation.
- This is the layer most users will spend their time in.

**Layer 2 — Inferential (`inferential.py`):**
- Materialize the inferred class hierarchy + property assertions in both A and B (via a reasoner).
- Diff the materializations.
- A satisfying outcome: many syntactic changes, zero inferential changes → pure refactor.
- **v1: stub only.** Real implementation in v2.

**Layer 3 — Impact (`impact.py`):**
- Given SHACL shapes or SPARQL queries, identify which are affected by changed entities.
- **v1: stub only.** Real implementation in v2.

### Rename Detector (`src/owlcompare/rename.py`)

**Responsibility:** Identify entities that appear deleted-and-added but are likely renamed.

**Heuristics, in order:**
1. Identical `rdfs:label` (any language) → high confidence.
2. Identical structural fingerprint (same incoming/outgoing axioms after IRI elision) → high confidence.
3. High string similarity on local name + identical kind → medium confidence.
4. User-supplied mapping file → certainty.

Outputs `Rename` records with a `confidence: float` in `[0, 1]`. The HTML report shows these in a separate panel; the user can confirm or reject.

### Report Renderers (`src/owlcompare/report/`)

Each renderer takes a `DiffResult` and produces output in one format. Renderers do **not** share state. Adding a new format = adding one file.

- `json_report.py`: canonical machine-readable output. Versioned schema.
- `markdown_report.py`: compact PR-comment-ready summary.
- `html_report.py`: the interactive showcase. Single self-contained HTML file, embedded JSON data, small Preact app (or Alpine.js — TBD in component spec).

### Reasoner adapter (`src/owlcompare/reasoner.py`)

v1: stub. v2: thin adapter over `owlready2` (HermiT, Pellet) and ELK via owlapi. Pluggable.

## Public API surfaces (versioned)

These surfaces are part of the public contract and follow semver:

1. **CLI flags and exit codes** (`owlcompare --help`)
2. **JSON output schema** (versioned via a top-level `"schema_version"` field)
3. **Python library entry points** (`from owlcompare import diff, load`)

Internal modules can change freely between releases.

## Performance targets

| Ontology size | Layer 0+1 diff | Full report generation |
|---------------|-----------------|------------------------|
| Small (< 1k axioms) | < 500 ms | < 1 s |
| Medium (1k–10k axioms) | < 3 s | < 10 s |
| Large (10k–100k axioms) | < 30 s | < 90 s |
| Huge (> 100k axioms) | best effort | best effort |

Measured on a 2023 MacBook Pro M2 baseline.

## Error handling philosophy

- **Library code raises typed exceptions.** Never returns `None` for errors.
- **CLI catches at the boundary**, prints user-friendly messages, returns non-zero exit codes.
- **Loader is the most defensive layer** — bad input is the norm, not the exception.
- **Reasoner errors are isolated**: if Layer 2 fails, Layers 0/1/3 still produce output. The report shows that Layer 2 was skipped and why.
