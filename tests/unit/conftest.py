"""Shared fixtures for CLI unit tests.

Typer renders ``--help`` through rich. Two environment-dependent behaviours
break naive substring assertions on that output, and both bite in CI:

1. **Colour.** Under GitHub Actions, Typer sets ``force_terminal=True`` (it keys
   off ``GITHUB_ACTIONS``/``FORCE_COLOR``/``PY_COLORS``), so rich emits ANSI SGR
   codes. Its highlighter styles the two dashes of an option separately, so
   ``--format`` renders as ``-\x1b[0m\x1b[1;36m-format`` — the literal substring
   ``--format`` no longer exists.
2. **Width.** rich truncates/wraps long option names (e.g.
   ``--no-reify-restrictions``) at the terminal width, which defaults to 80 on a
   headless runner.

``clean`` strips the colour codes and joins wrapped lines; ``help_runner`` forces
a wide terminal so nothing is truncated. Together they make help assertions
independent of terminal width and colour support.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from typer.testing import CliRunner

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def clean_help(text: str) -> str:
    """Strip ANSI colour codes and collapse line breaks for substring checks."""
    return _ANSI_ESCAPE.sub("", text).replace("\n", " ")


@pytest.fixture
def clean() -> Callable[[str], str]:
    """Return the help-output normalizer (see :func:`clean_help`)."""
    return clean_help


@pytest.fixture
def help_runner() -> CliRunner:
    """A ``CliRunner`` with a wide terminal so rich never truncates options."""
    return CliRunner(env={"COLUMNS": "200"})
