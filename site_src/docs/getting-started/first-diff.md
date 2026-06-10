# Your first diff

This is a hands-on, ten-minute walkthrough. You'll create two small ontology
files, diff them, read the output line by line, and then render the same diff as
an HTML report. By the end you'll understand the shape of everything owlcompare
produces.

You only need owlcompare installed — see [Installation](installation.md) if you
haven't yet.

## 1. Create two versions of an ontology

We'll use a tiny Vehicle vocabulary — a deliberately simple, domain-neutral
example. Save this as **`sample_v1.ttl`**:

```turtle
@prefix ex:   <http://example.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/ontology> a owl:Ontology ;
    owl:versionInfo "1.0.0" ;
    rdfs:label "Vehicle Example Ontology"@en .

ex:Vehicle a owl:Class ;
    rdfs:label "Vehicle"@en ;
    rdfs:label "Véhicule"@fr .

ex:Car a owl:Class ;
    rdfs:subClassOf ex:Vehicle ;
    rdfs:label "Car"@en ;
    rdfs:subClassOf [
        a owl:Restriction ;
        owl:onProperty ex:hasWheel ;
        owl:maxCardinality "4"^^xsd:nonNegativeInteger
    ] .

ex:Factory a owl:Class ;
    rdfs:label "Factory"@en .

ex:hasWheel a owl:DatatypeProperty ;
    rdfs:domain ex:Car ;
    rdfs:range xsd:integer ;
    rdfs:label "has wheel count"@en .

ex:assembledAt a owl:ObjectProperty ;
    rdfs:domain ex:Car ;
    rdfs:range ex:Factory ;
    rdfs:label "assembled at"@en .
```

Now save a second version as **`sample_v2.ttl`** with four realistic edits — a new
class, a removed property, a loosened cardinality, and a refined French label —
plus a version bump:

```turtle
@prefix ex:   <http://example.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/ontology> a owl:Ontology ;
    owl:versionInfo "2.0.0" ;
    rdfs:label "Vehicle Example Ontology"@en .

ex:Vehicle a owl:Class ;
    rdfs:label "Vehicle"@en ;
    rdfs:label "Véhicule à moteur"@fr .

ex:Car a owl:Class ;
    rdfs:subClassOf ex:Vehicle ;
    rdfs:label "Car"@en ;
    rdfs:subClassOf [
        a owl:Restriction ;
        owl:onProperty ex:hasWheel ;
        owl:maxCardinality "6"^^xsd:nonNegativeInteger
    ] .

ex:ElectricVehicle a owl:Class ;
    rdfs:subClassOf ex:Vehicle ;
    rdfs:label "Electric Vehicle"@en .

ex:Factory a owl:Class ;
    rdfs:label "Factory"@en .

ex:hasWheel a owl:DatatypeProperty ;
    rdfs:domain ex:Car ;
    rdfs:range xsd:integer ;
    rdfs:label "has wheel count"@en .
```

## 2. Run the diff

```bash
owlcompare diff sample_v1.ttl sample_v2.ttl
```

You'll see:

```text
owlcompare diff
A: sample_v1.ttl
B: sample_v2.ttl

9 triples added, 10 triples removed (1 breaking)

Layer 1 — Structural (5 changes)
  [additive] Class added: ex:ElectricVehicle "Electric Vehicle"@en
  [breaking] Object property removed: ex:assembledAt "assembled at"@en
  [non_breaking] Restriction changed on ex:Car: ex:hasWheel max 4 → max 6
  [info] Label changed on ex:Vehicle (fr): 'Véhicule' → 'Véhicule à moteur'
  [info] Ontology metadata: owl:versionInfo '1.0.0' → '2.0.0'

Layer 0 — Syntactic (0 unexplained)        [use --show-syntactic for all]
```

## 3. Read it line by line

**`9 triples added, 10 triples removed (1 breaking)`** — the raw, triple-level
count. Nineteen triples moved. If that's all your diff tool told you, you'd have
to read all nineteen to find the one that matters. owlcompare keeps going.

**`Layer 1 — Structural (5 changes)`** — those nineteen triples roll up into five
*semantic* events, each tagged with a severity:

- `[additive]`{ data-severity="additive" } **Class added: ex:ElectricVehicle** — a pure
  addition. Nothing that used the old ontology can break because a class appeared.
- `[breaking]`{ data-severity="breaking" } **Object property removed: ex:assembledAt**
  — this is the one that matters. Any query, shape, or code that referenced
  `ex:assembledAt` will now break. owlcompare flags it and **exits with code 10**.
- `[non_breaking]`{ data-severity="non-breaking" } **Restriction changed … max 4 → max 6**
  — the cardinality was *loosened*. Existing data that satisfied "at most 4" still
  satisfies "at most 6", so valid usage doesn't break.
- `[info]`{ data-severity="info" } **Label changed (fr)** — an editorial change to the
  French label on `ex:Vehicle`. Semantically inert.
- `[info]`{ data-severity="info" } **Ontology metadata: versionInfo** — the version
  string bump. Noted, not significant.

**`Layer 0 — Syntactic (0 unexplained)`** — every raw triple change was *explained*
by one of the Layer 1 events above, so there's no leftover noise to show. Pass
`--show-syntactic` if you ever want to see the raw triples anyway.

## 4. Render an HTML report

The terminal view is great for a quick look. For review, generate the
self-contained HTML report:

```bash
owlcompare diff sample_v1.ttl sample_v2.ttl --format html --out report.html
```

Open `report.html` in any browser. It's a single file — no server, no external
assets — so you can email it, commit it to a PR, or archive it. The breaking
change is front and center; everything else is grouped and collapsible. See
[Reading the HTML report](../guides/reading-html-report.md) for a tour.

## 5. Check the exit code

owlcompare follows the Unix convention of meaning-bearing exit codes. Because
this diff contained a breaking change, the process exited **10**:

```bash
owlcompare diff sample_v1.ttl sample_v2.ttl > /dev/null
echo $?
# 10
```

That's the hook CI uses to fail a build. A diff with no breaking changes exits
`0`. The full table is in [Exit codes](../reference/exit-codes.md).

## What just happened

You took two ontology files differing by nineteen raw triples and got back a
five-line summary that told you *exactly one* change is dangerous. That
compression — from triples to meaning — is the whole point of owlcompare.

## Next steps

- [Understanding the output](understanding-output.md) — the layer model and the
  severity definitions, in depth.
- [CI integration](../guides/ci-integration.md) — make this run on every PR.
- [CLI reference](../reference/cli.md) — every command and flag.
```
