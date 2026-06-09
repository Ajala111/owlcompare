# Configure severity overrides

owlcompare ships with sensible defaults for what counts as `breaking`,
`non_breaking`, `additive`, or `info` — but "breaking" is ultimately a
project-specific judgment. A severity-override config lets you encode your
project's conventions in a small TOML file you commit alongside the ontology, so
everyone (and CI) classifies changes the same way. This page will be the
complete how-to; for the built-in rules and the file format, see
[Severity rules](../reference/severity-rules.md).

!!! info "This page is being expanded"
    The outline below anchors the scope; full worked scenarios are coming.

## What this page will cover

- **The TOML override format** — `kind_pattern`, `subject_pattern`, `layer`, and
  the target `severity`, with glob matching.
- **Common scenarios**, each as a copy-pasteable snippet:
    - "Ignore all annotation changes."
    - "Treat any class reparenting as breaking."
    - "Downgrade restriction changes on a specific entity being deprecated."
- **How overrides interact with the built-in rules** (user overrides win) and the
  refinement order.
- **How overrides affect the exit code** — demoting the last breaking change to
  `info` flips the exit from `10` to `0`.
- **Wiring a config into CI** via the Action's `severity-config` input.
