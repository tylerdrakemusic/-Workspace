"""Tests for src/utils/ollama_model_inventory.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.ollama_model_inventory import (
    DEFAULT_OLLAMA_MODELS_DIR,
    OllamaModelInventoryError,
    OllamaModelInventoryResult,
    PREFERRED_MODEL,
    _parse_ollama_list_output,
    _select_fallback_model,
    get_storage_path,
    list_local_models,
    select_best_local_model,
)


def test_parse_ollama_list_output_strips_header() -> None:
    stdout = "NAME ID SIZE\nllama3.3:70b abc 4GB\nllama3.1:8b def 2GB\n"
    assert _parse_ollama_list_output(stdout) == ["llama3.3:70b", "llama3.1:8b"]


def test_select_fallback_model_prefers_70b() -> None:
    assert _select_fallback_model(["llama3.1:8b", "llama3:70b", "mistral:13b"]) == "llama3:70b"


def test_select_fallback_model_chooses_13b_when_no_70b() -> None:
    assert _select_fallback_model(["llama3.1:8b", "mistral:13b"]) == "mistral:13b"


def test_select_fallback_model_uses_8b_as_last_resort() -> None:
    assert _select_fallback_model(["llama3.1:8b"]) == "llama3.1:8b"


def test_get_storage_path_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODELS", r"D:\\models")
    assert get_storage_path() == Path(r"D:\\models")


def test_get_storage_path_defaults_to_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    assert get_storage_path() == DEFAULT_OLLAMA_MODELS_DIR


def test_list_local_models_invokes_ollama_list(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_run = MagicMock()
    patch_run.return_value = MagicMock(returncode=0, stdout="NAME ID SIZE\nllama3.3:70b abc 4GB\n")
    with patch("shutil.which", return_value="ollama"), patch("subprocess.run", patch_run):
        assert list_local_models() == ["llama3.3:70b"]


def test_list_local_models_raises_when_ollama_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("shutil.which", return_value=None):
        with pytest.raises(OllamaModelInventoryError, match="Ollama CLI not found"):
            list_local_models()


def test_select_best_local_model_returns_override_without_pull(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODELS", r"D:\\models")
    with patch("src.utils.ollama_model_inventory.list_local_models", return_value=["llama3.1:8b"]):
        result = select_best_local_model(override="gemma:2b", auto_pull=False)
    assert result.selected_model == "gemma:2b"
    assert result.preferred_available is False
    assert result.selected_reason == "explicit override"


def test_select_best_local_model_prefers_installed_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("src.utils.ollama_model_inventory.list_local_models", return_value=[PREFERRED_MODEL, "llama3.1:8b"]):
        result = select_best_local_model(auto_pull=False)
    assert result.selected_model == PREFERRED_MODEL
    assert result.preferred_available is True
    assert result.pull_attempted is False
    assert "preferred model already installed" in result.selected_reason


def test_select_best_local_model_falls_back_when_preferred_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("src.utils.ollama_model_inventory.list_local_models", return_value=["llama3:70b", "llama3.1:8b"]), patch("src.utils.ollama_model_inventory._can_auto_pull", return_value=(False, 80 * 1024**3)):
        result = select_best_local_model(auto_pull=False)
    assert result.selected_model == "llama3:70b"
    assert result.preferred_available is False
    assert result.pull_attempted is False
    assert "preferred model missing" in result.selected_reason


def test_select_best_local_model_skips_pull_on_low_space(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("src.utils.ollama_model_inventory.list_local_models", return_value=["llama3:70b"]), patch("src.utils.ollama_model_inventory._can_auto_pull", return_value=(False, 10 * 1024**3)):
        result = select_best_local_model(auto_pull=True)
    assert result.pull_attempted is False
    assert result.pull_succeeded is None
    assert result.selected_model == "llama3:70b"


def test_select_best_local_model_attempts_pull_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("src.utils.ollama_model_inventory.list_local_models", side_effect=[["llama3:70b"], ["llama3:70b", PREFERRED_MODEL]]), patch("src.utils.ollama_model_inventory._can_auto_pull", return_value=(True, 120 * 1024**3)), patch("src.utils.ollama_model_inventory._pull_model", return_value=(True, None)):
        result = select_best_local_model(auto_pull=True)
    assert result.pull_attempted is True
    assert result.pull_succeeded is True
    assert result.preferred_available is True
    assert result.selected_model == PREFERRED_MODEL


def test_select_best_local_model_pulls_fallback_when_preferred_pull_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch(
        "src.utils.ollama_model_inventory.list_local_models",
        side_effect=[["llama3:70b"], ["llama3:70b", "mistral:13b"]],
    ), patch("src.utils.ollama_model_inventory._can_auto_pull", return_value=(True, 120 * 1024**3)), patch(
        "src.utils.ollama_model_inventory._pull_model",
        side_effect=[(False, "preferred fetch failed"), (True, None)],
    ):
        result = select_best_local_model(auto_pull=True)
    assert result.pull_attempted is True
    assert result.pull_succeeded is True
    assert result.selected_model == "mistral:13b"
    assert "fallback mistral:13b pulled successfully" in result.selected_reason
    assert result.preferred_available is False
