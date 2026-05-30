"""Source resolution: file path or URL → bytes + provenance.

Reserved for v2: ``git:<ref>:<path>`` shorthand. See ``specs/02-loader.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from owlcompare.exceptions import LoadError

logger = logging.getLogger(__name__)

# Extension → rdflib format name (kept as rdflib's strings so the loader can
# pass them straight to ``Graph.parse(format=...)``).
_EXTENSION_TO_FORMAT: dict[str, str] = {
    ".ttl": "turtle",
    ".rdf": "xml",
    ".owl": "xml",
    ".jsonld": "json-ld",
    ".json": "json-ld",
    ".nt": "nt",
    ".n3": "n3",
    ".trig": "trig",
}

_CONTENT_TYPE_TO_FORMAT: dict[str, str] = {
    "text/turtle": "turtle",
    "application/x-turtle": "turtle",
    "application/rdf+xml": "xml",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/ld+json": "json-ld",
    "application/n-triples": "nt",
    "text/n3": "n3",
    "application/trig": "trig",
}

_HTTP_ACCEPT = (
    "text/turtle, application/rdf+xml;q=0.9, application/ld+json;q=0.8, "
    "application/n-triples;q=0.7, */*;q=0.5"
)


@dataclass(frozen=True, slots=True)
class ResolvedSource:
    """Result of resolving a source specifier to its bytes + metadata."""

    description: str
    content: bytes
    detected_format: str | None
    origin: Literal["file", "url"]


def _format_from_extension(path: str | Path) -> str | None:
    suffix = Path(str(path)).suffix.lower()
    return _EXTENSION_TO_FORMAT.get(suffix)


def _resolve_file(path: Path) -> ResolvedSource:
    if not path.exists():
        raise LoadError(f"file not found: {path}")
    if path.is_dir():
        raise LoadError(f"source is a directory, expected a file: {path}")
    try:
        content = path.read_bytes()
    except PermissionError as exc:
        raise LoadError(f"permission denied: {path}") from exc
    except OSError as exc:
        raise LoadError(f"failed to read file {path}: {exc}") from exc
    return ResolvedSource(
        description=str(path),
        content=content,
        detected_format=_format_from_extension(path),
        origin="file",
    )


def _resolve_url(url: str, timeout_seconds: float) -> ResolvedSource:
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"Accept": _HTTP_ACCEPT})
    except httpx.TimeoutException as exc:
        raise LoadError(f"timed out fetching {url} after {timeout_seconds}s") from exc
    except httpx.HTTPError as exc:
        raise LoadError(f"failed to fetch {url}: {exc}") from exc

    if response.is_error:
        raise LoadError(f"HTTP {response.status_code} fetching {url}: {response.reason_phrase}")

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    detected = _format_from_extension(url) or _CONTENT_TYPE_TO_FORMAT.get(content_type)
    return ResolvedSource(
        description=str(response.url),
        content=response.content,
        detected_format=detected,
        origin="url",
    )


def resolve(specifier: str | Path, timeout_seconds: float = 30.0) -> ResolvedSource:
    """Resolve a source specifier to its bytes.

    Args:
        specifier: A filesystem path or an ``http(s)://`` URL.
        timeout_seconds: Network timeout for URL fetches; ignored for files.

    Raises:
        LoadError: file missing/unreadable, directory passed, network failure,
            non-2xx HTTP status, or unsupported URL scheme.
    """
    if isinstance(specifier, Path):
        return _resolve_file(specifier)
    if specifier.startswith(("http://", "https://")):
        return _resolve_url(specifier, timeout_seconds)
    if "://" in specifier:
        scheme = specifier.split("://", 1)[0]
        raise LoadError(f"unsupported URL scheme: {scheme}:// (only http/https)")
    return _resolve_file(Path(specifier))
