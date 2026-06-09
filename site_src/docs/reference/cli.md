# CLI reference

The complete reference for the `owlcompare` command — every subcommand, every
flag, with examples. For a gentle introduction, start with
[Your first diff](../getting-started/first-diff.md) instead.

```text
owlcompare [GLOBAL OPTIONS] COMMAND [ARGS]
```

owlcompare has three working commands — [`diff`](#owlcompare-diff),
[`load`](#owlcompare-load), and [`canonicalize`](#owlcompare-canonicalize) —
plus `version`.

!!! tip "Windows + Smart App Control"
    If the `owlcompare` shim is blocked on Windows, invoke through the
    interpreter: `python -m owlcompare ...`. It behaves identically.

## Global options

These apply to the root command and every subcommand.

| Option | Description |
|--------|-------------|
| `--version` | Print the version and exit. |
| `-v`, `--verbose` | Increase log verbosity. Repeatable: `-v` (info), `-vv` (debug). |
| `-q`, `--quiet` | Only log errors. |
| `--help` | Show help for the command and exit. |

Running `owlcompare` with no command prints help and exits `0`.

---

## `owlcompare diff`

Compare two ontologies and report the delta. This is the main command.

```text
owlcompare diff [OPTIONS] ONTOLOGY_A ONTOLOGY_B
```

`ONTOLOGY_A` is the **baseline** (the "before"); `ONTOLOGY_B` is the
**comparison** (the "after"). Each may be a local path or an `http(s)` URL. The
serialization (Turtle, RDF/XML, OWL/XML, JSON-LD, N-Triples) is auto-detected.

owlcompare loads and canonicalizes both inputs, computes the syntactic (Layer 0)
and structural (Layer 1) diff, classifies severity, detects renames, and renders
the result. It **exits `10` if there is any breaking change**, `0` otherwise.

### Examples

```bash
# Text report to the terminal (the default)
owlcompare diff old.ttl new.ttl

# A self-contained HTML report you can share
owlcompare diff old.ttl new.ttl --format html --out report.html

# Machine-readable JSON for a script
owlcompare diff old.ttl new.ttl --format json --out diff.json

# Diff a remote ontology against a local working copy
owlcompare diff https://example.org/ontology/v1.ttl ./working.ttl
```

### Output options

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `text` | Output format: `text`, `json`, `markdown`, `html`, or `junit`. |
| `--out PATH` | *(stdout)* | Write the report to a file instead of standard output. |
| `--show-syntactic` | off | Show all Layer 0 changes in text output, including those a Layer 1 change already explains (hidden by default). |

### Layer selection

| Option | Default | Description |
|--------|---------|-------------|
| `--layers` | `syntactic,structural` | Comma-separated layers to run. Only `syntactic` and `structural` are implemented in v1; naming `inferential` or `impact` is a usage error. |

### Markdown options

These apply only to `--format markdown`.

| Option | Default | Description |
|--------|---------|-------------|
| `--markdown-heading-level` | `2` | Top-level heading depth (1–4; out-of-range falls back to 2). |
| `--no-markdown-emoji` | off | Use plain-text severity tags (`[BREAKING]`, `[OK]`, …) instead of emoji. |

### HTML options

These apply only to `--format html`.

| Option | Default | Description |
|--------|---------|-------------|
| `--html-theme` | `auto` | First-paint theme: `light`, `dark`, or `auto` (respects the viewer's `prefers-color-scheme`). The viewer can still toggle. |
| `--no-embed-json` | off | Don't embed the JSON payload in the HTML (disables the in-report JSON download button). |

### JUnit options

These apply only to `--format junit`.

| Option | Default | Description |
|--------|---------|-------------|
| `--junit-suite-name NAME` | `owlcompare.diff` | Override the `<testsuite>` name. |
| `--junit-include-skipped` | off | Emit info-severity changes as `<skipped>` elements (they pass silently by default). |

### Severity options

| Option | Default | Description |
|--------|---------|-------------|
| `--severity-config PATH` | *(none)* | A TOML file of severity overrides. Overrides can change the exit code — e.g. demoting the last breaking change to `info` yields exit `0`. |
| `--no-severity-refinement` | off | Skip the cross-cutting severity refinement pass (debugging/verification). |
| `--explain-severity` | off | After the diff, print the rule that decided each refined severity. |

See [Severity rules](severity-rules.md) and the
[overrides guide](../guides/severity-overrides.md).

### Rename-detection options

| Option | Default | Description |
|--------|---------|-------------|
| `--rename-confidence` | `high` | Lowest confidence to accept: `certain` (mapping only), `high` (adds label matching), `medium` (adds structural fingerprinting), or `none` (disable detection). |
| `--rename-mapping PATH` | *(none)* | A TOML file of user-asserted renames (treated as `certain` confidence). |
| `--export-rename-mapping PATH` | *(none)* | Write the detected renames to a TOML file loadable by `--rename-mapping`. Additive — does not change stdout. Overwrites any existing file. |

See the [rename detection guide](../guides/rename-detection.md).

### Schema validation

| Option | Default | Description |
|--------|---------|-------------|
| `--validate-schema` | off | Validate the JSON output against the bundled schema before emitting. On failure, raise an error (exit `5`) rather than ship non-conforming JSON. No effect unless `--format json`. |

### Diff examples with options

```bash
# Markdown for a PR comment, level-3 headings, no emoji
owlcompare diff a.ttl b.ttl --format markdown --markdown-heading-level 3 --no-markdown-emoji

# Force a dark HTML report and skip the embedded JSON
owlcompare diff a.ttl b.ttl --format html --html-theme dark --no-embed-json --out report.html

# Apply project severity conventions and explain every refinement
owlcompare diff a.ttl b.ttl --severity-config .owlcompare-severity.toml --explain-severity

# Detect renames more aggressively, and save the mapping for next time
owlcompare diff a.ttl b.ttl --rename-confidence medium --export-rename-mapping renames.toml
```

---

## `owlcompare load`

Load a single ontology and print a summary — entity counts, the ontology IRI, and
prefix bindings. A quick way to confirm a file parses before you diff it.

```text
owlcompare load [OPTIONS] SOURCE
```

`SOURCE` is a file path or URL.

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | *(auto)* | Format hint: `turtle`, `xml`, `n3`, `nt`, `json-ld`, `trig`. Auto-detected if omitted. |
| `--strict` | off | Treat parse warnings as errors. |
| `--timeout SECONDS` | `30` | Network timeout for URL sources. |
| `--base-iri IRI` | *(none)* | Base IRI for resolving relative references. |

```bash
owlcompare load ontology/era.ttl
owlcompare load https://example.org/ontology.owl --format xml --timeout 60
```

---

## `owlcompare canonicalize`

Emit the normalized (canonical) form of an ontology. owlcompare canonicalizes
internally before diffing; this command exposes that step so two semantically
equal inputs produce byte-identical output, which is handy for debugging "why did
these diff?" puzzles.

```text
owlcompare canonicalize [OPTIONS] SOURCE
```

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | *(auto)* | Input format hint (passed to the loader). |
| `--out PATH` | *(stdout)* | Write the normalized form to a file. |
| `--output-format` | `turtle` | Serialization for the output: `turtle` or `nt`. |
| `--no-blank-nodes` | off | Skip blank-node canonicalization. |
| `--no-reify-restrictions` | off | Skip restriction reification. |
| `--no-collapse-lists` | off | Skip RDF-list collapsing. |
| `--no-sort` | off | Skip triple sorting. |

```bash
owlcompare canonicalize messy.ttl --out clean.ttl
owlcompare canonicalize a.ttl --output-format nt | sha256sum
```

The `--no-*` flags disable individual normalization steps; by default all four
run. See [Canonicalization](../architecture/canonicalization.md) for what each one
does and why.

---

## `owlcompare version`

Print the version and exit. Equivalent to `owlcompare --version`.

```bash
owlcompare version
# owlcompare 0.0.1
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success — no breaking changes. |
| `2` | Usage error (bad arguments, missing file). |
| `3` | Load error (couldn't parse the ontology). |
| `4` | Diff / canonicalization error. |
| `5` | Report-generation or schema-validation error. |
| `6` | Invalid config file. |
| `10` | Success — but breaking changes were detected. |

The full table, with the rationale for each code, is in
[Exit codes](exit-codes.md).
