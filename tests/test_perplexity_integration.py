"""Live integration tests for PerplexityClient — require PERPLEXITY_API_KEY and hit real API.

These tests are EXCLUDED from CI (pytest.ini: addopts = -m 'not integration').

Run locally with:
    C:\\G\\python.exe -m pytest tests/test_perplexity_integration.py -m integration -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.integrations.perplexity import PerplexityClient, PerplexityError, SearchResponse, AIResponse, EmbeddingResponse

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client() -> PerplexityClient:
    key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not key:
        pytest.skip("PERPLEXITY_API_KEY not set")
    return PerplexityClient(api_key=key)


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------

class TestSearchLive:
    def test_search_returns_results(self, client: PerplexityClient) -> None:
        resp = client.search("Perplexity AI company", max_results=3)

        assert isinstance(resp, SearchResponse)
        assert len(resp.results) > 0
        r = resp.results[0]
        assert r.url.startswith("http")
        assert r.title

    def test_search_respects_max_results(self, client: PerplexityClient) -> None:
        resp = client.search("Python programming language", max_results=2)

        assert len(resp.results) <= 2

    def test_search_id_present(self, client: PerplexityClient) -> None:
        resp = client.search("test query")
        assert resp.id


# ---------------------------------------------------------------------------
# /v1/responses
# ---------------------------------------------------------------------------

class TestRespondLive:
    def test_respond_returns_text(self, client: PerplexityClient) -> None:
        resp = client.respond("What is 2 + 2? Reply with just the number.")

        assert isinstance(resp, AIResponse)
        assert "4" in resp.text
        assert resp.id
        assert resp.usage.get("input_tokens", 0) > 0

    def test_respond_usage_has_cost(self, client: PerplexityClient) -> None:
        resp = client.respond("What color is the sky?")

        assert "cost" in resp.usage
        assert resp.usage["cost"]["currency"] == "USD"
        assert resp.usage["cost"]["total_cost"] > 0

    def test_respond_custom_preset(self, client: PerplexityClient) -> None:
        resp = client.respond("What is the capital of France?", preset="fast-search")

        assert isinstance(resp, AIResponse)
        assert "Paris" in resp.text


# ---------------------------------------------------------------------------
# /v1/embeddings
# ---------------------------------------------------------------------------

class TestEmbedLive:
    def test_embed_single_text(self, client: PerplexityClient) -> None:
        resp = client.embed(["hello world"])

        assert isinstance(resp, EmbeddingResponse)
        assert len(resp.embeddings) == 1
        assert len(resp.embeddings[0]) > 100  # pplx-embed-v1-4b is 3416-dim

    def test_embed_multiple_texts_preserves_order(self, client: PerplexityClient) -> None:
        texts = ["apple", "banana", "cherry"]
        resp = client.embed(texts)

        assert len(resp.embeddings) == len(texts)
        # All embeddings are distinct
        assert resp.embeddings[0] != resp.embeddings[1]
        assert resp.embeddings[1] != resp.embeddings[2]

    def test_embed_similar_texts_closer_than_dissimilar(self, client: PerplexityClient) -> None:
        """Semantic sanity check: similar texts should have higher cosine similarity."""
        import math

        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            mag_a = math.sqrt(sum(x * x for x in a))
            mag_b = math.sqrt(sum(y * y for y in b))
            return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0

        resp = client.embed([
            "The stock market rose sharply today.",
            "Equities gained in today's trading session.",
            "I enjoy hiking in the mountains.",
        ])
        sim_related = cosine(resp.embeddings[0], resp.embeddings[1])
        sim_unrelated = cosine(resp.embeddings[0], resp.embeddings[2])

        assert sim_related > sim_unrelated, (
            f"Expected finance sentences more similar ({sim_related:.3f}) "
            f"than hiking sentence ({sim_unrelated:.3f})"
        )

    def test_embed_model_returned(self, client: PerplexityClient) -> None:
        resp = client.embed(["test"])
        assert resp.model == "pplx-embed-v1-4b"

    def test_embed_usage_has_cost(self, client: PerplexityClient) -> None:
        resp = client.embed(["test embedding"])
        assert resp.usage.get("total_tokens", 0) > 0
