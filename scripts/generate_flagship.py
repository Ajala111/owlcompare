#!/usr/bin/env python
"""Regenerate the flagship FIBO demo outputs (Component 21).

This script re-runs ``owlcompare diff`` on the committed FIBO Business Entities
files and writes all four output formats to the showcase assets directory, then
prints the "at a glance" metrics so they can be pasted into the showcase page.

It is run *manually* during implementation and after an owlcompare upgrade; it is
**not** part of the docs build pipeline. The generated outputs are committed to
the repo so the showcase is reproducible from a clean checkout.

Usage
-----
    uv run python scripts/generate_flagship.py

What it does
------------
1. Diffs ``examples/fibo_demo/v1/.../Executives.rdf`` against the v2 copy, once
   per format (JSON, HTML, Markdown, JUnit XML), writing to
   ``site_src/docs/showcase/assets/fibo-diff-report.{json,html,md,xml}``.
2. Reads the JSON back and prints the metrics for the at-a-glance table.
3. Creates a *placeholder* preview PNG (``fibo-diff-report-preview.png``) **only
   if one does not already exist** — so re-running this script never clobbers a
   real, human-captured screenshot.

Capturing the real preview screenshot (manual — replaces the placeholder)
-------------------------------------------------------------------------
The preview PNG on the showcase page is a static screenshot of the HTML report.
owlcompare ships no headless browser, so capture it manually, exactly as the
landing-page screenshots are captured (see ``site_src/docs/assets/README.md``):

1. Open ``site_src/docs/showcase/assets/fibo-diff-report.html`` in Chrome.
2. F12 -> Ctrl+Shift+M -> set the viewport to 1440 x 900.
3. DevTools (three-dot) menu -> "Capture full size screenshot".
4. Save as ``site_src/docs/showcase/assets/fibo-diff-report-preview.png``,
   overwriting the placeholder this script created.
5. Rebuild: ``uv run mkdocs build --strict`` and confirm the showcase renders.

There is no automated drift detection: re-run this script (and re-capture the
screenshot) whenever owlcompare's output or the FIBO source files change.
"""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import zlib
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
V1 = REPO_ROOT / "examples" / "fibo_demo" / "v1" / "OwnershipAndControl" / "Executives.rdf"
V2 = REPO_ROOT / "examples" / "fibo_demo" / "v2" / "OwnershipAndControl" / "Executives.rdf"
ASSETS = REPO_ROOT / "site_src" / "docs" / "showcase" / "assets"

# (format flag, output filename) — one owlcompare invocation each.
FORMATS = (
    ("json", "fibo-diff-report.json"),
    ("html", "fibo-diff-report.html"),
    ("markdown", "fibo-diff-report.md"),
    ("junit", "fibo-diff-report.xml"),
)
PREVIEW_PNG = "fibo-diff-report-preview.png"

# Component 12.5's anonymous-structure kinds, tracked so the metrics report can
# state the (currently zero) count explicitly rather than implying via absence.
_ANON_KINDS = frozenset(
    {
        "domain_union_changed",
        "domain_union_added",
        "domain_union_removed",
        "range_union_changed",
        "range_union_added",
        "range_union_removed",
        "subclass_union_changed",
        "subclass_union_added",
        "subclass_union_removed",
        "equivalent_class_union_changed",
        "equivalent_class_union_added",
        "equivalent_class_union_removed",
        "datatype_facet_added",
        "datatype_facet_removed",
        "datatype_facet_changed",
        "datatype_base_changed",
        "replaced_by_set",
        "replaced_by_unset",
    }
)


def _run_diff(fmt: str, out_name: str) -> None:
    """Run ``owlcompare diff`` for one format, writing to the assets directory.

    Exit code 10 (breaking changes present) is expected and not an error here.
    """
    out_path = ASSETS / out_name
    # Pass repo-relative paths (cwd=REPO_ROOT) so the committed reports embed
    # "examples/fibo_demo/..." rather than a contributor's absolute home path —
    # keeping the artifacts reproducible byte-for-byte from any checkout.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "owlcompare",
            "diff",
            V1.relative_to(REPO_ROOT).as_posix(),
            V2.relative_to(REPO_ROOT).as_posix(),
            "--format",
            fmt,
            "--out",
            str(out_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode not in (0, 10):
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"owlcompare diff --format {fmt} failed (rc={proc.returncode})")
    print(f"  wrote {out_path.relative_to(REPO_ROOT)}")


def _print_metrics() -> None:
    """Read the generated JSON and print the at-a-glance metrics."""
    data = json.loads((ASSETS / "fibo-diff-report.json").read_text(encoding="utf-8"))
    changes = data["changes"]
    structural = [c for c in changes if c["layer"] == "structural"]
    syntactic = [c for c in changes if c["layer"] == "syntactic"]
    severities = Counter(c["severity"] for c in structural)
    kinds = Counter(c["kind"] for c in structural)

    subsumed: set[str] = set()
    for change in changes:
        for cid in (change.get("details") or {}).get("subsumes", []):
            subsumed.add(cid)
    unexplained = [
        c for c in syntactic if (c.get("details") or {}).get("change_id") not in subsumed
    ]

    renames = sum(v for k, v in kinds.items() if k.endswith("_renamed"))
    anon = sum(v for k, v in kinds.items() if k in _ANON_KINDS)
    facets = sum(v for k, v in kinds.items() if k.startswith("datatype_"))

    print("\n=== At a glance (paste into site_src/docs/showcase/fibo.md) ===")
    print(f"  Total Layer 1 changes        : {len(structural)}")
    print(f"  Breaking                     : {severities.get('breaking', 0)}")
    print(f"  Non-breaking                 : {severities.get('non_breaking', 0)}")
    print(f"  Additive                     : {severities.get('additive', 0)}")
    print(f"  Info                         : {severities.get('info', 0)}")
    print(f"  Renames detected             : {renames}")
    print(f"  Anonymous structure changes  : {anon}")
    print(f"  Datatype facet changes       : {facets}")
    print(f"  Unexplained Layer 0          : {len(unexplained)} (of {len(syntactic)} raw triples)")
    print(f"  Structural kinds             : {dict(kinds)}")


# --- Stdlib-only placeholder PNG -------------------------------------------------
#
# owlcompare ships no image library and adds none for a placeholder. This is a
# tiny 5x7 bitmap font (only the glyphs needed for "SCREENSHOT PENDING") plus a
# minimal PNG encoder, so the placeholder is fully self-contained.

_FONT: dict[str, tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "N": ("10001", "11001", "11001", "10101", "10011", "10011", "10001"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
}


def _draw_text(
    pixels: list[list[tuple[int, int, int]]], text: str, scale: int, color: tuple[int, int, int]
) -> None:
    """Center ``text`` (in the supported glyphs) on the pixel grid."""
    height = len(pixels)
    width = len(pixels[0])
    glyph_w, glyph_h = 5, 7
    advance = (glyph_w + 1) * scale
    total_w = advance * len(text)
    x0 = (width - total_w) // 2
    y0 = (height - glyph_h * scale) // 2
    for i, ch in enumerate(text):
        glyph = _FONT.get(ch, _FONT[" "])
        for ry, row in enumerate(glyph):
            for rx, bit in enumerate(row):
                if bit != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px = x0 + i * advance + rx * scale + dx
                        py = y0 + ry * scale + dy
                        if 0 <= px < width and 0 <= py < height:
                            pixels[py][px] = color


def _write_png(path: Path, pixels: list[list[tuple[int, int, int]]]) -> None:
    """Encode an RGB pixel grid as a PNG using only the stdlib."""
    height = len(pixels)
    width = len(pixels[0])
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter type 0 (None) for each scanline
        for r, g, b in row:
            raw.extend((r, g, b))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _ensure_placeholder_png() -> None:
    """Create the preview placeholder PNG only if no image exists yet."""
    path = ASSETS / PREVIEW_PNG
    if path.exists():
        print(f"  preview PNG exists, leaving it untouched: {path.relative_to(REPO_ROOT)}")
        return
    width, height = 1440, 900
    bg = (63, 81, 181)  # Material indigo, matching the docs primary palette
    fg = (255, 255, 255)
    pixels = [[bg for _ in range(width)] for _ in range(height)]
    # A thin lighter border so it's obviously an intentional placeholder.
    border = (121, 134, 203)
    for x in range(width):
        for y in (*range(6), *range(height - 6, height)):
            pixels[y][x] = border
    for y in range(height):
        for x in (*range(6), *range(width - 6, width)):
            pixels[y][x] = border
    _draw_text(pixels, "SCREENSHOT PENDING", scale=10, color=fg)
    _write_png(path, pixels)
    print(
        f"  wrote PLACEHOLDER preview (capture the real one — see module docstring): "
        f"{path.relative_to(REPO_ROOT)}"
    )


def main() -> None:
    if not V1.is_file() or not V2.is_file():
        raise SystemExit(f"FIBO source files not found:\n  {V1}\n  {V2}")
    ASSETS.mkdir(parents=True, exist_ok=True)
    print(f"Diffing {V1.name} (2023Q3 -> 2024Q3) into {ASSETS.relative_to(REPO_ROOT)}/")
    for fmt, out_name in FORMATS:
        _run_diff(fmt, out_name)
    _ensure_placeholder_png()
    _print_metrics()


if __name__ == "__main__":
    main()
