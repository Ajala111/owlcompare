# Component 02: Ontology Loader (+ Internal Model)

## Identity

- **Component number:** 02 (includes the work originally scoped as 03)
- **Name:** Ontology loader and internal model
- **Module paths:**
  - `src/owlcompare/model.py` — internal dataclasses
  - `src/owlcompare/loader.py` — loading logic
  - `src/owlcompare/sources.py` — source resolution (path / URL / future: git ref)
- **Roadmap phase:** Phase 1
- **Depends on components:** 01 (uses `OwlCompareError` hierarchy)
- **Depended on by (planned):** 04 (canonicalization), 05–09 (diff layers), all renderers

## Purpose

Read an ontology from a source (file path or URL) in any common RDF serialization, validate it, and produce a normalized `OntologySnapshot` that downstream components can consume without ever touching rdflib directly. Provide an indexed view of all entities (classes, properties, individuals, datatypes) so diff components can look up axioms by entity in O(1).

What would break if we removed it: nothing else can be built. The loader is the gateway between the outside world (files, URLs) and the internal model.

## Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| Source specifier | `str \| pathlib.Path` | CLI args / library caller | File path or `http(s)://` URL. Git refs reserved for v2. |
| Format hint | `str \| None` | optional CLI flag | One of `turtle`, `xml`, `n3`, `nt`, `json-ld`. Auto-detected if absent. |
| Options | `LoadOptions` | optional, dataclass | Strictness flags, base IRI override, timeout (URL fetch). |

## Outputs

| Output | Type | Consumer | Notes |
|--------|------|----------|-------|
| `OntologySnapshot` | dataclass | All downstream components | Frozen, hashable on identity, ~all access via accessor methods |
| `LoadError` (on failure) | exception | CLI / library caller | Subclass of `OwlCompareError`, exit code 3 |

## Public API

```python
# src/owlcompare/model.py

from dataclasses import dataclass, field
from pathlib import Path
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


@dataclass(frozen=True, slots=True)
class Entity:
    """A single named entity in an ontology."""
    iri: str
    kind: EntityKind
    labels: tuple[tuple[str, str], ...]   # ((lang_tag, label), ...) — tuple for hashability
    comments: tuple[tuple[str, str], ...] # ((lang_tag, comment), ...)
    is_deprecated: bool
    # Note: arbitrary annotations live on the snapshot's graph; only the
    # commonly-accessed ones are denormalized onto Entity for fast access.


@dataclass(frozen=True, slots=True)
class EntityIndex:
    """Indexed view of all entities in an OntologySnapshot."""
    classes: dict[str, Entity]                # IRI -> Entity
    object_properties: dict[str, Entity]
    data_properties: dict[str, Entity]
    annotation_properties: dict[str, Entity]
    individuals: dict[str, Entity]
    datatypes: dict[str, Entity]

    def all_iris(self) -> set[str]:
        """Union of every IRI across all entity kinds."""

    def lookup(self, iri: str) -> Entity | None:
        """First entity with this IRI across any kind. None if not found.
        Note: OWL 2 punning permits same IRI across kinds; use kind_of() to enumerate."""

    def kinds_of(self, iri: str) -> tuple[EntityKind, ...]:
        """All kinds the IRI is declared as. Empty tuple if not declared."""

    def __len__(self) -> int: ...
    def counts(self) -> dict[EntityKind, int]: ...


@dataclass(frozen=True, slots=True)
class OntologyMetadata:
    """Metadata extracted from owl:Ontology declaration."""
    iri: str | None              # owl:Ontology IRI
    version_iri: str | None      # owl:versionIRI
    imports: tuple[str, ...]     # owl:imports (not resolved in v1)
    labels: tuple[tuple[str, str], ...]
    comments: tuple[tuple[str, str], ...]
    version_info: str | None     # owl:versionInfo
    prior_version: str | None    # owl:priorVersion
    other_annotations: tuple[tuple[str, str], ...]  # (predicate_iri, value_string)


@dataclass(frozen=True)
class OntologySnapshot:
    """A loaded, indexed ontology. NOT yet canonicalized (Component 04)."""
    metadata: OntologyMetadata
    entities: EntityIndex
    graph: rdflib.Graph              # the raw parsed graph
    prefixes: dict[str, str]         # prefix -> namespace IRI
    source: str                      # human-readable origin description
    format: str                      # detected serialization format

    # Convenience methods
    def axiom_count(self) -> int:
        """Triple count in the graph (proxy for axiom count)."""

    def summary(self) -> str:
        """Human-readable one-screen summary. Used by `owlcompare load`."""


@dataclass(frozen=True, slots=True)
class LoadOptions:
    strict: bool = False             # if True, syntactic warnings become LoadError
    base_iri: str | None = None      # override base IRI for relative URIs
    timeout_seconds: float = 30.0    # URL fetch timeout
    format_hint: str | None = None   # rdflib format string; auto-detected if None
```

```python
# src/owlcompare/sources.py

@dataclass(frozen=True, slots=True)
class ResolvedSource:
    """Result of resolving a source specifier to bytes + metadata."""
    description: str         # human-readable, used as OntologySnapshot.source
    content: bytes
    detected_format: str | None  # from URL extension or HTTP Content-Type
    origin: Literal["file", "url"]


def resolve(specifier: str | Path, timeout_seconds: float = 30.0) -> ResolvedSource:
    """Resolve a source specifier to its bytes. Raises LoadError on failure."""
```

```python
# src/owlcompare/loader.py

def load(
    source: str | Path,
    options: LoadOptions | None = None,
) -> OntologySnapshot:
    """Load an ontology and return its snapshot.

    Raises:
        LoadError: bad source, parse failure, missing required structure.
    """
```

## CLI integration

Add a `load` subcommand to `cli.py`. Purpose: smoke-test the loader from the shell and let users inspect any ontology.

```
owlcompare load [OPTIONS] SOURCE

Arguments:
  SOURCE                File path or URL  [required]

Options:
  --format [turtle|xml|n3|nt|json-ld|trig]   Format hint (auto-detected if absent)
  --strict                                    Treat warnings as errors
  --timeout SECONDS                           Network timeout (default 30)
  --base-iri IRI                              Base IRI for relative references
  --help                                      Show this message and exit
```

Behavior: load, then print `snapshot.summary()` to stdout, exit 0. On `LoadError`, log to stderr and exit 3.

## Internal design

### Source resolution (`sources.py`)

- **File paths:** open and read bytes. If file does not exist or isn't readable → `LoadError`.
- **URLs:** require `http://` or `https://`. Use `httpx` with the configured timeout. Follow redirects (max 5). Capture the final `Content-Type` for format detection. On network or HTTP error → `LoadError`.
- **Format detection priority:**
  1. Explicit `format_hint` from `LoadOptions` if provided.
  2. URL extension or filename extension (`.ttl` → turtle, `.rdf`/`.owl` → xml, `.jsonld` → json-ld, `.nt` → nt, `.n3` → n3, `.trig` → trig).
  3. HTTP `Content-Type` header (text/turtle, application/rdf+xml, application/ld+json, etc.).
  4. If still unknown → attempt rdflib's `guess_format`, then fall back to trying turtle first then xml.
- **No git ref support in v1.** Document as a planned v2 feature.

### Loading (`loader.py`)

1. Resolve source via `sources.resolve()`.
2. Determine format (see priority above).
3. Parse with rdflib into an `rdflib.Graph()`. Wrap any parser exception in `LoadError`.
4. Extract metadata:
   - Find `?o rdf:type owl:Ontology`. If multiple, prefer the one with a `owl:versionIRI`; warn at INFO if zero or multiple found.
   - Pull `owl:versionIRI`, `owl:imports`, `rdfs:label`, `rdfs:comment`, `owl:versionInfo`, `owl:priorVersion`.
5. Build the entity index by scanning the graph for type declarations:
   - `?e rdf:type owl:Class` → class
   - `?e rdf:type owl:ObjectProperty` → object property
   - `?e rdf:type owl:DatatypeProperty` → data property
   - `?e rdf:type owl:AnnotationProperty` → annotation property
   - `?e rdf:type owl:NamedIndividual` → individual
   - `?e rdf:type rdfs:Datatype` → datatype
   - Also recognize `rdfs:Class` as class (RDFS compatibility).
   - **Punning support:** the same IRI can appear under multiple kinds; index each separately.
6. For each indexed entity, denormalize `rdfs:label`, `rdfs:comment`, `owl:deprecated`.
7. Capture all prefixes from the graph's namespace manager into a plain dict.
8. Build and return the `OntologySnapshot`.

### Strict mode

When `strict=True`:
- Missing `owl:Ontology` declaration → `LoadError` (otherwise: warning).
- Multiple `owl:Ontology` declarations → `LoadError` (otherwise: warning, pick one).
- Blank-node-only entities flagged as warnings become errors.

### Performance notes

- Use a single SPARQL query per entity kind rather than iterating triples in Python. Faster on medium ontologies.
- Don't materialize the entity dicts as full Entity objects until iteration is complete (build them in a final pass after all metadata is gathered).
- Target: load a 10k-triple ontology in under 2 seconds on the baseline (DD-005-adjacent performance budget).

## Edge cases & failure modes

- **File not found** → `LoadError`, exit 3.
- **Permission denied on file** → `LoadError`, exit 3.
- **URL fetch fails (DNS, connection, 4xx/5xx)** → `LoadError` with status info, exit 3.
- **URL fetch times out** → `LoadError` mentioning the timeout value, exit 3.
- **Malformed RDF (parse error)** → `LoadError` wrapping the parser exception with line/column if available, exit 3.
- **Empty file** → `LoadError("ontology contains no triples")`, exit 3.
- **Unknown format hint** → `LoadError("unsupported format hint: <x>")`, exit 2 (usage error).
- **No `owl:Ontology` declaration** → permissive: warn at INFO, set `metadata.iri=None`. Strict: `LoadError`.
- **Same IRI declared as both class and individual (punning)** → indexed under both kinds, no error.
- **Blank node where an IRI is expected (e.g., as ontology IRI)** → treat as anonymous (None), warn at INFO.
- **JSON-LD without `@context`** → let rdflib handle; if it fails, wrap in `LoadError`.
- **Very large ontology (> 1M triples)** → loads, possibly slowly; log a warning at INFO level above some threshold (say 500k triples) suggesting Phase 2's chunking (not yet implemented).
- **Source path is a directory** → `LoadError("source is a directory, expected a file")`, exit 3.

## Dependencies to add

```bash
uv add rdflib httpx
```

- **rdflib** — already approved in DD-001.
- **httpx** — chosen over `requests` for: async-ready (future), better timeout handling, modern API, MIT license. Add a DD-015 entry capturing this:

  **DD-015: httpx as the HTTP client.** Pure-Python, MIT, actively maintained, supports both sync and async (we use sync in v1), better default timeout and redirect handling than `requests`, type-hint-friendly. Alternative considered: `requests` (heavier, no async path, slower release cadence). Alternative considered: stdlib `urllib.request` (verbose, weaker error semantics). Decision: httpx.

## Acceptance tests

Located in `tests/unit/test_loader.py`, `tests/unit/test_model.py`, `tests/unit/test_sources.py`, and `tests/integration/test_loader_integration.py`.

### Fixtures to create (`tests/fixtures/`)

Create six small, hand-crafted Turtle files exercising specific scenarios. Each file has a comment header explaining what it tests.

- `fixtures/minimal_class.ttl` — one class, one property, one individual. Simplest possible ontology.
- `fixtures/with_metadata.ttl` — full `owl:Ontology` declaration with versionIRI, imports, labels in two languages.
- `fixtures/punned.ttl` — IRI declared as both class and individual (OWL 2 punning).
- `fixtures/multilingual.ttl` — labels in English, French, and German with proper language tags.
- `fixtures/deprecated.ttl` — entity marked `owl:deprecated true`.
- `fixtures/era_micro.ttl` — small hand-crafted ERA-style fragment (a Track, a BaliseGroup, with realistic IRI patterns).

Also create one malformed file: `fixtures/broken.ttl` (intentional syntax error).

### Test list

**Model (`tests/unit/test_model.py`):**
- [ ] `test_entity_is_frozen` — attempting to mutate raises `dataclasses.FrozenInstanceError`.
- [ ] `test_entity_is_hashable` — entities go into a `set` without error.
- [ ] `test_entity_index_lookup_unknown_iri_returns_none`
- [ ] `test_entity_index_kinds_of_punned_iri_returns_multiple`
- [ ] `test_entity_index_all_iris_unions_kinds`
- [ ] `test_entity_index_counts_matches_dict_lengths`
- [ ] `test_snapshot_axiom_count_matches_graph_len`
- [ ] `test_snapshot_summary_contains_iri_and_counts` — summary string must include the ontology IRI (or "<no ontology IRI>") and per-kind counts.

**Sources (`tests/unit/test_sources.py`):**
- [ ] `test_resolve_file_returns_bytes`
- [ ] `test_resolve_file_missing_raises_load_error`
- [ ] `test_resolve_file_directory_raises_load_error`
- [ ] `test_resolve_file_detects_format_from_extension` — `.ttl` → turtle, `.jsonld` → json-ld, etc. Parametrize across the supported extensions.
- [ ] `test_resolve_url_https_only` — `ftp://` and `file://` URLs are rejected.
- [ ] `test_resolve_url_timeout_raises_load_error` — use a mock or `respx` fixture.
- [ ] `test_resolve_url_4xx_raises_load_error` — mock returning 404.
- [ ] `test_resolve_url_uses_content_type_for_format_detection`

**Loader unit tests (`tests/unit/test_loader.py`):**
- [ ] `test_load_minimal_class_fixture_succeeds`
- [ ] `test_load_minimal_class_indexes_one_class_one_property_one_individual`
- [ ] `test_load_with_metadata_captures_version_iri`
- [ ] `test_load_with_metadata_captures_imports`
- [ ] `test_load_with_metadata_captures_multilingual_labels`
- [ ] `test_load_punned_iri_appears_under_multiple_kinds`
- [ ] `test_load_multilingual_labels_preserved_with_language_tags`
- [ ] `test_load_deprecated_entity_has_is_deprecated_true`
- [ ] `test_load_era_micro_indexes_expected_entities`
- [ ] `test_load_broken_turtle_raises_load_error`
- [ ] `test_load_empty_file_raises_load_error`
- [ ] `test_load_missing_file_raises_load_error_exit_code_3` — `LoadError.exit_code == 3`.
- [ ] `test_load_directory_path_raises_load_error`
- [ ] `test_load_unknown_format_hint_raises_load_error_exit_code_2`
- [ ] `test_load_no_owl_ontology_declaration_warns_not_strict`
- [ ] `test_load_no_owl_ontology_declaration_strict_raises`
- [ ] `test_load_captures_prefixes_from_turtle`
- [ ] `test_load_format_autodetect_from_extension`
- [ ] `test_load_with_format_hint_overrides_extension`

**CLI integration (`tests/unit/test_cli_load.py`):**
- [ ] `test_cli_load_help_lists_options`
- [ ] `test_cli_load_missing_source_exits_2`
- [ ] `test_cli_load_minimal_fixture_exits_0_prints_summary`
- [ ] `test_cli_load_broken_fixture_exits_3`
- [ ] `test_cli_load_missing_file_exits_3`
- [ ] `test_cli_load_strict_flag_propagates`

**Integration (`tests/integration/test_loader_integration.py`):**
- [ ] `test_load_via_python_dash_m_against_fixture` — invokes `python -m owlcompare load fixtures/minimal_class.ttl` via subprocess, asserts exit 0 and summary text on stdout.

## Out of scope (deliberately)

- Canonicalization (Component 04).
- Imports closure resolution — `owl:imports` IRIs are *captured* but not fetched. v2 feature.
- Git ref sources (`git:HEAD~1:path/onto.ttl`) — v2.
- Caching of loaded ontologies — premature.
- SPARQL query optimization — not needed at v1 scale.
- Reasoning/inference — Layer 2 / Component to-be-numbered.
- Schema validation against meta-models (DCAT, SKOS, OBO conventions) — separate concern.

## Open questions

- [ ] **Q1:** Should `owl:Ontology` declarations with blank-node subjects be treated as "no ontology declaration" (since we can't capture a stable IRI), or recorded with `metadata.iri = None`?
  **Proposed:** Record with `metadata.iri = None`, log INFO. The blank-node version IRI and imports are still useful metadata.
- [ ] **Q2:** How do we represent the `format` field on `OntologySnapshot` — using rdflib's internal format string (`"xml"`, `"turtle"`, `"json-ld"`) or a normalized enum (`"turtle"`, `"rdf-xml"`, `"json-ld"`)?
  **Proposed:** Use a normalized lowercase string with a small canonical set: `turtle`, `rdf-xml`, `n-triples`, `n3`, `json-ld`, `trig`. Internal mapping table from rdflib's strings to ours.
- [ ] **Q3:** Should we capture rdflib parser *warnings* (not errors) and attach them to the snapshot, so the report can show "ontology loaded with N warnings"?
  **Proposed:** Yes, but as a v2 polish — for now, just log at INFO. Add to backlog.

If you have a preference, override before implementing; otherwise proceed with the proposed answers.

## References

- `docs/ARCHITECTURE.md` § Loader, § Internal Model
- `docs/DESIGN_DECISIONS.md` § DD-001 (rdflib), § DD-006 (frozen dataclasses), § DD-007 (canonicalization — note: this component does NOT canonicalize)
- `docs/CONVENTIONS.md` § Error handling, § Naming
- `docs/GLOSSARY.md` § Snapshot, § Entity, § Punning
- rdflib documentation: https://rdflib.readthedocs.io/
- httpx documentation: https://www.python-httpx.org/
