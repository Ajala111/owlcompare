# Conventions

## Python style

- **Formatter & linter:** `ruff` with the configuration in `pyproject.toml`. Run `uv run ruff format .` and `uv run ruff check .` before any commit. Lint rule selection (`select`/`ignore`) lives under `[tool.ruff.lint]`, not top-level `[tool.ruff]` — the top-level form is deprecated in modern ruff and emits warnings.
- **Type hints:** required on every public function and method. Optional but encouraged on internals.
- **Type checking:** `mypy --strict` for `src/owlcompare/` public modules. Permissive for internal helpers.
- **Imports:** sorted by ruff's isort rules. Standard library, then third-party, then local.
- **Docstrings:** required on every public function/class. Use Google style. One-liners are fine for obvious methods.
- **Line length:** 100 characters.

### Windows-specific notes

- If `uv run mypy` fails to start with a DLL load error (`An application control policy has blocked this file` / Smart App Control), it's blocking mypy's mypyc-compiled binary, not a code problem. See **DD-012** in `docs/DESIGN_DECISIONS.md` for the local-only, git-ignored `uv.toml` workaround that forces a pure-Python mypy build.

## Naming

- Modules: `lower_snake_case.py`
- Classes: `PascalCase`
- Functions, methods, variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `_leading_underscore`
- Test files: `test_<module>.py` mirroring source layout

## Project-specific naming

- The CLI command is `owlcompare` (lowercase, no hyphen).
- The package name is `owlcompare`.
- Internal data types use the `Onto` prefix sparingly. Prefer `OntologySnapshot` over `Ontology` to avoid clashing with `rdflib`/`owlready2`.
- "Change" is the canonical term for a diff record. Not "diff entry," "delta," or "modification."
- "Snapshot" is the canonical term for a loaded ontology. Not "version," "instance," or "doc."

## Type-hinting style

- Use `list[X]`, `dict[K, V]`, `tuple[A, B]`, never `List`, `Dict`, `Tuple` from typing.
- Use `X | Y` and `X | None`, never `Union[X, Y]` or `Optional[X]`.
- Use `Literal["a", "b"]` for enums of strings; prefer a real `Enum` if the set is closed and used widely.
- Public dataclasses are `@dataclass(frozen=True, slots=True)` by default.

## Error handling

- **Define typed exception classes** in `src/owlcompare/exceptions.py` (`OwlCompareError` base, then `LoadError`, `DiffError`, `ReportError`).
- **Library code raises**; CLI code catches and translates to exit codes + user messages.
- **Never** use bare `except:` or `except Exception:` without re-raising or logging context.
- **Never** swallow errors silently. If something is expected to fail, document it.

## Logging

- Use the standard `logging` module. Library code uses `logger = logging.getLogger(__name__)`.
- CLI configures logging at startup based on `-v` / `-vv` flags.
- No `print()` in library code. Ever.

## Testing

- **Framework:** `pytest`.
- **Coverage target:** 85% for `src/owlcompare/` excluding `cli.py` and `report/html_report.py`.
- **Fixtures:** small (< 100 axioms), hand-crafted Turtle in `tests/fixtures/`. See DD-010.
- **Test naming:** `test_<thing>_<condition>_<expected>`. e.g., `test_loader_invalid_turtle_raises_load_error`.
- **One assertion concept per test.** Multiple `assert` lines are fine if they test the same logical concept.
- **Parametrize** when testing the same logic over multiple inputs.

## Git & commits

- **Branch naming:** `phase-N/component-NN-short-description` (e.g., `phase-2/component-06-structural-entities`).
- **Commit messages:** Conventional Commits format:
  - `feat:` new functionality
  - `fix:` bug fix
  - `docs:` documentation
  - `refactor:` no behavior change
  - `test:` tests only
  - `chore:` tooling, deps, CI
- **One component per PR.** Don't bundle.
- **PR description must reference the spec file** it implements.

## Documentation

- Public functions have docstrings. Private helpers may.
- Architectural decisions go in `docs/DESIGN_DECISIONS.md`, not in code comments.
- Cross-component contracts go in `docs/ARCHITECTURE.md`, not in code comments.
- Code comments explain *why*, never *what*.

## Dependencies

- **Add a dependency only after a DD entry approves it.** Each `uv add` should be paired with an update to `DESIGN_DECISIONS.md` if the dependency is new.
- **No abandonware.** Last release within 12 months; active issue triage.
- **No GPL dependencies.** MIT/BSD/Apache only, to keep our license clean.

## File layout

When adding a new module:

1. Source file goes in the appropriate package under `src/owlcompare/`.
2. Test file mirrors the source path under `tests/unit/`.
3. If it introduces a new public API surface, add a section to `docs/ARCHITECTURE.md`.
4. If it implements a spec, update the corresponding `specs/NN-*.md` with the resolved decisions.

## When you're stuck

1. Re-read the relevant spec in `specs/`.
2. Check `docs/DESIGN_DECISIONS.md` for prior choices.
3. Check existing components for patterns to mirror.
4. Ask the user. Don't guess.
