# JSON schema reference

`owlcompare diff --format json` emits a **versioned, machine-readable contract**,
formalized as a [JSON Schema 2020-12](https://json-schema.org/) document. If you
build automation on top of owlcompare — a dashboard, a custom gate, a language
server — this is the surface to target. The schema is bundled with the package
and published in the repository.

!!! info "This page is being expanded"
    The full field-by-field reference is coming. The pointers below are enough to
    integrate against the contract today.

## The bundled schema

The canonical schema file lives at
[`docs/schema/diff-result.schema.json`](https://github.com/Ajala111/owlcompare/blob/main/docs/schema/diff-result.schema.json)
and ships inside the installed package. External consumers can pin the raw URL:

```
https://raw.githubusercontent.com/Ajala111/owlcompare/main/docs/schema/diff-result.schema.json
```

Validate your own captured output against it during development with
`owlcompare diff ... --format json --validate-schema`.

## What this page will cover

- **The top-level shape** — `schema_version`, `summary`, `changes`, and
  `metadata`.
- **The `Change` object** — `kind`, `severity`, `details`, `subsumes`, and the
  per-kind `details` variants.
- **The `summary` block** — the counts CI reads (`total`, `breaking`, …).
- **The `metadata` block** — the subsumption registry and severity-refinement
  audit trail.
- **The versioning policy** — what's forward-compatible (new optional fields, new
  `kind` values) versus what bumps the major `schema_version`.
