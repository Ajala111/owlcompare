# Your first diff

This is a hands-on, ten-minute walkthrough. You'll create two small ontology
files, diff them, read the output line by line, and then render the same diff as
an HTML report. By the end you'll understand the shape of everything owlcompare
produces.

You only need owlcompare installed — see [Installation](installation.md) if you
haven't yet.

## 1. Create two versions of an ontology

We'll use a tiny fragment of a railway vocabulary (the kind of domain owlcompare
was built for). Save this as **`era_v1.ttl`**:

```turtle
@prefix era:  <http://data.europa.eu/949/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://data.europa.eu/949/ontology> a owl:Ontology ;
    owl:versionInfo "1.0.0" ;
    rdfs:label "ERA Evolution Fragment"@en .

era:Track a owl:Class ;
    rdfs:label "Track"@en ;
    rdfs:label "Voie"@fr ;
    rdfs:subClassOf [
        a owl:Restriction ;
        owl:onProperty era:hasMaxSpeed ;
        owl:maxCardinality "1"^^xsd:nonNegativeInteger
    ] .

era:Tunnel a owl:Class ;
    rdfs:subClassOf era:Track ;
    rdfs:label "Tunnel"@en .

era:Signal a owl:Class ;
    rdfs:label "Signal"@en .

era:hasMaxSpeed a owl:DatatypeProperty ;
    rdfs:domain era:Track ;
    rdfs:range xsd:integer ;
    rdfs:label "has maximum speed"@en .

era:locatedOn a owl:ObjectProperty ;
    rdfs:domain era:Signal ;
    rdfs:range era:Track ;
    rdfs:label "located on"@en .
```

Now save a second version as **`era_v2.ttl`** with four realistic edits — a new
class, a removed property, a loosened cardinality, and a corrected French label —
plus a version bump:

```turtle
@prefix era:  <http://data.europa.eu/949/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://data.europa.eu/949/ontology> a owl:Ontology ;
    owl:versionInfo "2.0.0" ;
    rdfs:label "ERA Evolution Fragment"@en .

era:Track a owl:Class ;
    rdfs:label "Track"@en ;
    rdfs:label "Voie ferrée"@fr ;
    rdfs:subClassOf [
        a owl:Restriction ;
        owl:onProperty era:hasMaxSpeed ;
        owl:maxCardinality "2"^^xsd:nonNegativeInteger
    ] .

era:Tunnel a owl:Class ;
    rdfs:subClassOf era:Track ;
    rdfs:label "Tunnel"@en .

era:Signal a owl:Class ;
    rdfs:label "Signal"@en .

era:Platform a owl:Class ;
    rdfs:label "Platform"@en .

era:hasMaxSpeed a owl:DatatypeProperty ;
    rdfs:domain era:Track ;
    rdfs:range xsd:integer ;
    rdfs:label "has maximum speed"@en .
```

## 2. Run the diff

```bash
owlcompare diff era_v1.ttl era_v2.ttl
```

You'll see:

```text
owlcompare diff
A: era_v1.ttl
B: era_v2.ttl

8 triples added, 10 triples removed (1 breaking)

Layer 1 — Structural (5 changes)
  [additive]     Class added: era:Platform "Platform"@en
  [breaking]     Object property removed: era:locatedOn "located on"@en
  [non_breaking] Restriction changed on era:Track: era:hasMaxSpeed max 1 → max 2
  [info]         Label changed on era:Track (fr): 'Voie' → 'Voie ferrée'
  [info]         Ontology metadata: owl:versionInfo '1.0.0' → '2.0.0'

Layer 0 — Syntactic (0 unexplained)        [use --show-syntactic for all]
```

## 3. Read it line by line

**`8 triples added, 10 triples removed (1 breaking)`** — the raw, triple-level
count. Eighteen triples moved. If that's all your diff tool told you, you'd have
to read all eighteen to find the one that matters. owlcompare keeps going.

**`Layer 1 — Structural (5 changes)`** — those eighteen triples roll up into five
*semantic* events, each tagged with a severity:

- `[additive]`{ data-severity="additive" } **Class added: era:Platform** — a pure
  addition. Nothing that used the old ontology can break because a class appeared.
- `[breaking]`{ data-severity="breaking" } **Object property removed: era:locatedOn**
  — this is the one that matters. Any query, shape, or code that referenced
  `era:locatedOn` will now break. owlcompare flags it and **exits with code 10**.
- `[non_breaking]`{ data-severity="non-breaking" } **Restriction changed … max 1 → max 2**
  — the cardinality was *loosened*. Existing data that satisfied "at most 1" still
  satisfies "at most 2", so valid usage doesn't break.
- `[info]`{ data-severity="info" } **Label changed (fr)** — an editorial change to a
  French label. Semantically inert.
- `[info]`{ data-severity="info" } **Ontology metadata: versionInfo** — the version
  string bump. Noted, not significant.

**`Layer 0 — Syntactic (0 unexplained)`** — every raw triple change was *explained*
by one of the Layer 1 events above, so there's no leftover noise to show. Pass
`--show-syntactic` if you ever want to see the raw triples anyway.

## 4. Render an HTML report

The terminal view is great for a quick look. For review, generate the
self-contained HTML report:

```bash
owlcompare diff era_v1.ttl era_v2.ttl --format html --out report.html
```

Open `report.html` in any browser. It's a single file — no server, no external
assets — so you can email it, commit it to a PR, or archive it. The breaking
change is front and center; everything else is grouped and collapsible. See
[Reading the HTML report](../guides/reading-html-report.md) for a tour.

## 5. Check the exit code

owlcompare follows the Unix convention of meaning-bearing exit codes. Because
this diff contained a breaking change, the process exited **10**:

```bash
owlcompare diff era_v1.ttl era_v2.ttl > /dev/null
echo $?
# 10
```

That's the hook CI uses to fail a build. A diff with no breaking changes exits
`0`. The full table is in [Exit codes](../reference/exit-codes.md).

## What just happened

You took two ontology files differing by eighteen raw triples and got back a
five-line summary that told you *exactly one* change is dangerous. That
compression — from triples to meaning — is the whole point of owlcompare.

## Next steps

- [Understanding the output](understanding-output.md) — the layer model and the
  severity definitions, in depth.
- [CI integration](../guides/ci-integration.md) — make this run on every PR.
- [CLI reference](../reference/cli.md) — every command and flag.
