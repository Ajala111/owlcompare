"""Build-verification tests for the documentation site (Component 20).

These run as part of the normal pytest suite. They check the site infrastructure
is structurally sound — valid config, every nav target on disk, a self-contained
landing page, a valid publishing workflow — without actually invoking MkDocs
(that is `mkdocs build --strict`, run separately in CI and locally).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
SITE_SRC = REPO_ROOT / "site_src"
INDEX_HTML = SITE_SRC / "index.html"
DOCS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs.yml"


def _load_mkdocs_config() -> dict[str, object]:
    # MkDocs config is plain YAML for our purposes (no Python tags), so safe_load
    # is sufficient and avoids importing mkdocs just to read the file.
    return yaml.safe_load(MKDOCS_YML.read_text(encoding="utf-8"))


def _iter_nav_md_targets(nav: object) -> list[str]:
    """Collect every Markdown file path referenced anywhere in the nav tree."""
    targets: list[str] = []
    if isinstance(nav, list):
        for item in nav:
            targets.extend(_iter_nav_md_targets(item))
    elif isinstance(nav, dict):
        for value in nav.values():
            targets.extend(_iter_nav_md_targets(value))
    elif isinstance(nav, str) and nav.endswith(".md"):
        targets.append(nav)
    return targets


def test_mkdocs_yml_is_valid_yaml() -> None:
    config = _load_mkdocs_config()
    assert isinstance(config, dict)


def test_mkdocs_yml_has_required_fields() -> None:
    config = _load_mkdocs_config()
    for field in ("site_name", "site_url", "theme", "nav"):
        assert field in config, f"mkdocs.yml is missing required field {field!r}"
    assert config["theme"]["name"] == "material"


def test_mkdocs_yml_nav_entries_all_exist() -> None:
    config = _load_mkdocs_config()
    docs_dir = REPO_ROOT / str(config.get("docs_dir", "docs"))
    targets = _iter_nav_md_targets(config["nav"])
    assert targets, "nav contains no Markdown targets — did the config change?"
    missing = [t for t in targets if not (docs_dir / t).is_file()]
    assert not missing, f"nav references files that don't exist on disk: {missing}"


def test_site_src_index_html_exists() -> None:
    assert INDEX_HTML.is_file(), "the custom landing page site_src/index.html is missing"


def test_site_src_index_html_is_valid_html() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")

    # html.parser is lenient; we assert it parses without raising and that the
    # document is well-formed enough to contain a root <html> element.
    class _Collector(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.tags: set[str] = set()

        def handle_starttag(self, tag: str, attrs: object) -> None:
            self.tags.add(tag)

    parser = _Collector()
    parser.feed(text)
    parser.close()
    assert "html" in parser.tags
    assert "head" in parser.tags
    assert "body" in parser.tags


def test_site_src_index_html_has_no_external_resources() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")

    # The landing page must be fully self-contained (same rule as the HTML report,
    # DD-005): no externally-loaded CSS/JS/fonts/images. External *hyperlinks*
    # (an <a href> to GitHub) are fine — only resource loads are forbidden.
    assert not re.search(r"<script[^>]*\bsrc\s*=", text), "external <script src> is not allowed"
    assert not re.search(r"<link[^>]+href\s*=\s*['\"]https?:", text), (
        "external <link> stylesheet/resource is not allowed"
    )
    assert not re.search(r"\bsrc\s*=\s*['\"]https?:", text), (
        "no element may load a resource over http(s)"
    )
    assert "@import" not in text, "CSS @import of an external sheet is not allowed"
    assert not re.search(r"url\(\s*['\"]?https?:", text), "CSS may not reference an external url()"


def test_docs_workflow_yml_is_valid_yaml() -> None:
    config = yaml.safe_load(DOCS_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(config, dict)
    assert "jobs" in config


def test_docs_workflow_yml_runs_mkdocs_build_strict() -> None:
    text = DOCS_WORKFLOW.read_text(encoding="utf-8")
    assert "mkdocs build --strict" in text, (
        "the docs workflow must build with --strict so broken links fail the publish"
    )


def test_docs_workflow_triggers_on_push_main_and_dispatch() -> None:
    text = DOCS_WORKFLOW.read_text(encoding="utf-8")
    # YAML 1.1 coerces the bare `on:` key to True, so assert against the raw text.
    assert "workflow_dispatch" in text
    assert re.search(r"branches:\s*\[main\]", text) or "- main" in text


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
