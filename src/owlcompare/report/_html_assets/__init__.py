"""Bundled static assets for the HTML report (Component 17).

This package holds the hand-written stylesheet (``styles.css``) and the vanilla
interactive script (``interactive.js``) that :mod:`owlcompare.report.html_report`
inlines into the rendered document via :func:`importlib.resources.files`. The
files are *source* artifacts, committed and reviewed as code, never generated.
They ship as package data so the renderer works for installed users too. See
``specs/17-html-report.md`` and ``docs/design/``.
"""
