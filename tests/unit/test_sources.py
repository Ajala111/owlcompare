"""Acceptance tests for owlcompare.sources — specs/02-loader.md."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from owlcompare.exceptions import LoadError
from owlcompare.sources import resolve


def test_resolve_file_returns_bytes(tmp_path: Path) -> None:
    path = tmp_path / "ontology.ttl"
    path.write_text("@prefix : <http://example.org/> .\n:Thing a :Class .\n")
    resolved = resolve(path)
    assert resolved.origin == "file"
    assert resolved.description == str(path)
    assert b"@prefix" in resolved.content


def test_resolve_file_missing_raises_load_error(tmp_path: Path) -> None:
    with pytest.raises(LoadError) as info:
        resolve(tmp_path / "does_not_exist.ttl")
    assert "not found" in str(info.value).lower()


def test_resolve_file_directory_raises_load_error(tmp_path: Path) -> None:
    with pytest.raises(LoadError) as info:
        resolve(tmp_path)
    assert "directory" in str(info.value).lower()


@pytest.mark.parametrize(
    "filename, expected_format",
    [
        ("a.ttl", "turtle"),
        ("a.rdf", "xml"),
        ("a.owl", "xml"),
        ("a.jsonld", "json-ld"),
        ("a.nt", "nt"),
        ("a.n3", "n3"),
        ("a.trig", "trig"),
    ],
)
def test_resolve_file_detects_format_from_extension(
    tmp_path: Path, filename: str, expected_format: str
) -> None:
    path = tmp_path / filename
    path.write_text("ignored — content does not need to be valid for extension detection")
    assert resolve(path).detected_format == expected_format


@pytest.mark.parametrize("url", ["ftp://example.org/x.ttl", "file:///tmp/x.ttl"])
def test_resolve_url_https_only(url: str) -> None:
    with pytest.raises(LoadError) as info:
        resolve(url)
    assert "scheme" in str(info.value).lower()


@respx.mock
def test_resolve_url_timeout_raises_load_error() -> None:
    respx.get("https://example.org/onto.ttl").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(LoadError) as info:
        resolve("https://example.org/onto.ttl", timeout_seconds=0.1)
    assert "timed out" in str(info.value).lower()
    assert "0.1" in str(info.value)


@respx.mock
def test_resolve_url_4xx_raises_load_error() -> None:
    respx.get("https://example.org/missing.ttl").mock(return_value=httpx.Response(404))
    with pytest.raises(LoadError) as info:
        resolve("https://example.org/missing.ttl")
    assert "404" in str(info.value)


@respx.mock
def test_resolve_url_uses_content_type_for_format_detection() -> None:
    respx.get("https://example.org/feed").mock(
        return_value=httpx.Response(
            200,
            content=b"<rdf:RDF/>",
            headers={"content-type": "application/rdf+xml; charset=utf-8"},
        )
    )
    resolved = resolve("https://example.org/feed")
    assert resolved.origin == "url"
    assert resolved.detected_format == "xml"
