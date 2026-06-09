"""Content-existence tests for the documentation site (Component 20).

These guard against the cheap-but-painful failure modes: a page with no title, a
stub that was never filled in *below* the placeholder threshold, a missing
section, or a broken internal link. They do not judge content quality — that is
manual review.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "site_src" / "docs"

# Fenced code blocks (``` ... ```) are stripped before link-scanning so that
# example link-like syntax inside a code sample isn't mistaken for a real link.
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_LINK_RE = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)")


def _all_doc_pages() -> list[Path]:
    """Every published Markdown page (excludes the contributor-only assets note)."""
    return sorted(
        p for p in DOCS_DIR.rglob("*.md") if "assets" not in p.relative_to(DOCS_DIR).parts
    )


def _page_ids() -> list[str]:
    return [str(p.relative_to(DOCS_DIR)).replace("\\", "/") for p in _all_doc_pages()]


@pytest.mark.parametrize("page", _all_doc_pages(), ids=_page_ids())
def test_every_docs_page_has_title(page: Path) -> None:
    lines = [ln for ln in page.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines, f"{page.name} is empty"
    assert lines[0].startswith("# "), f"{page.name} must open with a '# Title' heading"


@pytest.mark.parametrize("page", _all_doc_pages(), ids=_page_ids())
def test_every_docs_page_has_more_than_50_words(page: Path) -> None:
    # Catches accidental empty placeholders. Real stub pages clear 100 words.
    words = page.read_text(encoding="utf-8").split()
    assert len(words) > 50, f"{page.name} has only {len(words)} words — looks empty"


def test_getting_started_pages_present() -> None:
    base = DOCS_DIR / "getting-started"
    for name in ("installation", "first-diff", "understanding-output", "next-steps"):
        assert (base / f"{name}.md").is_file(), f"missing getting-started/{name}.md"


def test_guides_pages_present() -> None:
    base = DOCS_DIR / "guides"
    for name in (
        "ci-integration",
        "severity-overrides",
        "rename-detection",
        "reading-html-report",
        "working-with-large-ontologies",
    ):
        assert (base / f"{name}.md").is_file(), f"missing guides/{name}.md"


def test_reference_pages_present() -> None:
    base = DOCS_DIR / "reference"
    for name in ("cli", "json-schema", "severity-rules", "change-kinds", "exit-codes"):
        assert (base / f"{name}.md").is_file(), f"missing reference/{name}.md"


def test_architecture_pages_present() -> None:
    base = DOCS_DIR / "architecture"
    for name in (
        "overview",
        "diff-layers",
        "rename-detection-internals",
        "canonicalization",
    ):
        assert (base / f"{name}.md").is_file(), f"missing architecture/{name}.md"


@pytest.mark.parametrize("page", _all_doc_pages(), ids=_page_ids())
def test_no_broken_internal_links(page: Path) -> None:
    body = _FENCE_RE.sub("", page.read_text(encoding="utf-8"))
    broken: list[str] = []
    for raw_target in _LINK_RE.findall(body):
        target = raw_target.strip().split()[0]  # drop any "(...)" link title
        # Skip external links, mailto, and pure in-page anchors.
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        # We validate internal links to other docs pages and bundled HTML examples.
        if not path_part.endswith((".md", ".html")):
            continue
        resolved = (page.parent / path_part).resolve()
        if not resolved.is_file():
            broken.append(f"{page.name}: [{target}] -> {path_part}")
    assert not broken, "broken internal links found:\n" + "\n".join(broken)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
