"""Perplexity.ai API client — Search, Responses, and Embeddings.

Wraps three Perplexity endpoints:
- ``/search``         — keyword web search, returns ranked result snippets
- ``/v1/responses``   — AI-generated answer with citations (presets: fast-search, etc.)
- ``/v1/embeddings``  — text embeddings (model: pplx-embed-v1-4b)

Self-contained: reads PERPLEXITY_API_KEY from environment.
No dependency on any per-project config or vendor SDK.

Usage (from any workspace project)::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(r"f:\\⊕Workspace")))
    from src.integrations.perplexity import PerplexityClient

    client = PerplexityClient.from_env()

    # Web search — ranked snippets
    results = client.search("fed funds rate 2026", max_results=5)
    for r in results.results:
        print(r.title, r.url)

    # AI response with citations
    resp = client.respond("Summarize recent Fed policy changes.")
    print(resp.text)
    print(resp.usage)

    # Embeddings
    emb = client.embed(["text one", "text two"])
    print(len(emb.embeddings[0]))  # 3416-dim vectors

Environment variables
---------------------
PERPLEXITY_API_KEY : API key from https://www.perplexity.ai/settings/api
    Required — no default.
"""

from __future__ import annotations

import base64
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://api.perplexity.ai"
_SEARCH_ENDPOINT = "/search"
_RESPONSES_ENDPOINT = "/v1/responses"
_EMBEDDINGS_ENDPOINT = "/v1/embeddings"

DEFAULT_EMBED_MODEL = "pplx-embed-v1-4b"

# Timeouts (seconds) — /v1/responses can be slow on deep-search presets
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 120.0
_TIMEOUT = httpx.Timeout(
    connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=10.0, pool=5.0
)

# Retry settings
_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 1.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Response dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single result item from ``/search``."""

    title: str
    url: str
    snippet: str
    last_updated: str


@dataclass
class SearchResponse:
    """Response from ``/search``."""

    id: str
    results: list[SearchResult]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class AIResponse:
    """Response from ``/v1/responses``."""

    id: str
    text: str
    """Extracted text from the first output_text content block."""

    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    """Usage dict including ``cost``, ``input_tokens``, ``output_tokens``."""

    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class EmbeddingResponse:
    """Response from ``/v1/embeddings``."""

    model: str
    embeddings: list[list[float]]
    """Ordered list of embedding vectors, one per input text."""

    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PerplexityError(RuntimeError):
    """Raised when the Perplexity API returns an error or is unreachable."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class PerplexityClient:
    """Synchronous HTTP client for the Perplexity.ai API.

    Covers /search, /v1/responses, and /v1/embeddings.
    All calls retry up to _MAX_RETRIES times on 429 / 5xx responses using
    exponential backoff (1s, 2s, 4s).

    API key resolution order:
    1. ``api_key`` constructor argument
    2. ``PERPLEXITY_API_KEY`` environment variable
    """

    def __init__(self, api_key: str | None = None) -> None:
        resolved = (api_key or os.environ.get("PERPLEXITY_API_KEY", "")).strip()
        if not resolved:
            raise EnvironmentError(
                "Perplexity API key not found. "
                "Set the PERPLEXITY_API_KEY environment variable or pass api_key= explicitly. "
                "Generate a key at: https://www.perplexity.ai/settings/api"
            )
        self._api_key = resolved
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "PerplexityClient":
        """Construct a client from the PERPLEXITY_API_KEY environment variable.

        Raises
        ------
        EnvironmentError
            If PERPLEXITY_API_KEY is not set or is empty.
        """
        return cls()

    # ------------------------------------------------------------------
    # Public API — /search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        max_tokens_per_page: int = 512,
    ) -> SearchResponse:
        """Web search — returns ranked result snippets with URLs.

        Parameters
        ----------
        query:
            Search query string.
        max_results:
            Maximum number of result items to return (default 5).
        max_tokens_per_page:
            Token budget per result page for snippet extraction.

        Returns
        -------
        SearchResponse
            Ranked results with title, url, snippet, last_updated.

        Raises
        ------
        PerplexityError
            On API errors, connection failures, or exhausted retries.
        """
        payload: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "max_tokens_per_page": max_tokens_per_page,
        }
        raw = self._post_with_retry(_SEARCH_ENDPOINT, payload)
        return self._parse_search(raw)

    # ------------------------------------------------------------------
    # Public API — /v1/responses
    # ------------------------------------------------------------------

    def respond(
        self,
        input: str,
        *,
        preset: str = "fast-search",
        max_output_tokens: int | None = None,
    ) -> AIResponse:
        """AI-generated answer with web grounding via the Responses API.

        Parameters
        ----------
        input:
            The question or prompt.
        preset:
            Response preset controlling speed/depth (e.g. ``fast-search``).
        max_output_tokens:
            Cap on output tokens. ``None`` uses the API default.

        Returns
        -------
        AIResponse
            Parsed response with extracted text, model, and usage stats.

        Raises
        ------
        PerplexityError
            On API errors, connection failures, or exhausted retries.
        """
        payload: dict[str, Any] = {"preset": preset, "input": input}
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens
        raw = self._post_with_retry(_RESPONSES_ENDPOINT, payload)
        return self._parse_ai_response(raw)

    # ------------------------------------------------------------------
    # Public API — /v1/embeddings
    # ------------------------------------------------------------------

    def embed(
        self,
        texts: list[str],
        *,
        model: str = DEFAULT_EMBED_MODEL,
    ) -> EmbeddingResponse:
        """Generate embeddings for a list of input strings.

        Parameters
        ----------
        texts:
            One or more strings to embed.
        model:
            Embedding model ID (default ``pplx-embed-v1-4b``, 3416-dim).

        Returns
        -------
        EmbeddingResponse
            Ordered list of float vectors (one per input text).

        Raises
        ------
        PerplexityError
            On API errors, connection failures, or exhausted retries.
        """
        payload: dict[str, Any] = {"input": texts, "model": model}
        raw = self._post_with_retry(_EMBEDDINGS_ENDPOINT, payload)
        return self._parse_embeddings(raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_with_retry(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to *path* with exponential backoff on retryable errors."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                delay = _RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                time.sleep(delay)
            try:
                resp = httpx.post(
                    _BASE_URL + path,
                    headers=self._headers,
                    json=payload,
                    timeout=_TIMEOUT,
                )
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                continue  # retry on connection-level failures

            if resp.status_code not in _RETRYABLE_STATUS_CODES:
                return self._check_response(resp, path)

            last_exc = PerplexityError(
                f"Perplexity API returned HTTP {resp.status_code} on attempt "
                f"{attempt + 1}/{_MAX_RETRIES + 1}: {resp.text[:200]}"
            )

        raise PerplexityError(
            f"Perplexity API failed after {_MAX_RETRIES + 1} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc

    @staticmethod
    def _check_response(resp: httpx.Response, path: str) -> dict[str, Any]:
        if resp.status_code >= 400:
            raise PerplexityError(
                f"Perplexity API error on {path}: "
                f"HTTP {resp.status_code} — {resp.text[:400]}"
            )
        try:
            return resp.json()
        except Exception as exc:
            raise PerplexityError(
                f"Perplexity API returned non-JSON response on {path}: {resp.text[:200]}"
            ) from exc

    @staticmethod
    def _parse_search(raw: dict[str, Any]) -> SearchResponse:
        try:
            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("snippet", ""),
                    last_updated=r.get("last_updated", ""),
                )
                for r in raw["results"]
            ]
        except (KeyError, TypeError) as exc:
            raise PerplexityError(
                f"Unexpected /search response shape. Keys: {list(raw.keys())}"
            ) from exc
        return SearchResponse(id=raw.get("id", ""), results=results, raw=raw)

    @staticmethod
    def _parse_ai_response(raw: dict[str, Any]) -> AIResponse:
        try:
            output_blocks = raw["output"]
            # Find the first message block with output_text content
            text = ""
            for block in output_blocks:
                if block.get("type") == "message":
                    for content in block.get("content", []):
                        if content.get("type") == "output_text":
                            text = content["text"]
                            break
                if text:
                    break
            if not text and output_blocks:
                raise KeyError("No output_text block found")
        except (KeyError, TypeError, IndexError) as exc:
            raise PerplexityError(
                f"Unexpected /v1/responses shape. Keys: {list(raw.keys())}"
            ) from exc
        return AIResponse(
            id=raw.get("id", ""),
            text=text,
            model=raw.get("model", ""),
            usage=raw.get("usage", {}),
            raw=raw,
        )

    @staticmethod
    def _parse_embeddings(raw: dict[str, Any]) -> EmbeddingResponse:
        try:
            # Sort by index to ensure ordering; decode base64 int8 or plain list
            sorted_data = sorted(raw["data"], key=lambda x: x["index"])
            embeddings = [PerplexityClient._decode_embedding(item["embedding"]) for item in sorted_data]
        except (KeyError, TypeError) as exc:
            raise PerplexityError(
                f"Unexpected /v1/embeddings response shape. Keys: {list(raw.keys())}"
            ) from exc
        return EmbeddingResponse(
            model=raw.get("model", ""),
            embeddings=embeddings,
            usage=raw.get("usage", {}),
            raw=raw,
        )

    @staticmethod
    def _decode_embedding(raw_emb: Any) -> list[float]:
        """Decode an embedding field — handles base64 int8 (API default) or a list of numbers."""
        if isinstance(raw_emb, str):
            # Default API format: base64-encoded signed int8 values
            data = base64.b64decode(raw_emb)
            n = len(data)
            return [float(v) for v in struct.unpack(f"{n}b", data)]
        # Fallback: already a list of numbers
        return [float(v) for v in raw_emb]
