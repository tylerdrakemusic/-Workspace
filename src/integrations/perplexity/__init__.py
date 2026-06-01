"""Perplexity.ai workspace integration — public surface."""

from .client import (
    AIResponse,
    EmbeddingResponse,
    PerplexityClient,
    PerplexityError,
    SearchResponse,
    SearchResult,
)

__all__ = [
    "AIResponse",
    "EmbeddingResponse",
    "PerplexityClient",
    "PerplexityError",
    "SearchResponse",
    "SearchResult",
]
