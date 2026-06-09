# Detect renames

When an entity is renamed, a triple-level diff reports it as an unrelated removal
plus addition — multiplied by every axiom that referenced the old IRI. owlcompare
recognizes the rename and reports it as a single event, with a confidence level
so you know how sure it is. This page will be the complete guide to controlling
that behavior; the [Understanding the output](../getting-started/understanding-output.md)
page introduces the idea.

!!! info "This page is being expanded"
    The outline below is in place; the full guide with examples is coming.

## What this page will cover

- **The three confidence tiers**, with an example of each:
    - **certain** — asserted by you in a mapping file.
    - **high** — matched by a shared `rdfs:label` (the default floor).
    - **medium** — matched by structural fingerprint when labels don't align.
- **When to lower the floor** with `--rename-confidence medium`, and the
  trade-off (more renames detected, more chance of a false pairing).
- **The TOML rename-mapping file** — asserting renames owlcompare can't infer,
  via `--rename-mapping`.
- **The export workflow** — `--export-rename-mapping` to capture detected renames
  and reuse or hand-edit them.
- **Cascade consolidation** — how a rename absorbs the reference updates it
  causes, and how genuinely-new structure on a renamed entity still surfaces.
- **Disabling detection** entirely with `--rename-confidence none`.
