"""Report renderers (Phase 4).

This package holds every renderer that turns a :class:`~owlcompare.diff._common.DiffResult`
into an external artifact: JSON (the versioned contract — Component 14),
Markdown (PR-comment style — Component 15), HTML (the self-contained report —
Component 17), and, later, JUnit XML (Component 18). Each renderer is a pure
function of the ``DiffResult``; the CLI decides where the output goes (stdout,
file, API).
"""

from __future__ import annotations

from owlcompare.report.html_report import HtmlOptions
from owlcompare.report.html_report import render as render_html
from owlcompare.report.json_report import diff_json

__all__ = ["HtmlOptions", "diff_json", "render_html"]
