# Design Decisions

This is the project's decision log. Every non-obvious choice that affects multiple components is recorded here, with the reasoning. New contributors (human or AI) should consult this before introducing alternatives.

Format: each decision has a status (`accepted`, `superseded`, `proposed`), a date, a short rationale, and the alternatives considered.

---

## DD-001: Use rdflib as the primary RDF parsing library

**Status:** accepted
**Date:** 2026-05-25

**Decision:** All ontology loading goes through `rdflib`. We do not directly use the Java-based OWL API or Apache Jena.

**Reasoning:**
- Pure Python: no JVM dependency, dramatically simpler distribution.
- Broadest format support out of the box (Turtle, RDF/XML, OWL/XML, JSON-LD, N-Triples, TriG, N-Quads).
- Mature, actively maintained, large ecosystem.

**Alternatives considered:**
- *owlready2 only:* good for OWL-DL reasoning but weaker on general RDF; tightly couples model to its `Ontology` class which is harder to subset.
- *Apache Jena via Py4J:* powerful but JVM is a distribution killer.
- *Pyoxigraph:* fast, but format coverage is narrower and the API is less ergonomic for our use case.

**Implication:** For Layer 2 reasoning we will use `owlready2` as a *secondary* dependency, only loaded when reasoning is requested.

---

## DD-002: Python 3.11 minimum

**Status:** accepted
**Date:** 2026-05-25

**Decision:** Support Python 3.11+. Develop against 3.12.

**Reasoning:**
- 3.11 is now widely available in distributions and CI.
- Gives us: structural pattern matching, `Self` type, tomllib in stdlib, better error messages.
- Going lower means dragging dependency back-compat code.

---

## DD-003: `uv` for package management

**Status:** accepted
**Date:** 2026-05-25

**Decision:** Use `uv` for dependency management, virtual environments, and tool installation. Lockfile is `uv.lock`.

**Reasoning:**
- Order-of-magnitude faster than `pip` and `poetry`.
- Single binary, no bootstrap problem.
- `uv tool install owlcompare` is the cleanest end-user install story.

---

## DD-004: Typer for the CLI

**Status:** accepted
**Date:** 2026-05-25

**Decision:** Use `typer` for the CLI layer.

**Reasoning:**
- Type-hint-driven; matches our overall typing discipline.
- Excellent `--help` output by default.
- Built on Click but with less ceremony.

**Alternatives considered:** Click directly (more verbose), argparse (no), fire (too magical).

---

## DD-005: Self-contained single-file HTML report

**Status:** accepted
**Date:** 2026-05-25

**Decision:** The HTML report is a single `.html` file with embedded CSS, JS, and JSON data. No external assets, no server.

**Reasoning:**
- Easy to share: attach to email, commit to PR, archive in a release.
- Works offline.
- No CDN dependency = no link rot.

**Implication:** Asset size matters. Target: report under 500 KB for medium ontologies.

---

## DD-006: Internal model is frozen dataclasses, not rdflib objects

**Status:** accepted
**Date:** 2026-05-25

**Decision:** The diff engine and renderers operate on our internal `OntologySnapshot` / `Entity` / `Change` dataclasses, not directly on rdflib `Graph` objects.

**Reasoning:**
- Decouples diff logic from rdflib internals; we could swap the parser later.
- Frozen dataclasses are safe to share across threads / serialize / hash.
- Forces an explicit normalization step (DD-007), which is where canonicalization happens.

---

## DD-007: Canonicalize before diffing

**Status:** accepted
**Date:** 2026-05-25

**Decision:** Both ontologies are canonicalized during loading. Canonicalization includes:
- Blank node label normalization (stable, content-based).
- Restriction reification (anonymous restrictions get deterministic identifiers).
- List collapsing (RDF lists → ordered Python lists).
- Triple sorting where order is semantically irrelevant.

**Reasoning:** Without this, every "diff" is dominated by spurious blank-node-label changes and reordering noise.

**Implication:** Loading is more expensive but diffing is dramatically cheaper and more meaningful.

---

## DD-008: Severity classification is built-in, not a post-step

**Status:** accepted
**Date:** 2026-05-25

**Decision:** Each `Change` carries a `severity` field set by the diff layer that produced it, not computed afterward.

**Severity definitions:**
- `breaking`: downstream consumers may fail (removed entity, tightened cardinality, narrowed range).
- `non_breaking`: semantics changed but doesn't break valid existing usage (widened range, relaxed cardinality).
- `additive`: pure addition with no constraint on existing usage.
- `info`: annotation, label, comment, or metadata change.

The CLI exit code maps from severity: any `breaking` → exit 1.

---

## DD-009: Layer 2 and Layer 3 are stubs in v1

**Status:** accepted
**Date:** 2026-05-25

**Decision:** v1 ships with Layers 0 and 1 fully implemented; Layers 2 (inferential) and 3 (impact) exist as stubs that return empty results and a "not yet implemented" notice.

**Reasoning:**
- v1 is already valuable with structural diff alone (most users live there).
- Reasoner integration and SHACL/SPARQL impact analysis each add weeks of work plus heavier dependencies.
- Shipping early validates the UX before we invest in deeper analysis.

**Implication:** The architecture must support these layers cleanly when we add them; the stubs are not throwaway code, they define the interface.

---

## DD-010: Test fixtures are small, hand-crafted ontologies

**Status:** accepted
**Date:** 2026-05-25

**Decision:** Test fixtures in `tests/fixtures/` are small (< 100 axioms), hand-crafted Turtle files designed to exercise specific diff cases — not snapshots of real-world ontologies.

**Reasoning:**
- Test failures must be diagnosable. A failure in a 10k-axiom ontology tells us nothing.
- Fixtures double as documentation: "what does our diff do for case X?"
- Real-world ontologies are used in integration tests, separately.

---

## DD-011: Rendering library for the HTML report

**Status:** proposed (to be confirmed when we build the report component)
**Date:** 2026-05-25

**Decision (tentative):** Use Preact (via CDN, but inlined) for the HTML report's interactivity.

**Reasoning:**
- ~10 KB minified, no build step needed if we inline.
- React-compatible JSX-less API, components are easy to reason about.
- Alternative: Alpine.js (smaller, declarative) — possibly better for a mostly-read-only report. Decide during the report component spec.

**Will revisit at:** `specs/NN-html-report.md`.

---

## DD-012: Smart App Control workaround for mypy on Windows

**Status:** accepted
**Date:** 2026-05-27

**Decision:** On Windows machines where Smart App Control (SAC) is enabled, mypy is installed as a source (pure-Python) build instead of the default mypyc-compiled wheel. This is done with a **local-only**, git-ignored `uv.toml` in the project root:

```toml
no-binary-package = ["mypy"]
```

**Problem:** mypy ships compiled with mypyc, so the wheel contains an unsigned native extension (e.g. `..__mypyc.cp311-win_amd64.pyd`). With Smart App Control on, Windows blocks that DLL from loading and mypy crashes on startup:

```
ImportError: DLL load failed while importing ..__mypyc:
An application control policy has blocked this file.
```

The pure-Python build of mypy (mypyc disabled — the default when building from sdist) has no native extension, so SAC does not block it.

**Why local-only (`uv.toml`, git-ignored) and not `[tool.uv]` in `pyproject.toml`:**
- The issue is specific to this developer's machine/security posture, not to the project.
- CI runs on Linux, where SAC does not exist and the fast compiled wheel works fine; pinning no-binary project-wide would needlessly force every consumer and CI to build mypy from source.
- `uv.toml` takes precedence over `[tool.uv]` and is kept out of version control, so the override never leaks into the shared configuration.

**Implication:** A fresh `uv sync` on this machine rebuilds mypy from source automatically (no manual step). On machines without `uv.toml`, behavior is unchanged. CI is unaffected.

**Alternatives considered:**
- *Disable Smart App Control:* a system-wide security downgrade that requires a Windows reset to fully enable/disable; out of proportion to the problem.
- *Skip mypy locally, rely on CI:* loses the local type-check feedback loop.
- *Pin no-binary in `pyproject.toml`:* would fix it everywhere but slows CI and all contributors for a one-machine issue.
