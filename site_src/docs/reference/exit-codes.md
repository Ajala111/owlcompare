# Exit codes

owlcompare follows the Unix convention that a process's exit code carries
meaning. This is what makes it scriptable and CI-friendly: a build can branch on
exactly *why* owlcompare stopped. Every code below is part of the tool's stable
contract.

## The table

| Code | Name | When |
|------|------|------|
| `0` | Success | The command completed. For `diff`, this also means **no breaking changes**. |
| `1` | General error | An unexpected internal error. Re-run with `-v` for a traceback. |
| `2` | Usage error | Bad arguments, an unknown flag, an unknown `--layers` value, or a file/config path that doesn't exist. |
| `3` | Load error | An ontology couldn't be loaded or parsed (malformed Turtle/RDF, a fetch failure). |
| `4` | Diff / canonicalization error | The diff or the canonicalization step failed — e.g. an input uses an unsupported feature such as named graphs. |
| `5` | Report error | Report generation failed, or `--validate-schema` found the JSON didn't conform to the published schema. |
| `6` | Config error | A `--severity-config` or `--rename-mapping` file is present but invalid (malformed TOML, unknown `schema_version`, a bad entry). |
| `10` | Breaking changes detected | The diff succeeded **and** found at least one breaking change. |
| `130` | Interrupted | The process was cancelled (`Ctrl-C`). |

## The one that matters most: `10`

`owlcompare diff` returns **`10`** when the diff completed successfully but
contained at least one `breaking`-severity change. This is deliberate: it
separates "the tool worked and found a problem" (10) from "the tool itself
failed" (1–6). CI can then fail a pull request on `10` while still treating a
parse error (`3`) or a config typo (`6`) as a different class of failure.

```bash
owlcompare diff old.ttl new.ttl
case $? in
  0)  echo "No breaking changes — safe to merge." ;;
  10) echo "Breaking changes detected — review required." ;;
  *)  echo "owlcompare failed to run (exit $?)." ;;
esac
```

The GitHub Action turns this into a build status for you; see
[CI integration](../guides/ci-integration.md).

## Severity overrides can change the exit code

Because the exit code is derived from severity, a `--severity-config` that demotes
the last remaining breaking change to `info` will flip the exit code from `10` to
`0` — and one that *promotes* a change to `breaking` can flip `0` to `10`. That's
intended: the exit code reflects your project's definition of "breaking," not a
fixed global one. See [Severity overrides](../guides/severity-overrides.md).

## Why `2` for a missing file

A path that doesn't exist on disk is treated as a **usage error** (`2`), not a
load error (`3`). The reasoning: the user mistyped an argument, which is the same
class of mistake as passing an unknown flag. A `3` is reserved for files that
*do* exist but can't be parsed.

## Notes for scripting

- Don't treat any non-zero code as "failed." `10` means success-with-findings.
  Check for `10` explicitly when you care about breaking changes.
- Under `set -e` in bash, an exit `10` will abort the script. Guard the call
  (`owlcompare diff ... || true`) and inspect `$?` yourself, or capture the JSON
  and read `summary.breaking`.
- The JSON output's `summary` block carries the same information
  (`breaking`, `total`) if you'd rather branch on content than on the exit code.
