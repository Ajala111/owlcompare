# FIBO flagship demo sources

This directory holds the source ontology files for owlcompare's flagship
showcase (Component 21). The showcase page itself is at
[`site_src/docs/showcase/fibo.md`](../../site_src/docs/showcase/fibo.md); the
rendered diff outputs live in `site_src/docs/showcase/assets/`.

## What's here

```
examples/fibo_demo/
├── v1/            # FIBO-BE module, release 2023Q3 (52 .rdf files + FIBO's own README)
├── v2/            # FIBO-BE module, release 2024Q3 (52 .rdf files + FIBO's own README)
├── LICENSE-FIBO   # verbatim copy of FIBO's MIT license, preserved per attribution
└── README.md      # this file
```

`v1/` and `v2/` are the **FIBO Business Entities (BE)** module, copied unmodified
from the EDM Council distribution. The structure under each is identical (legal
entities, corporations, government entities, ownership & control, partnerships,
trusts, …). FIBO ships these as **RDF/XML (`.rdf`)**, not Turtle; owlcompare loads
RDF/XML transparently via rdflib.

## Exact versions

| Version | FIBO release | Git tag | Released |
|---------|--------------|---------|----------|
| `v1/`   | 2023 Q3      | [`master_2023Q3`](https://github.com/edmcouncil/fibo/releases/tag/master_2023Q3) | September 2023 |
| `v2/`   | 2024 Q3      | [`master_2024Q3`](https://github.com/edmcouncil/fibo/releases/tag/master_2024Q3) | September 2024 |

EDM Council tags each quarterly release as `master_<year>Q<quarter>`. The flagship
diff spans one year (four quarterly releases).

## Source

- Repository: <https://github.com/edmcouncil/fibo>
- Specification site: <https://spec.edmcouncil.org/fibo/>
- Release notes: <https://github.com/edmcouncil/fibo/releases>
- BE module path within the repo: `BE/`

These files were obtained with shallow clones at the two tags and the `BE/`
directory copied in verbatim:

```bash
git clone --depth 1 --branch master_2023Q3 https://github.com/edmcouncil/fibo.git fibo-v1
git clone --depth 1 --branch master_2024Q3 https://github.com/edmcouncil/fibo.git fibo-v2
cp -r fibo-v1/BE/. examples/fibo_demo/v1/
cp -r fibo-v2/BE/. examples/fibo_demo/v2/
cp    fibo-v1/LICENSE examples/fibo_demo/LICENSE-FIBO
```

## License & attribution

FIBO is published by the
[Enterprise Data Management Council (EDM Council)](https://edmcouncil.org/) and
standardized by the [Object Management Group (OMG)](https://www.omg.org/), and is
licensed under the **MIT License** (Copyright © 2020 Enterprise Data Management
Council). The MIT license requires that the copyright and permission notice be
preserved in redistributions; the verbatim notice is kept here as `LICENSE-FIBO`.

owlcompare is not affiliated with or endorsed by EDM Council, OMG, or any FIBO
contributor. These files are redistributed unmodified as a representative,
publicly-available test case.

## Reproduce the flagship diff

The showcase diffs a single substantive sub-ontology,
`OwnershipAndControl/Executives.rdf`, as representative of the module's evolution:

```bash
uv run python -m owlcompare diff \
  examples/fibo_demo/v1/OwnershipAndControl/Executives.rdf \
  examples/fibo_demo/v2/OwnershipAndControl/Executives.rdf \
  --format html --out flagship-report.html
```

## Regenerate all showcase outputs

`scripts/generate_flagship.py` re-runs the diff in all four formats (JSON, HTML,
Markdown, JUnit XML), writes them to `site_src/docs/showcase/assets/`, and prints
the at-a-glance metrics:

```bash
uv run python scripts/generate_flagship.py
```

The committed reports use repo-relative input paths, so regenerating from any
clean checkout produces byte-identical output (for the same owlcompare version).

## Regenerate the preview screenshot

The preview image (`fibo-diff-report-preview.png`) is a static screenshot of the
HTML report. `generate_flagship.py` writes a **placeholder** PNG only if none
exists (it never overwrites a real screenshot). To capture the real one:

1. Open `site_src/docs/showcase/assets/fibo-diff-report.html` in Chrome.
2. `F12` → `Ctrl+Shift+M` → set the viewport to **1440 × 900**.
3. DevTools (⋮) menu → **Capture full size screenshot**.
4. Save as `site_src/docs/showcase/assets/fibo-diff-report-preview.png`,
   overwriting the placeholder.
5. Rebuild: `uv run mkdocs build --strict` and confirm the showcase renders.

Re-capture whenever owlcompare's HTML output changes materially.
