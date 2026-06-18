# Flagship: FIBO Business Entities, 2023Q3 → 2024Q3

owlcompare diffing two published quarterly releases of the
[Financial Industry Business Ontology (FIBO)](https://spec.edmcouncil.org/fibo/),
a production multi-stakeholder ontology for financial-industry vocabulary,
published by the Enterprise Data Management Council (EDM Council) and
standardized by the Object Management Group (OMG).

**Source:** [FIBO at EDM Council](https://github.com/edmcouncil/fibo) ·
**License:** MIT ·
**Module:** FIBO-BE (Business Entities) · **File:** `OwnershipAndControl/Executives.rdf` ·
**Versions:** 2023Q3 (released September 2023) → 2024Q3 (released September 2024) ·
**Run on:** 2026-06-12 · **owlcompare version:** 0.1.0

Why this comparison: FIBO is a real production ontology under continuous
multi-stakeholder development. [Academic research](https://arxiv.org/abs/2108.05401)
has documented that roughly one-third of FIBO entities change per quarter. This
flagship shows what owlcompare makes of a year of evolution in one FIBO file —
and the answer is a clean, comprehensible story rather than a wall of diff noise.

!!! tip "The headline isn't *how many* changes — it's *what they mean*"
    owlcompare distills **214 raw triple changes** into **41 structured events**,
    and **34 of those 41** turn out to be a *single coordinated refactor*: FIBO-BE
    adopting the OMG Commons Ontology Library in place of its own Foundations
    Parties vocabulary (`fibo-fnd-pty-pty:` → `cmns-pts:`). owlcompare describes a
    multi-stakeholder migration as a handful of human-readable changes — and EDM
    Council's own release notes confirm exactly that migration (see
    [cross-validation](#cross-validating-with-edm-councils-release-notes) below).

## At a glance

| Metric | Value |
|--------|-------|
| Total Layer 1 changes | 41 |
| Breaking changes | 28 |
| Additive changes (new classes/properties) | 0 |
| Non-breaking changes (restriction relaxations) | 12 |
| Info changes (labels, comments, metadata) | 1 |
| Renames detected | 0 |
| Anonymous structure changes | 0 |
| Datatype facet changes | 0 |
| Unexplained Layer 0 | 10 |

The **Unexplained Layer 0** line is owlcompare's headline correctness claim. Here
all 10 are meaningful ontology-level metadata — `owl:imports` reorganization,
`owl:versionIRI` bump, and `cmns-av:copyright` year update — not decoder noise.
There is *nothing* in this diff owlcompare failed to account for except changes
that have no higher-level structure to fold into. (More in
[complete coverage of the diff](#4-complete-coverage-of-the-diff).)

This window contains **zero renames and zero anonymous-structure changes** — no
`unionOf` shifts, datatype facets, or `dcterms:isReplacedBy` assertions. That is
characteristic of this editorial period (a vocabulary migration, not a
restructuring), not a gap in owlcompare; the rename detector and Component 12.5's
anonymous-structure decoder simply had nothing to fire on here.

## Source files

The exact FIBO files used in this diff are committed to the owlcompare repo,
ready for anyone to fork or rerun:

- **2023Q3 baseline:** [`examples/fibo_demo/v1/`](https://github.com/Ajala111/owlcompare/tree/main/examples/fibo_demo/v1) (FIBO-BE module, git tag `master_2023Q3`)
- **2024Q3 target:** [`examples/fibo_demo/v2/`](https://github.com/Ajala111/owlcompare/tree/main/examples/fibo_demo/v2) (FIBO-BE module, git tag `master_2024Q3`)
- **License:** MIT, preserved at [`LICENSE-FIBO`](https://github.com/Ajala111/owlcompare/blob/main/examples/fibo_demo/LICENSE-FIBO)

The specific file diffed in this showcase is `OwnershipAndControl/Executives.rdf`.
The [Reproduce this diff](#reproduce-this-diff) section below has the one command
that turns these files back into every output format on this page.

## Cross-validating with EDM Council's release notes

This is the showcase's unique value-add: owlcompare's findings cross-referenced
against EDM Council's *own* published release notes for the intervening quarters.
Every quote below is verbatim and maps to a specific change owlcompare detected.

### From the EDM Council 2023Q4 release notes — the migration begins

> "Changes made to Business Entities in Q4 included minor spelling corrections and elimination of duplicate content with respect to the new Commons ontologies as well as elimination of deprecated elements from early 2023."
>
> — [EDM Council, FIBO 2023Q4 Release Notes](https://github.com/edmcouncil/fibo/releases/tag/master_2023Q4)

The same notes forecast the specific work owlcompare later detects:
*"We will continue this work in Q1 2024 for roles and parties."* That "roles and
parties" alignment is precisely the migration that lands inside this diff.

### From the EDM Council 2024Q1 release notes — the migration lands in BE

> "Revisions to Business Entities in Q1 were primarily with respect to support for migration of certain FIBO FND ontologies to the OMG's Commons Ontology Library."
>
> — [EDM Council, FIBO 2024Q1 Release Notes](https://github.com/edmcouncil/fibo/releases/tag/master_2024Q1)

owlcompare reports the corresponding changes — **34 of the 41** total: 10 entities
re-parented from `fibo-fnd-pty-pty:` to `cmns-pts:`, and 24 restrictions migrated
from `fibo-fnd-pty-rl:isPlayedBy` to `cmns-rlcmp:isPlayedBy`:

> 🔴 **Class reparented:** `fibo-be-oac-exec:AuthorizingParty`: fibo-fnd-pty-pty:Actor → cmns-pts:Actor (lateral)
> 🔴 **Restriction added on** `fibo-be-oac-exec:Executive`: `exactly 1 fibo-be-le-lp:LegallyCompetentNaturalPerson cmns-rlcmp:isPlayedBy`

### From the EDM Council 2024Q1 release notes — which vocabularies moved

> "The primary revisions to Foundations in Q1 reflect migration of several ontologies to the OMG's Commons Ontology Library. These include the entire Roles ontology, much of the Parties ontology…"
>
> — [EDM Council, FIBO 2024Q1 Release Notes](https://github.com/edmcouncil/fibo/releases/tag/master_2024Q1)

This explains *why* the namespaces changed: the **Parties** ontology moving to
Commons is why `fibo-fnd-pty-pty:Actor`/`PartyInRole` became `cmns-pts:Actor`/
`PartyRole` (the reparents and the `elects`/`nominates` domain/range shifts), and
the **Roles** ontology moving is why `fibo-fnd-pty-rl:isPlayedBy` became
`cmns-rlcmp:isPlayedBy` (the 24 restriction changes).

!!! note "FIBO validates itself, inside the diff"
    owlcompare also surfaces a `skos:changeNote` that FIBO's curators embedded
    directly in `Executives.rdf` for this very release: *"…modified to replace
    content that is now available in the OMG Commons Ontology Library (Commons)
    v1.1 (FND-380)."* The diff is self-validating: owlcompare detected the
    migration mechanically, and FIBO's own change note — ticket **FND-380** —
    confirms it.

## The full interactive report

[**Open the interactive HTML report ↗**](assets/fibo-diff-report.html){target="_blank"}

![Screenshot of the FIBO diff HTML report](assets/fibo-diff-report-preview.png)

Self-contained HTML (~370 KB); opens offline; no dependencies. Also available as
[Markdown](https://github.com/Ajala111/owlcompare/blob/main/site_src/docs/showcase/assets/fibo-diff-report.md)
(rendered on GitHub),
[JSON](assets/fibo-diff-report.json), or
[JUnit XML](assets/fibo-diff-report.xml).

## How owlcompare describes the changes

Four patterns from this diff, each shown as owlcompare's literal output followed
by what it means.

### 1. Lateral reparenting — the Commons migration, consolidated

owlcompare detects FIBO's Commons-adoption migration as **10 lateral reparents,
consolidated from 20 raw triple changes** (each reparent is an `rdfs:subClassOf`/
`rdfs:subPropertyOf` removed *and* added at the Layer 0 level):

> 🔴 **Class reparented:** `fibo-be-oac-exec:AuthorizingParty`: fibo-fnd-pty-pty:Actor → cmns-pts:Actor (lateral)
> 🔴 Property `fibo-be-oac-exec:authorizes` reparented: fibo-fnd-pty-pty:actsOn → cmns-pts:actsOn (lateral)

Rather than show you 20 disconnected add/remove triples, owlcompare folds each
into one statement and tags the direction **`(lateral)`** — it recognizes the
new parent is a same-named concept in a *different namespace*, neither a
generalization nor a specialization. Seven properties (`authorizes`,
`hasAuthorizingParty`, `isAuthorizedBy`, …) and three classes (`Authorization`,
`AuthorizingParty`, `ResponsibleParty`) all moved this way.

### 2. Severity classification at scale

The 24 restriction changes split cleanly into **12 breaking additions and 12
non-breaking removals**. Here is one entity, `fibo-be-oac-exec:Executive`, on both
sides of the migration:

> 🔴 **Restriction added on** `fibo-be-oac-exec:Executive`: `exactly 1 fibo-be-le-lp:LegallyCompetentNaturalPerson cmns-rlcmp:isPlayedBy`
> 🟡 **Restriction removed from** `fibo-be-oac-exec:Executive`: `exactly 1 fibo-be-le-lp:LegallyCompetentNaturalPerson fibo-fnd-rel-rel:hasIdentity`

owlcompare's severity rule is asymmetric and conservative: *adding* a constraint
(red) can invalidate data that was previously valid → **breaking**; *removing* one
(yellow) only relaxes the model → **non-breaking**. That asymmetry is what lets a
reviewer trust the breaking count as a worst-case signal.

!!! info "A v2 opportunity, stated honestly"
    These 24 changes are really one migration of the `isPlayedBy` predicate. A
    future owlcompare version could collapse such pairs into a single
    `restriction_predicate_migrated` kind. For v1 they are correctly reported as
    independent breaking/non-breaking changes — the axioms genuinely differ at
    `owl:onProperty`, so owlcompare does not pretend to a semantic equivalence it
    hasn't proven.

### 3. Signature evolution

The migration also shifts property *signatures* — domains and ranges — and
owlcompare reports each as its own structured change:

> 🔴 **Domain changed on** `fibo-be-oac-exec:elects`: fibo-fnd-pty-pty:PartyInRole → cmns-pts:PartyRole
> 🔴 **Range changed on** `fibo-be-oac-exec:elects`: fibo-fnd-pty-pty:PartyInRole → cmns-pts:PartyRole

`elects` had *both* its domain and range retargeted to the Commons `PartyRole`
concept; `nominates` likewise, and `hasResponsibility`'s domain moved to
`cmns-pts:Party`. These are exactly the kind of signature shifts that quietly
break downstream SPARQL and SHACL if a reviewer misses them.

### 4. Complete coverage of the diff

owlcompare accounts for every change in this diff. Of the 214 raw Layer 0
triple changes, all but 10 fold into one of the 41 structured Layer 1 events
shown above. The remaining 10 are ontology-level metadata that have no
higher-level structure to fold into:

> 🟡 Removed: `…Executives/ owl:imports <https://spec.edmcouncil.org/fibo/ontology/FND/Par…`
> 🟡 Added: `…Executives/ owl:imports <https://www.omg.org/spec/Commons/PartiesAndSituat…`

The import reorganization toward Commons, the `owl:versionIRI` bump from the
2023 to the 2024 IRI, and the `cmns-av:copyright` year update — meaningful
Layer 0 metadata that doesn't have a Layer 1 equivalent.

One change in the diff uses owlcompare's `complex_class_expression_changed`
kind:

> 🔴 Complex class expression on `fibo-be-oac-exec:BoardCapacity` changed (deep)

This appears once across the entire 41-change diff and signals that a
deeply-nested anonymous class expression on `BoardCapacity` changed in a way
that the v1 structured decoder reports with its outer structure rather than a
fully-unfolded breakdown.

## Reproduce this diff

The exact FIBO source files and reproduction command are committed to the
owlcompare repo:

```bash
# Clone owlcompare
git clone https://github.com/Ajala111/owlcompare.git
cd owlcompare

# Install owlcompare
uv sync                     # if you have uv
# OR: pip install -e .       # if you prefer pip

# Run the flagship diff
uv run python -m owlcompare diff \
  examples/fibo_demo/v1/OwnershipAndControl/Executives.rdf \
  examples/fibo_demo/v2/OwnershipAndControl/Executives.rdf \
  --format html --out flagship-report.html

# Open flagship-report.html in your browser
```

Or regenerate every output format used on this page:

```bash
python scripts/generate_flagship.py
```

The FIBO source files in this repo are unmodified copies of EDM Council's
publicly-released versions (git tags `master_2023Q3` and `master_2024Q3`; MIT
license — see [`examples/fibo_demo/LICENSE-FIBO`](https://github.com/Ajala111/owlcompare/blob/main/examples/fibo_demo/LICENSE-FIBO)).
The reproduction output may differ slightly from this page if you run a newer
owlcompare version with updated classifiers.

## Attribution

The Financial Industry Business Ontology is published by the
[Enterprise Data Management Council (EDM Council)](https://edmcouncil.org/) and
standardized by the [Object Management Group (OMG)](https://www.omg.org/). FIBO is
licensed under the [MIT License](https://github.com/edmcouncil/fibo/blob/master/LICENSE)
(Copyright © 2020 Enterprise Data Management Council); a copy is preserved in this
repo at `examples/fibo_demo/LICENSE-FIBO`.

This showcase demonstrates owlcompare's diff capabilities. owlcompare is not
affiliated with EDM Council, OMG, or any FIBO contributor. We use the
publicly-available FIBO files as a representative test case for the kinds of
multi-stakeholder ontology evolution owlcompare is designed for.

owlcompare is authored by [Olatunji Felix Ajala (phelz)](https://github.com/Ajala111),
who chose FIBO as the flagship subject for its permissive license, its rapid
quarterly evolution, and its broad recognizability to the ontology-engineering
community.

---

← [Back to owlcompare docs](../index.md)
