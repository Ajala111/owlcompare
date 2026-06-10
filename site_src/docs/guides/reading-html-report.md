# Read the HTML report

The HTML report is owlcompare's flagship deliverable: a single self-contained file
you can open offline, attach to an email, or commit to a pull request. It presents
the same diff as the terminal view, but organized for unhurried review — breaking
changes first, everything else grouped and collapsible. This page will be a
guided tour of every part of it. Generate one with `owlcompare diff a.ttl b.ttl
--format html --out report.html`, or open the
[live example](../examples/sample.html).

!!! info "This page is being expanded"
    The outline below anchors the scope; the full annotated tour is coming.

## What this page will cover

- **The header and status badge** — the at-a-glance "is this safe to merge?"
  signal.
- **The sticky summary strip** — counts by severity, always visible as you scroll.
- **The sections** — Renames → Breaking → Other → Unexplained Layer 0, and why
  they're ordered that way.
- **Anatomy of a change card** — the severity stripe, the summary line, the
  "why breaking" refinement note, and the collapsible details.
- **The toolbar** — section collapse, the light/dark/auto theme cycle, the
  copy-link button, and the JSON download.
- **Working offline** — why there are no external resources, and what that means
  for sharing.
- **Performance** — how the report stays responsive at thousands of changes.
