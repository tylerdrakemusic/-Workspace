"""Tests for src/integrations/perplexity/client.py — mocked HTTP, no live API needed."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.integrations.perplexity.client import (
    AIResponse,
    DEFAULT_EMBED_MODEL,
    EmbeddingResponse,
    PerplexityClient,
    PerplexityError,
    SearchResponse,
    SearchResult,
    _MAX_RETRIES,
    _RETRYABLE_STATUS_CODES,
    _SEARCH_ENDPOINT,
    _RESPONSES_ENDPOINT,
    _EMBEDDINGS_ENDPOINT,
)


# ---------------------------------------------------------------------------
# Helpers — canned API response shapes (match live API exactly)
# ---------------------------------------------------------------------------

def _search_raw(n: int = 1) -> dict:
    return {
        "id": "fake-search-id",
        "results": [
            {
                "title": f"Result {i}",
                "url": f"https://example.com/{i}",
                "snippet": f"Snippet {i}",
                "last_updated": "2026-06-01",
            }
            for i in range(n)
        ],
    }


def _responses_raw(text: str = "The answer is 42.") -> dict:
    return {
        "id": "resp_fake",
        "model": "sonar-pro",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "id": "msg_fake",
                "content": [
                    {"type": "output_text", "text": text, "annotations": [], "logprobs": []}
                ],
            }
        ],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "cost": {"currency": "USD", "input_cost": 0.001, "total_cost": 0.001},
        },
    }


def _embeddings_raw(n: int = 2, dim: int = 4) -> dict:
    return {
        "data": [{"index": i, "embedding": [0.1 * j for j in range(dim)], "object": "embedding"} for i in range(n)],
        "model": DEFAULT_EMBED_MODEL,
        "object": "list",
        "usage": {"prompt_tokens": 5 * n, "total_tokens": 5 * n},
    }


def _ok(body: dict) -> MagicMock:
    m = MagicMock(spec=httpx.Response)
    m.status_code = 200
    m.json.return_value = body
    m.text = str(body)
    return m


def _err(status: int, text: str = "error") -> MagicMock:
    m = MagicMock(spec=httpx.Response)
    m.status_code = status
    m.json.side_effect = ValueError("not json")
    m.text = text
    return m


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_raises_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="PERPLEXITY_API_KEY"):
            PerplexityClient()

    def test_raises_with_empty_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "   ")
        with pytest.raises(EnvironmentError, match="PERPLEXITY_API_KEY"):
            PerplexityClient()

    def test_explicit_key_bypasses_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        client = PerplexityClient(api_key="pk-test-key")
        assert client._api_key == "pk-test-key"

    def test_from_env_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-env-key")
        client = PerplexityClient.from_env()
        assert client._api_key == "pk-env-key"

    def test_from_env_raises_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        with pytest.raises(EnvironmentError):
            PerplexityClient.from_env()

    def test_bearer_header_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-abc123")
        client = PerplexityClient.from_env()
        assert client._headers["Authorization"] == "Bearer pk-abc123"


# ---------------------------------------------------------------------------
# search() — /search endpoint
# ---------------------------------------------------------------------------

class TestSearch:
    @patch("src.integrations.perplexity.client.httpx.post")
    def test_returns_search_response(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_search_raw(3))

        client = PerplexityClient.from_env()
        resp = client.search("fed funds rate")

        assert isinstance(resp, SearchResponse)
        assert resp.id == "fake-search-id"
        assert len(resp.results) == 3
        assert isinstance(resp.results[0], SearchResult)
        assert resp.results[0].title == "Result 0"
        assert resp.results[0].url == "https://example.com/0"
        assert resp.results[0].snippet == "Snippet 0"
        assert resp.results[0].last_updated == "2026-06-01"

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_posts_to_search_endpoint(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_search_raw())

        PerplexityClient.from_env().search("test", max_results=7, max_tokens_per_page=256)

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["query"] == "test"
        assert kwargs["json"]["max_results"] == 7
        assert kwargs["json"]["max_tokens_per_page"] == 256

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_uses_search_url(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_search_raw())

        PerplexityClient.from_env().search("q")

        args, _ = mock_post.call_args
        assert args[0].endswith(_SEARCH_ENDPOINT)

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_malformed_search_response_raises(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock = MagicMock(spec=httpx.Response)
        mock.status_code = 200
        mock.json.return_value = {"unexpected": "keys"}
        mock.text = "{}"
        mock_post.return_value = mock

        with pytest.raises(PerplexityError, match="shape"):
            PerplexityClient.from_env().search("q")


# ---------------------------------------------------------------------------
# respond() — /v1/responses endpoint
# ---------------------------------------------------------------------------

class TestRespond:
    @patch("src.integrations.perplexity.client.httpx.post")
    def test_returns_ai_response(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_responses_raw("The answer is 42."))

        resp = PerplexityClient.from_env().respond("What is the answer?")

        assert isinstance(resp, AIResponse)
        assert resp.text == "The answer is 42."
        assert resp.id == "resp_fake"
        assert resp.model == "sonar-pro"
        assert resp.usage["input_tokens"] == 100
        assert resp.usage["cost"]["currency"] == "USD"

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_posts_to_responses_endpoint(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_responses_raw())

        PerplexityClient.from_env().respond("query", preset="fast-search")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["preset"] == "fast-search"
        assert kwargs["json"]["input"] == "query"

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_uses_responses_url(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_responses_raw())

        PerplexityClient.from_env().respond("q")

        args, _ = mock_post.call_args
        assert args[0].endswith(_RESPONSES_ENDPOINT)

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_max_output_tokens_forwarded(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_responses_raw())

        PerplexityClient.from_env().respond("q", max_output_tokens=256)

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["max_output_tokens"] == 256

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_malformed_responses_raises(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        m = MagicMock(spec=httpx.Response)
        m.status_code = 200
        m.json.return_value = {"id": "x", "output": [{"type": "tool_call", "content": []}]}
        m.text = "{}"
        mock_post.return_value = m

        with pytest.raises(PerplexityError, match="shape"):
            PerplexityClient.from_env().respond("q")


# ---------------------------------------------------------------------------
# embed() — /v1/embeddings endpoint
# ---------------------------------------------------------------------------

class TestEmbed:
    @patch("src.integrations.perplexity.client.httpx.post")
    def test_returns_embedding_response(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_embeddings_raw(n=2, dim=4))

        resp = PerplexityClient.from_env().embed(["text one", "text two"])

        assert isinstance(resp, EmbeddingResponse)
        assert resp.model == DEFAULT_EMBED_MODEL
        assert len(resp.embeddings) == 2
        assert len(resp.embeddings[0]) == 4
        assert resp.usage["total_tokens"] == 10

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_posts_to_embeddings_endpoint(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_embeddings_raw(n=1))

        PerplexityClient.from_env().embed(["hello"])

        args, kwargs = mock_post.call_args
        assert args[0].endswith(_EMBEDDINGS_ENDPOINT)
        assert kwargs["json"]["input"] == ["hello"]
        assert kwargs["json"]["model"] == DEFAULT_EMBED_MODEL

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_embeddings_ordered_by_index(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        # Return data out of order
        raw = {
            "data": [
                {"index": 1, "embedding": [0.9, 0.9], "object": "embedding"},
                {"index": 0, "embedding": [0.1, 0.1], "object": "embedding"},
            ],
            "model": DEFAULT_EMBED_MODEL,
            "object": "list",
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        }
        mock_post.return_value = _ok(raw)

        resp = PerplexityClient.from_env().embed(["a", "b"])

        assert resp.embeddings[0] == [0.1, 0.1]
        assert resp.embeddings[1] == [0.9, 0.9]

    @patch("src.integrations.perplexity.client.httpx.post")
    def test_custom_model_forwarded(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _ok(_embeddings_raw(n=1))

        PerplexityClient.from_env().embed(["text"], model="pplx-embed-v2")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["model"] == "pplx-embed-v2"


# ---------------------------------------------------------------------------
# Retry logic (shared across all three methods)
# ---------------------------------------------------------------------------

class TestRetry:
    @patch("src.integrations.perplexity.client.time.sleep")
    @patch("src.integrations.perplexity.client.httpx.post")
    def test_retries_on_429(self, mock_post: MagicMock, mock_sleep: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.side_effect = [_err(429), _err(429), _ok(_search_raw())]

        PerplexityClient.from_env().search("q")

        assert mock_post.call_count == 3
        assert mock_sleep.call_args_list == [call(1.0), call(2.0)]

    @patch("src.integrations.perplexity.client.time.sleep")
    @patch("src.integrations.perplexity.client.httpx.post")
    def test_raises_after_max_retries(self, mock_post: MagicMock, mock_sleep: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _err(503)

        with pytest.raises(PerplexityError, match="failed after"):
            PerplexityClient.from_env().search("q")

        assert mock_post.call_count == _MAX_RETRIES + 1

    @patch("src.integrations.perplexity.client.time.sleep")
    @patch("src.integrations.perplexity.client.httpx.post")
    def test_no_retry_on_400(self, mock_post: MagicMock, mock_sleep: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.return_value = _err(400, "bad request")

        with pytest.raises(PerplexityError, match="HTTP 400"):
            PerplexityClient.from_env().search("q")

        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()

    @patch("src.integrations.perplexity.client.time.sleep")
    @patch("src.integrations.perplexity.client.httpx.post")
    def test_retries_on_connect_error(self, mock_post: MagicMock, mock_sleep: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-test")
        mock_post.side_effect = [httpx.ConnectError("refused"), _ok(_search_raw())]

        resp = PerplexityClient.from_env().search("q")

        assert isinstance(resp, SearchResponse)
        assert mock_post.call_count == 2

    @patch("src.integrations.perplexity.client.time.sleep")
    @patch("src.integrations.perplexity.client.httpx.post")
    def test_401_raises_immediately(self, mock_post: MagicMock, mock_sleep: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pk-bad")
        mock_post.return_value = _err(401, "Unauthorized")

        with pytest.raises(PerplexityError, match="HTTP 401"):
            PerplexityClient.from_env().embed(["x"])

        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()

