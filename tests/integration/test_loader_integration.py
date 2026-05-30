"""Integration test: ``python -m owlcompare load`` against a real fixture."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_load_via_python_dash_m_against_fixture():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "owlcompare",
            "load",
            str(FIXTURES / "minimal_class.ttl"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "http://example.org/minimal" in result.stdout
    assert "Entity counts:" in result.stdout
    assert "class: 1" in result.stdout
