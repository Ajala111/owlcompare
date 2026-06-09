# Work with large ontologies

owlcompare is designed for the medium-sized, pull-request-review case, but it
holds up well on larger ontologies too. This page will cover the performance
characteristics you can expect, where the time actually goes, and the practical
techniques for keeping diffs fast and reports usable as your ontology grows.

!!! info "This page is being expanded"
    The outline below is in place; the full performance guide is coming.

## What this page will cover

- **Where the time goes** — parsing and canonicalization dominate; the diff
  itself is cheap by comparison.
- **The HTML report benchmark** — engineered to stay responsive at **2000
  changes under 5 MB**, with native scrolling and lazy-rendered detail sections
  rather than an artificial cap on what's shown.
- **Memory and the internal model** — what to expect on large inputs.
- **Selective diffing** — narrowing scope with `--layers` when you don't need the
  full analysis.
- **CI considerations** — caching, timeouts, and running on big files in the
  GitHub Action.
- **When owlcompare isn't the right tool** — the honest edges of the v1 design
  (imports closures, quad stores).
