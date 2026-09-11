"""Regression guards for workspace-wide Ollama retirement."""

from pathlib import Path

from src.utils import api_health_monitor


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEALTH_ENDPOINTS = {"elevenlabs", "huggingface", "perplexity"}


def test_workspace_ollama_modules_config_and_tests_are_removed() -> None:
    retired_paths = (
        WORKSPACE_ROOT / "src" / "integrations" / "ollama",
        WORKSPACE_ROOT / "src" / "utils" / "ollama_model_inventory.py",
        WORKSPACE_ROOT / "src" / "config" / "ollama_model_status.json",
        WORKSPACE_ROOT / "tests" / "test_ollama_client.py",
        WORKSPACE_ROOT / "tests" / "test_ollama_model_inventory.py",
    )

    assert not [path for path in retired_paths if path.exists()]


def test_health_monitor_retains_only_supported_provider_endpoints() -> None:
    names = {endpoint["name"] for endpoint in api_health_monitor._ENDPOINTS}

    assert names == EXPECTED_HEALTH_ENDPOINTS