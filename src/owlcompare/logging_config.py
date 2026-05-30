"""Logging setup for the CLI.

The CLI is the only place that configures logging; library modules just call
``logging.getLogger(__name__)`` and emit records. No ``print()`` anywhere.
"""

from __future__ import annotations

import logging
import os
import sys

from rich.logging import RichHandler

_ENV_VAR = "OWLCOMPARE_LOG_LEVEL"


def _resolve_level(verbosity: int) -> int:
    """Map a verbosity integer to a logging level.

    Verbosity: <= -1 = ERROR (-q), 0 = WARNING (default), 1 = INFO (-v),
    2+ = DEBUG (-vv). ``OWLCOMPARE_LOG_LEVEL`` (e.g. ``DEBUG``) overrides it.
    """
    env = os.environ.get(_ENV_VAR)
    if env:
        # getLevelName returns the numeric level for a known name, else a string.
        level = logging.getLevelName(env.strip().upper())
        if isinstance(level, int):
            return level
    if verbosity <= -1:
        return logging.ERROR
    if verbosity == 0:
        return logging.WARNING
    if verbosity == 1:
        return logging.INFO
    return logging.DEBUG


def configure_logging(verbosity: int) -> None:
    """Configure the root logger.

    Args:
        verbosity: 0 = WARNING (default), 1 = INFO (-v), 2+ = DEBUG (-vv),
            and <= -1 = ERROR (-q). The ``OWLCOMPARE_LOG_LEVEL`` env var, when
            set to a valid level name, overrides the verbosity argument.

    Uses ``rich.logging.RichHandler`` when stderr is a TTY; falls back to a
    plain ``"<level> <module>: <message>"`` formatter otherwise (e.g. CI logs).
    """
    level = _resolve_level(verbosity)
    root = logging.getLogger()
    root.setLevel(level)

    # Idempotent: drop handlers from a previous configure call before re-adding.
    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler: logging.Handler
    if sys.stderr.isatty():
        handler = RichHandler(show_time=False, show_path=False, rich_tracebacks=True)
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    handler.setLevel(level)
    root.addHandler(handler)
