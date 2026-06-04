"""Text-formatting helpers for the Markdown report (Component 15).

Three concerns live here so :mod:`owlcompare.report.markdown_report` can stay
focused on document structure: escaping user-supplied text so Markdown specials
render literally, mapping severities to emoji / plain tags, and shortening IRIs
to prefixed display forms. See ``specs/15-markdown-report.md``.
"""

from __future__ import annotations

from owlcompare.diff._common import Severity, shorten_synthetic_iri
from owlcompare.model import shorten_iri

# Markdown special characters that must be escaped when they appear in
# user-supplied text (labels, comments, annotation values). Inside backtick code
# spans these are already literal, so only free text is escaped. See spec
# § Special character escaping.
_MARKDOWN_SPECIALS = frozenset("*_~`[]()<>\\|")

# Per-severity bullet indicators. Renames use a dedicated pencil regardless of
# severity (a rename is always informational). Spec § Sectioning rules.
_SEVERITY_EMOJI: dict[Severity, str] = {
    "breaking": "🔴",
    "non_breaking": "🟡",
    "additive": "🟢",
    "info": "⚪",
}
_SEVERITY_PLAIN: dict[Severity, str] = {
    "breaking": "[BREAKING]",
    "non_breaking": "[NON-BREAKING]",
    "additive": "[ADDITIVE]",
    "info": "[INFO]",
}
_RENAME_EMOJI = "✏️"
_RENAME_PLAIN = "[RENAME]"

# Title-line status indicators (a coarser three-way status than the per-bullet
# severity icons). Spec § Severity summary phrasing.
_TITLE_EMOJI = {"breaking": "🔴", "ok": "🟢", "none": "⚪"}
_TITLE_PLAIN = {"breaking": "[BREAKING]", "ok": "[OK]", "none": "[NONE]"}


def escape_markdown(text: str) -> str:
    """Backslash-escape every Markdown special character in ``text``.

    A single left-to-right pass prefixes each special with a backslash; because
    ``\\`` is itself in the special set it is escaped naturally, so the function
    is safe to apply once to arbitrary user content without double-escaping.
    ``<`` and ``>`` are escaped too, so HTML in a label renders as text.
    """
    return "".join(f"\\{ch}" if ch in _MARKDOWN_SPECIALS else ch for ch in text)


def severity_icon(severity: Severity, *, emoji: bool) -> str:
    """Bullet indicator for a change of ``severity`` (emoji or plain tag)."""
    table = _SEVERITY_EMOJI if emoji else _SEVERITY_PLAIN
    return table[severity]


def rename_icon(*, emoji: bool) -> str:
    """Bullet indicator for a rename change (the pencil / ``[RENAME]``)."""
    return _RENAME_EMOJI if emoji else _RENAME_PLAIN


def title_icon(status: str, *, emoji: bool) -> str:
    """Title-line indicator for one of ``'breaking'`` / ``'ok'`` / ``'none'``."""
    table = _TITLE_EMOJI if emoji else _TITLE_PLAIN
    return table[status]


def normalize_source(source: str) -> str:
    """Convert a Windows file-path source to forward slashes for stable output.

    Diff reports are shared across machines (committed to PRs, pasted into CI
    logs), so a Windows source like ``tests\\fixtures\\a.ttl`` is rewritten to
    ``tests/fixtures/a.ttl``. URLs (anything containing ``://``) and sources with
    no backslash are returned unchanged — only a string that clearly looks like a
    Windows path is normalized.
    """
    if "\\" in source and "://" not in source:
        return source.replace("\\", "/")
    return source


def prefix_iri(iri: str, prefixes: dict[str, str]) -> str:
    """Display form of ``iri``: ``prefix:local`` when known, else the full IRI.

    Synthetic restriction / list URNs from canonicalization collapse to their
    compact ``_restriction:abc12345`` form (reusing Component 05's helper). The
    result is *not* wrapped in backticks — the caller decides that.
    """
    return shorten_synthetic_iri(shorten_iri(iri, prefixes))
