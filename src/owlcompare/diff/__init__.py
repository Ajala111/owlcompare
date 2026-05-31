"""Diff engine package. Layer 0 (syntactic) is implemented; 1-3 are planned."""

from __future__ import annotations

from . import syntactic
from ._common import Change, DiffLayer, DiffOptions, DiffResult, Severity

__all__ = ["Change", "DiffLayer", "DiffOptions", "DiffResult", "Severity", "syntactic"]
