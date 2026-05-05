"""Canonical shared Ollama integration for all workspace projects.

Re-exports the primary client so callers can write::

    from src.integrations.ollama import OllamaClient
"""

from .client import OllamaClient, OllamaError

__all__ = ["OllamaClient", "OllamaError"]
