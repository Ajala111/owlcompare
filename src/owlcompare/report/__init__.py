"""Report renderers (Phase 4).

This package holds every renderer that turns a :class:`~owlcompare.diff._common.DiffResult`
into an external artifact: JSON (the versioned contract — Component 14),
Markdown (PR-comment style — Component 15), and, later, HTML (Components 16/17)
and JUnit XML (Component 18). Each renderer is a pure function of the
``DiffResult``; the CLI decides where the output goes (stdout, file, API).
"""

from __future__ import annotations

from owlcompare.report.json_report import diff_json

__all__ = ["diff_json"]
