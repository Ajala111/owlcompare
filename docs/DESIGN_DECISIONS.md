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

---

## DD-013: Hatchling as the build backend

**Status:** accepted
**Date:** 2026-05-28

**Decision:** Use `hatchling` as the build backend (`[build-system]` in `pyproject.toml`), with the version sourced dynamically from `src/owlcompare/_version.py`.

**Reasoning:**
- Single source of truth for the version is essential for a public PyPI package. Manual two-place editing of the version is a known footgun.
- Hatchling is the PyPA-maintained, widely-used default backend for modern Python projects and supports file-based dynamic versioning.
- `uv_build` is still maturing and does not yet support this pattern.
- This affects only the build layer. `uv` remains our package manager and developer tool (DD-003).

**Alternatives considered:**
- *Keep `uv_build` with static version:* simpler config, but introduces a sync-two-files release ritual we'd regret.
- *setuptools:* heavier config, no benefit over Hatchling.
- *PDM-backend, Flit:* viable but no advantage over Hatchling for our needs.

---

## DD-014: Typer private API dependency (`typer._click`)

**Status:** accepted
**Date:** 2026-05-28

**Decision:** `cli.py` imports `ClickException` from the vendored, private `typer._click.exceptions` module, and `typer` is pinned to `>=0.26.2,<0.27` in `pyproject.toml` to guard against a minor-version change silently breaking that import.

**Context:** Typer 0.26 vendors Click as `typer._click`; there is no standalone `click` package installed. The CLI's `main()` runs the Typer app with `standalone_mode=False` (so `KeyboardInterrupt` reaches our handler and maps to exit 130 instead of Click's default exit 1), which means we must catch Click's usage errors ourselves and map them to exit code 2.

`typer` publicly re-exports only `Exit`, `Abort`, and the narrow `BadParameter` — **not** the `ClickException`/`UsageError` base. `BadParameter` alone does not cover "missing argument" (`MissingParameter`) or "no such command" (`UsageError`), so catching the base class is required. We use the public `typer.Exit` / `typer.Abort` where available and reach into `typer._click.exceptions` only for `ClickException`, minimizing the private surface to a single symbol.

**Reasoning:**
- The exit-code contract (usage error → 2) in `specs/01-cli.md` requires catching the `ClickException` base, which has no public Typer path.
- An upper version pin makes the private dependency explicit and prevents an unattended `typer` upgrade from breaking the import at runtime.

**Upgrade path:** Re-evaluate when Typer 0.27 ships. Check whether (a) Typer re-exports a `ClickException` equivalent publicly, or (b) a standalone `click` is available to import from. If either holds, drop the private import and widen the pin.

**Alternatives considered:**
- *Catch only `typer.BadParameter`:* misses `MissingParameter` and "no such command", so some usage errors would fall through to the generic exit-1 handler. Rejected — violates the exit-code contract.
- *Run with `standalone_mode=True` and catch `SystemExit`:* Click would convert `KeyboardInterrupt` to `Abort`/exit 1, breaking the exit-130 requirement. Rejected.
- *Add `click` as a direct dependency:* it is not installed standalone with this Typer build; introducing a second Click would risk version skew against Typer's vendored copy. Rejected.

---

## DD-015: `httpx` as the HTTP client

**Status:** accepted
**Date:** 2026-05-29

**Decision:** Use `httpx` (sync API, sync `Client`) as the HTTP client for fetching ontologies from URLs in the loader. `respx` is the matching mock-transport library used in tests.

**Reasoning:**
- Pure Python, MIT licensed, actively maintained.
- Supports both sync and async transports behind a single API. v1 is sync; if we later need parallel fetches (resolving imports closures, scanning a directory of URLs) we can move to async without a library swap.
- First-class timeout semantics (`connect`, `read`, `write`, `pool` configurable) and explicit redirect controls (max-redirect counts) instead of `requests`' implicit defaults.
- Better type hints than `requests` — works cleanly under `mypy --strict`.
- `respx` provides a `MockTransport`-based mocking layer that keeps the test suite free of real network calls (see DD-010 — fixtures stay deterministic).

**Alternatives considered:**
- *`requests`:* widely used and battle-tested but has no async path, slower release cadence, weaker timeout granularity, and incomplete type hints. Rejected.
- *`urllib.request` (stdlib):* verbose, awkward error semantics, no built-in connection pooling. Rejected.
- *`aiohttp`:* async-only — forces async on the entire loader path for no v1 benefit. Rejected.

**Implication:** All URL fetching in `sources.py` goes through `httpx.Client`. Tests mock at the transport layer via `respx`; no real network calls in `tests/`.

---

## DD-016: Windows Smart App Control workaround for the console script

**Status:** accepted
**Date:** 2026-05-31

**Decision:** On Windows machines where Smart App Control (SAC) is enabled, invoke the CLI as `uv run python -m owlcompare ...` rather than the `uv run owlcompare ...` console script.

**Problem:** On Windows with SAC enabled, `uv run owlcompare` can fail intermittently with OS error 4551 after `uv` rebuilds the console-script wrapper (`owlcompare.exe`). The freshly-emitted wrapper executable is unsigned and SAC blocks it from running until it is trusted. The error surfaces as a launch failure before any owlcompare code runs.

**Workaround:** `uv run python -m owlcompare` routes through the trusted `python.exe` interpreter (which is signed and SAC-trusted) and imports `owlcompare.__main__`, bypassing the regenerated wrapper. This is purely an invocation change; nothing in the package needs to change.

**Why not fix it in code:** the issue is environmental (Windows + SAC + uv's wrapper regeneration), not a bug in `owlcompare`. CI runs on Linux, where SAC does not exist and the console script works fine; pinning a workaround in shared config would needlessly disadvantage every non-Windows environment.

**Resolution (2026-06-01):** the SAC blocks have been resolved durably by installing Python 3.11 via `winget install Python.Python.3.11` and pinning `uv` to that interpreter (`uv python pin 3.11`). The winget-installed Python is signed by the Python Software Foundation and is therefore trusted by SAC, whereas uv-downloaded interpreters are unsigned and were being intermittently blocked. CI on Linux is unaffected by this change. Continue to invoke the CLI as `uv run python -m owlcompare ...` rather than the `owlcompare.exe` console-script shim, which can still be re-blocked after `uv` rebuilds it.

**Implication:**
- `CLAUDE.md` and `docs/CONVENTIONS.md` document the `python -m owlcompare` form as the recommended Windows invocation so future contributors don't hit the same failure mode.
- The console-script entry point in `pyproject.toml` remains unchanged — it works fine on Linux/macOS and on Windows machines without SAC.
- This is paired with [[DD-012]], which records a related SAC workaround for mypy.

**Alternatives considered:**
- *Disable Smart App Control:* system-wide security downgrade requiring a Windows reset to toggle. Out of proportion to the problem.
- *Remove the console script:* would force every user (not just SAC-affected Windows users) to type the longer form. Rejected.
- *Sign the generated wrapper:* `uv` would have to ship a signed wrapper; out of our control.

---

## DD-017: Ruff version pin to avoid the 0.15.x f-string-lambda format panic

**Status:** accepted
**Date:** 2026-06-02

**Decision:** Pin the `ruff` dev dependency to `>=0.14,<0.16` (in `pyproject.toml` `[dependency-groups].dev`). Separately, project code avoids placing a `lambda` inside an implicitly-concatenated multi-line f-string.

**Problem:** During Component 08, `uv run ruff format` (ruff 0.15.14) panicked with:

```
error: Failed to format src\owlcompare\diff\structural\restrictions.py:
Invalid document: Expected end tag of kind Group but found Indent.
```

The file was valid Python (mypy strict and pytest both accepted it); only the *formatter* crashed, and it named the whole file with no line number. The minimal reproduction is a `lambda` inside an **implicitly-concatenated, multi-line** f-string — the formatter's grouping logic only engages (and trips the IR assertion) once it tries to wrap the f-string:

```python
summary = (
    f"Restriction changed on {ctx.short(before.attached_to)}: "
    f"{ce.describe_change(before, after, lambda i: ctx.short(i))}"
)
```

A single-line f-string with the same lambda formats fine; the bug needs the multi-line concatenation. No matching open issue was found on the `astral-sh/ruff` tracker as of 2026-06 (the "Expected end tag…" message is a generic formatter-IR assertion that also appears in Biome), so the workaround is tagged in code with a `# ruff-bug-0.15.x:` comment to revisit when the pin is lifted.

**Two-part mitigation:**
1. *Code:* expose the IRI shortener as the bound method `_Ctx.short` and compute the f-string's inner phrase on its own line, so no `lambda` ever sits inside an f-string replacement field. This reads at least as cleanly as the inline lambda, so it is not a pure workaround.
2. *Version pin:* cap ruff at `<0.16` so a future `uv sync` cannot silently pull a release whose formatter behaves differently again without a deliberate, reviewed bump. Lower bound `>=0.14` keeps us on the line we have validated (CI and local both run 0.15.x green with the code change in place).

**Implication:**
- `ruff format` and `ruff check` are green on 0.15.x today; the pin is belt-and-suspenders against unreviewed upgrades, mirroring the explicit upper pin rationale in [[DD-014]] (Typer).
- When bumping past 0.16, re-test the f-string-lambda case; if fixed upstream, the `# ruff-bug-0.15.x:` site may revert to an inline lambda and the upper bound can widen.

**Alternatives considered:**
- *Leave ruff unpinned (`>=0.6`) and only change the code:* the code change alone fixes today's failure, but a later ruff release could reformat the whole tree or reintroduce a panic with no guardrail. Rejected — the pin is cheap insurance.
- *Disable the formatter / skip `ruff format` in CI:* loses deterministic formatting, a core convention. Rejected.
- *`# fmt: off` around the call site:* narrower, but leaves the landmine for the next contributor who writes a lambda in an f-string elsewhere. The bound-method refactor plus the documented pin is more durable.
