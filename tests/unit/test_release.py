"""Static validation of the PyPI release pipeline (Component 22).

These tests assert the packaging metadata, changelog, and the two release
workflows are well-formed and internally consistent — the same declarative style
as ``test_action_yml.py`` (Component 19). They do not run a build or publish; the
build is exercised manually and in CI. ``test_release_build`` is the one optional
exception: when ``build`` is installed it builds real artifacts into a temp dir
and inspects them, proving the wheel/sdist split actually holds.
"""

from __future__ import annotations

import importlib.util
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_VERSION_FILE = _REPO_ROOT / "src" / "owlcompare" / "_version.py"
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"
_RELEASE_YML = _REPO_ROOT / ".github" / "workflows" / "release.yml"
_RELEASE_TEST_YML = _REPO_ROOT / ".github" / "workflows" / "release-test.yml"


@pytest.fixture(scope="module")
def pyproject() -> dict[str, Any]:
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def release_yml() -> dict[str, Any]:
    return yaml.safe_load(_RELEASE_YML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def release_test_yml() -> dict[str, Any]:
    return yaml.safe_load(_RELEASE_TEST_YML.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# pyproject metadata
# --------------------------------------------------------------------------- #


def test_pyproject_has_required_pypi_fields(pyproject: dict[str, Any]) -> None:
    project = pyproject["project"]
    for field in (
        "name",
        "description",
        "readme",
        "requires-python",
        "license",
        "authors",
        "keywords",
        "classifiers",
    ):
        assert field in project, f"pyproject [project] is missing '{field}'"
    assert project["name"] == "owlcompare"
    assert project["readme"] == "README.md"
    assert project["requires-python"].startswith(">=3.11")
    assert project["keywords"], "keywords should not be empty"
    assert any(c.startswith("License :: OSI Approved") for c in project["classifiers"])


def test_pyproject_has_project_urls(pyproject: dict[str, Any]) -> None:
    urls = pyproject["project"]["urls"]
    assert "Repository" in urls
    assert "Changelog" in urls
    for url in urls.values():
        assert url.startswith("https://"), f"non-https project URL: {url}"


def test_pyproject_authors_have_name(pyproject: dict[str, Any]) -> None:
    authors = pyproject["project"]["authors"]
    assert authors, "at least one author is required"
    assert all(a.get("name") for a in authors)


def test_entry_point_targets_cli_main(pyproject: dict[str, Any]) -> None:
    # The console script must call cli.main (which owns exit-code mapping), not the
    # raw Typer ``app`` object.
    scripts = pyproject["project"]["scripts"]
    assert scripts["owlcompare"] == "owlcompare.cli:main"


# --------------------------------------------------------------------------- #
# version: dynamic, single-sourced (DD-013)
# --------------------------------------------------------------------------- #


def _module_version() -> str:
    text = _VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert match is not None, "_version.py must declare __version__"
    return match.group(1)


def test_version_is_dynamic_and_single_sourced(pyproject: dict[str, Any]) -> None:
    project = pyproject["project"]
    # Per DD-013 the version is dynamic, sourced from _version.py — there must be no
    # competing static ``version`` field in [project].
    assert "version" in project.get("dynamic", []), "version must be declared dynamic"
    assert "version" not in project, "no static version may shadow the dynamic source"
    hatch_path = pyproject["tool"]["hatch"]["version"]["path"]
    assert hatch_path == "src/owlcompare/_version.py"


def test_module_version_matches_runtime_export() -> None:
    from owlcompare import __version__

    assert __version__ == _module_version()


def test_module_version_is_pep440(pyproject: dict[str, Any]) -> None:
    # A plain X.Y.Z final release for v0.1.0; allow optional pre-release suffixes
    # for staged TestPyPI builds.
    assert re.fullmatch(r"\d+\.\d+\.\d+([abc]|rc)?\d*", _module_version())


# --------------------------------------------------------------------------- #
# wheel / sdist build configuration
# --------------------------------------------------------------------------- #


def test_wheel_excludes_fibo_demo(pyproject: dict[str, Any]) -> None:
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    # The package tree (src/owlcompare) inherently excludes examples/, and the
    # explicit exclude records the intent.
    assert wheel["packages"] == ["src/owlcompare"]
    assert any("examples/fibo_demo" in entry for entry in wheel.get("exclude", []))


def test_sdist_includes_fibo_demo(pyproject: dict[str, Any]) -> None:
    sdist = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]
    includes = sdist["include"]
    assert any("examples/fibo_demo" in entry for entry in includes)
    assert any("src/owlcompare" in entry for entry in includes)


def test_release_build(tmp_path: Path) -> None:
    """Build real artifacts and prove the wheel/sdist data split holds.

    Skipped when ``build`` isn't installed (it is a dev dependency, so this runs
    in CI and on a full ``uv sync``).
    """
    build_api = pytest.importorskip("build")
    import zipfile

    builder = build_api.ProjectBuilder(str(_REPO_ROOT))  # type: ignore[attr-defined]
    try:
        wheel = builder.build("wheel", str(tmp_path))
        sdist = builder.build("sdist", str(tmp_path))
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"build backend unavailable in this environment: {exc}")

    with zipfile.ZipFile(wheel) as zf:
        wheel_names = zf.namelist()
    # The wheel must NOT carry the FIBO demo data...
    assert not any("fibo_demo" in name for name in wheel_names)
    # ...but must carry the package and the bundled JSON schema.
    assert any(name.endswith("schema/diff-result.schema.json") for name in wheel_names)

    import tarfile

    with tarfile.open(sdist) as tf:
        sdist_names = tf.getnames()
    # The sdist is the complete source tarball — it DOES carry the demo data.
    assert any("examples/fibo_demo" in name for name in sdist_names)


# --------------------------------------------------------------------------- #
# CHANGELOG
# --------------------------------------------------------------------------- #


def test_changelog_exists_and_is_keepachangelog() -> None:
    assert _CHANGELOG.exists()
    text = _CHANGELOG.read_text(encoding="utf-8")
    assert "## [Unreleased]" in text, "Keep a Changelog requires an Unreleased section"
    # At least one versioned entry of the form "## [X.Y.Z] - DATE".
    assert re.search(r"^## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}", text, re.MULTILINE)


def test_changelog_has_entry_for_current_version() -> None:
    text = _CHANGELOG.read_text(encoding="utf-8")
    version = _module_version()
    assert f"## [{version}]" in text, f"CHANGELOG has no section for {version}"


# --------------------------------------------------------------------------- #
# release workflows
# --------------------------------------------------------------------------- #


def _permissions(workflow: dict[str, Any]) -> dict[str, str]:
    return workflow["permissions"]


def test_release_yml_is_valid_yaml(release_yml: dict[str, Any]) -> None:
    assert isinstance(release_yml, dict)


def test_release_test_yml_is_valid_yaml(release_test_yml: dict[str, Any]) -> None:
    assert isinstance(release_test_yml, dict)


def test_release_yml_has_oidc_and_release_permissions(release_yml: dict[str, Any]) -> None:
    perms = _permissions(release_yml)
    assert perms["id-token"] == "write", "OIDC Trusted Publishing needs id-token: write"
    assert perms["contents"] == "write", "cutting a GitHub Release needs contents: write"


def test_release_test_yml_has_oidc_permission(release_test_yml: dict[str, Any]) -> None:
    perms = _permissions(release_test_yml)
    assert perms["id-token"] == "write", "OIDC Trusted Publishing needs id-token: write"


def test_release_yml_triggers_on_final_release_tags(release_yml: dict[str, Any]) -> None:
    # PyYAML parses the bare `on:` key as the boolean True.
    on = release_yml[True]
    assert on["push"]["tags"] == ["v*.*.*"]


def test_release_test_yml_triggers_on_pre_tags(release_test_yml: dict[str, Any]) -> None:
    on = release_test_yml[True]
    assert on["push"]["tags"] == ["pre/*"]


def test_release_yml_uses_pypi_environment(release_yml: dict[str, Any]) -> None:
    job = release_yml["jobs"]["release"]
    assert job["environment"]["name"] == "pypi"


def test_release_test_yml_uses_testpypi_environment(release_test_yml: dict[str, Any]) -> None:
    job = release_test_yml["jobs"]["release-test"]
    assert job["environment"]["name"] == "testpypi"


def test_release_yml_publishes_to_pypi_not_testpypi() -> None:
    text = _RELEASE_YML.read_text(encoding="utf-8")
    assert "pypa/gh-action-pypi-publish@release/v1" in text
    assert "test.pypi.org" not in text, "release.yml must NOT target TestPyPI"


def test_release_test_yml_publishes_to_testpypi() -> None:
    text = _RELEASE_TEST_YML.read_text(encoding="utf-8")
    assert "pypa/gh-action-pypi-publish@release/v1" in text
    assert "https://test.pypi.org/legacy/" in text, "release-test.yml must target TestPyPI"


def test_release_test_yml_does_not_create_github_release() -> None:
    text = _RELEASE_TEST_YML.read_text(encoding="utf-8")
    assert "action-gh-release" not in text, "TestPyPI staging must not cut a GitHub Release"


def test_release_yml_creates_github_release() -> None:
    text = _RELEASE_YML.read_text(encoding="utf-8")
    assert "softprops/action-gh-release@v2" in text


@pytest.mark.parametrize("workflow_path", [_RELEASE_YML, _RELEASE_TEST_YML])
def test_workflow_actions_are_pinned(workflow_path: Path) -> None:
    """No `uses:` may float on @main / @master."""
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    floating: list[str] = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if uses and (uses.endswith("@main") or uses.endswith("@master")):
                floating.append(uses)
    assert not floating, f"unpinned actions in {workflow_path.name}: {floating}"


def test_release_yml_validates_tag_against_version() -> None:
    # The pipeline must guard against publishing a tag that disagrees with the
    # package version (the whole point of single-sourcing).
    text = _RELEASE_YML.read_text(encoding="utf-8")
    assert "_version.py" in text
    assert "does not match package version" in text


def test_release_test_yml_calls_validation_script() -> None:
    # The pre-release tag check is delegated to the unit-tested script below rather
    # than embedded as inline shell, so the two stay in lock-step.
    text = _RELEASE_TEST_YML.read_text(encoding="utf-8")
    assert "scripts/validate_release_tag.py --mode pre" in text


# --------------------------------------------------------------------------- #
# tag/version validation logic (scripts/validate_release_tag.py)
# --------------------------------------------------------------------------- #


def _load_validate_module() -> Any:
    """Import scripts/validate_release_tag.py by path (it is not an installed pkg)."""
    path = _REPO_ROOT / "scripts" / "validate_release_tag.py"
    spec = importlib.util.spec_from_file_location("validate_release_tag", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_validate = _load_validate_module()


# release-test.yml (--mode pre): base-version match + must be a pre-release.
# A pre-release tag stages the upcoming final version, so _version.py stays at
# 0.1.0 while pre/v0.1.0-rc1, -rc2, … are cut.
@pytest.mark.parametrize(
    ("tag", "pkg"),
    [
        ("pre/v0.1.0-rc1", "0.1.0"),  # base versions match, tag is a pre-release
        ("pre/v0.1.0-rc2", "0.1.0"),  # the next rc against the same package version
    ],
)
def test_validate_pre_tag_accepts_matching_prereleases(tag: str, pkg: str) -> None:
    tag_v, pkg_v = _validate.validate_pre_tag(tag, pkg)
    assert tag_v.base_version == pkg_v.base_version
    assert tag_v.is_prerelease


def test_validate_pre_tag_rejects_base_version_mismatch() -> None:
    # pre/v0.2.0-rc1 cannot stage a 0.1.0 package — different base version.
    with pytest.raises(_validate.TagValidationError, match="base version"):
        _validate.validate_pre_tag("pre/v0.2.0-rc1", "0.1.0")


def test_validate_pre_tag_rejects_non_prerelease() -> None:
    # pre/v0.1.0 is a final release accidentally pushed to the staging workflow.
    with pytest.raises(_validate.TagValidationError, match="not a pre-release"):
        _validate.validate_pre_tag("pre/v0.1.0", "0.1.0")


# release.yml (--mode final): strict exact-version match, kept strict on purpose.
def test_validate_final_tag_accepts_exact_match() -> None:
    tag_v, pkg_v = _validate.validate_final_tag("v0.1.0", "0.1.0")
    assert tag_v == pkg_v


def test_validate_final_tag_rejects_version_mismatch() -> None:
    with pytest.raises(_validate.TagValidationError, match="does not match package version"):
        _validate.validate_final_tag("v0.1.0", "0.1.1")
