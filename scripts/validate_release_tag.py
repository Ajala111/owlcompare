"""Validate a git release tag against the package version (Component 22).

This is the single, testable home for the tag/version agreement logic that the
release workflows enforce. It is importable (the unit tests in
``tests/unit/test_release.py`` exercise the two validators directly against fixed
tag/version pairs) and runnable as a CLI (the workflows call it instead of
embedding the logic inline as shell/heredoc Python).

Two modes, deliberately different:

* ``final`` (release.yml → PyPI): the tag version must equal the package version
  **exactly** (PEP 440-normalized). A final release ships precisely what
  ``_version.py`` declares; any drift is a mistake and must block the publish.

* ``pre`` (release-test.yml → TestPyPI): a pre-release tag stages the *upcoming*
  release, so the package version stays at the eventual final version (e.g.
  ``0.1.0``) while you cut ``pre/v0.1.0-rc1``, ``pre/v0.1.0-rc2``, … Requiring
  ``_version.py`` to be bumped to ``0.1.0rc1`` would defeat the point of TestPyPI
  staging. So we compare ``Version.base_version`` (which drops the rc/pre/post/dev
  suffix) and additionally require the tag itself to *be* a pre-release — a
  non-pre-release tag pushed here belongs in release.yml.

Usage::

    python scripts/validate_release_tag.py --mode final --tag v0.1.0
    python scripts/validate_release_tag.py --mode pre   --tag pre/v0.1.0-rc1
"""

from __future__ import annotations

import argparse
import pathlib
import re

from packaging.version import InvalidVersion, Version

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_DEFAULT_VERSION_FILE = _REPO_ROOT / "src" / "owlcompare" / "_version.py"
_VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')


class TagValidationError(Exception):
    """Raised when a tag fails validation against the package version."""


def read_package_version(version_file: pathlib.Path = _DEFAULT_VERSION_FILE) -> str:
    """Return the raw ``__version__`` string from ``_version.py`` (DD-013)."""
    match = _VERSION_RE.search(version_file.read_text(encoding="utf-8"))
    if match is None:
        raise TagValidationError(f"No __version__ found in {version_file}")
    return match.group(1)


def _strip_final_prefix(tag: str) -> str:
    """``v0.1.0`` -> ``0.1.0`` (leave an already-bare version untouched)."""
    return tag[1:] if tag.startswith("v") else tag


def _strip_pre_prefix(tag: str) -> str:
    """``pre/v0.1.0-rc1`` -> ``0.1.0-rc1`` (tolerate missing ``pre/`` or ``v``)."""
    body = tag[len("pre/") :] if tag.startswith("pre/") else tag
    return body[1:] if body.startswith("v") else body


def _parse(tag_version_raw: str, pkg_raw: str) -> tuple[Version, Version]:
    try:
        return Version(tag_version_raw), Version(pkg_raw)
    except InvalidVersion as exc:
        raise TagValidationError(f"Cannot parse version: {exc}") from exc


def validate_final_tag(tag: str, pkg_raw: str) -> tuple[Version, Version]:
    """release.yml semantics: the tag must match the package version exactly.

    Returns the parsed ``(tag_version, package_version)`` on success; raises
    :class:`TagValidationError` otherwise.
    """
    tag_v, pkg_v = _parse(_strip_final_prefix(tag), pkg_raw)
    if tag_v != pkg_v:
        raise TagValidationError(
            f"Tag '{tag}' (=> {tag_v}) does not match package version {pkg_v}. "
            f"Bump src/owlcompare/_version.py and retag, or delete the mismatched tag."
        )
    return tag_v, pkg_v


def validate_pre_tag(tag: str, pkg_raw: str) -> tuple[Version, Version]:
    """release-test.yml semantics: base versions match and the tag is a pre-release.

    The package version stays at the upcoming final version while pre-release tags
    stage it, so we compare base versions (dropping rc/pre/post/dev) and require the
    tag to actually be a pre-release. Returns ``(tag_version, package_version)`` on
    success; raises :class:`TagValidationError` otherwise.
    """
    tag_v, pkg_v = _parse(_strip_pre_prefix(tag), pkg_raw)
    if tag_v.base_version != pkg_v.base_version:
        raise TagValidationError(
            f"Tag '{tag}' base version ({tag_v.base_version}) "
            f"does not match package version {pkg_v.base_version}. "
            f"Bump src/owlcompare/_version.py and retag."
        )
    if not tag_v.is_prerelease:
        raise TagValidationError(
            f"Tag '{tag}' is not a pre-release. "
            f"Use the release.yml workflow for final-release tags."
        )
    return tag_v, pkg_v


_VALIDATORS = {"final": validate_final_tag, "pre": validate_pre_tag}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=sorted(_VALIDATORS), required=True)
    parser.add_argument("--tag", required=True, help="the git tag, e.g. v0.1.0 or pre/v0.1.0-rc1")
    parser.add_argument(
        "--version-file",
        type=pathlib.Path,
        default=_DEFAULT_VERSION_FILE,
        help="path to _version.py (defaults to the package's)",
    )
    args = parser.parse_args(argv)

    try:
        pkg_raw = read_package_version(args.version_file)
        tag_v, pkg_v = _VALIDATORS[args.mode](args.tag, pkg_raw)
    except TagValidationError as exc:
        # ::error:: makes this a GitHub Actions annotation; the text is the reason.
        print(f"::error::{exc}")
        return 1

    print(f"Tag version:     {tag_v}")
    print(f"Package version: {pkg_v}")
    print(f"Base versions match: {tag_v.base_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
