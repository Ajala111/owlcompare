# Installation

owlcompare is a pure-Python command-line tool and library. There is no JVM, no
native build step, and no configuration file to write. This page covers every
way to install it, how to verify the install, and how to fix the handful of
problems people hit.

## Requirements

- **Python 3.11 or newer.** owlcompare uses features (structural pattern
  matching, `tomllib`, `StrEnum`) that landed in 3.11. 3.12 is recommended.
- **An operating system** — Linux, macOS, or Windows. Everything is tested on all
  three.

Check your Python version first:

```bash
python --version
# Python 3.11.x  (or higher)
```

If that prints 3.10 or lower, install a newer Python before continuing. On
Windows, `winget install Python.Python.3.12` is the smoothest path.

## Install the CLI

=== "pip"

    ```bash
    pip install owlcompare
    ```

=== "pipx (isolated)"

    Keeps owlcompare and its dependencies in their own environment, off your
    global site-packages:

    ```bash
    pipx install owlcompare
    ```

=== "uv"

    If you use [uv](https://docs.astral.sh/uv/) — owlcompare's own package
    manager:

    ```bash
    # add it to a project
    uv add owlcompare

    # …or install it as a global tool
    uv tool install owlcompare
    ```

All four give you the same `owlcompare` command on your `PATH`.

## Verify the install

```bash
owlcompare --version
# owlcompare 0.1.0

owlcompare --help
```

The `--help` output lists the three subcommands you'll use:

- `owlcompare diff A B` — the main event: diff two ontologies.
- `owlcompare load A` — load one ontology and print a summary (a quick sanity check).
- `owlcompare canonicalize A` — emit the normalized form of one ontology.

If `owlcompare --version` prints a version string, you're done. Head to
[Your first diff](first-diff.md).

## Use it as a GitHub Action

You don't have to install owlcompare locally to use it in CI. The GitHub Action
wraps the CLI so adding ontology diffing to a repository is a three-line step:

```yaml
- uses: actions/checkout@v4
- uses: Ajala111/owlcompare@v1
  with:
    ontology-path: ontology/my-ontology.ttl
```

See the [CI integration guide](../guides/ci-integration.md) for the full setup,
including PR comments and breaking-change gating.

## Use it as a library

owlcompare is importable. The public surface is small and typed:

```python
from owlcompare.loader import load
from owlcompare.model import LoadOptions
from owlcompare.diff import orchestrator
from owlcompare.diff._common import DiffOptions

a = load("old.ttl", LoadOptions())
b = load("new.ttl", LoadOptions())
result = orchestrator.run(a, b, DiffOptions())

for change in result.changes:
    print(change.severity, change.kind)
```

The library API is not yet frozen the way the [CLI](../reference/cli.md) and the
[JSON output](../reference/json-schema.md) are — expect it to firm up post-v1.

## Troubleshooting

**`owlcompare: command not found` after install.**
The install succeeded but the script directory isn't on your `PATH`. With `pip
install --user`, that's usually `~/.local/bin` (Linux/macOS) or the Python
`Scripts` directory (Windows). Either add it to `PATH`, or run the tool through
the interpreter, which always works:

```bash
python -m owlcompare --help
```

**`SyntaxError` or `unsupported operand` on startup.**
You're running owlcompare under Python 3.10 or older. Confirm with `python
--version` and install 3.11+.

**Windows: the `owlcompare.exe` shim is blocked / errors on launch.**
On Windows with Smart App Control enabled, the generated console-script wrapper
can be intermittently blocked. Invoke through the trusted interpreter instead:

```powershell
python -m owlcompare diff old.ttl new.ttl
```

This is purely an invocation change — everything else works identically.

**A dependency fails to build.**
owlcompare's dependencies (`rdflib`, `httpx`, `rich`, `typer`) all ship wheels
for supported platforms, so this is rare. If it happens, upgrade `pip`
(`python -m pip install --upgrade pip`) and retry; an old resolver picking a
source-only release is the usual cause.

## Next steps

- [Your first diff](first-diff.md) — a ten-minute hands-on walkthrough.
- [Understanding the output](understanding-output.md) — what the layers and
  severities mean.
- [CI integration](../guides/ci-integration.md) — diff on every pull request.
