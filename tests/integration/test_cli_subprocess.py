"""Integration test: `python -m owlcompare` matches the console-script entry."""

import subprocess
import sys

from owlcompare import __version__


def test_python_dash_m_works():
    module_run = subprocess.run(
        [sys.executable, "-m", "owlcompare", "--version"],
        capture_output=True,
        text=True,
    )
    # The console script calls owlcompare.cli:main; invoke it the same way.
    entry_run = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from owlcompare.cli import main; sys.exit(main(['--version']))",
        ],
        capture_output=True,
        text=True,
    )

    assert module_run.returncode == 0
    assert module_run.stdout == f"owlcompare {__version__}\n"
    assert module_run.stdout == entry_run.stdout
    assert module_run.returncode == entry_run.returncode
