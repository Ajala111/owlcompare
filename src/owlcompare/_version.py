"""Single source of truth for the package version.

`pyproject.toml` reads this dynamically via Hatchling (see DD-013), and
`owlcompare.__init__` re-exports it for programmatic access.
"""

__version__ = "0.0.1"
