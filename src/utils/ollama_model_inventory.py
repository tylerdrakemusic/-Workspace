"""Ollama local model inventory and availability monitoring for ⊕Workspace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OLLAMA_MODELS_DIR = Path(r"F:\.ollama\models")
PREFERRED_MODEL = "llama3.3:70b"
DEFAULT_MIN_FREE_BYTES = 90 * 1024**3  # 90 GiB
STATUS_FILE = Path(__file__).resolve().parents[2] / "src" / "config" / "ollama_model_status.json"


@dataclass(slots=True)
class OllamaModelInventoryResult:
    generated_at: str
    selected_model: str
    preferred_model: str
    preferred_available: bool
    available_models: list[str]
    storage_path: str
    storage_path_exists: bool
    free_bytes: int | None
    can_auto_pull: bool
    pull_attempted: bool
    pull_succeeded: bool | None
    pull_reason: str | None
    selected_reason: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "selected_model": self.selected_model,
            "preferred_model": self.preferred_model,
            "preferred_available": self.preferred_available,
            "available_models": self.available_models,
            "storage_path": self.storage_path,
            "storage_path_exists": self.storage_path_exists,
            "free_bytes": self.free_bytes,
            "can_auto_pull": self.can_auto_pull,
            "pull_attempted": self.pull_attempted,
            "pull_succeeded": self.pull_succeeded,
            "pull_reason": self.pull_reason,
            "selected_reason": self.selected_reason,
            "error": self.error,
        }


class OllamaModelInventoryError(RuntimeError):
    pass


def _ollama_cli_path() -> str:
    path = shutil.which("ollama")
    if path is None:
        raise OllamaModelInventoryError("Ollama CLI not found on PATH")
    return path


def _run_ollama_command(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OllamaModelInventoryError(f"Ollama CLI command failed: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise OllamaModelInventoryError(f"Ollama CLI command timed out: {exc}") from exc


def _parse_ollama_list_output(stdout: str) -> list[str]:
    lines = stdout.strip().splitlines()
    if len(lines) <= 1:
        return []

    model_names: list[str] = []
    for line in lines[1:]:
        parts = line.strip().split()
        if not parts:
            continue
        model_names.append(parts[0])
    return model_names


def list_local_models() -> list[str]:
    command = _ollama_cli_path()
    result = _run_ollama_command([command, "list"], timeout=15)
    if result.returncode != 0:
        raise OllamaModelInventoryError(
            f"ollama list failed: exit {result.returncode} {result.stderr.strip()[:200]}"
        )
    return _parse_ollama_list_output(result.stdout)


def _default_models_dir() -> Path:
    env_path = os.environ.get("OLLAMA_MODELS")
    if env_path:
        return Path(env_path)
    return DEFAULT_OLLAMA_MODELS_DIR


def get_storage_path(storage_path: Path | None = None) -> Path:
    if storage_path is not None:
        return storage_path
    return _default_models_dir()


def get_free_space(path: Path) -> int:
    query_path = path if path.exists() else path.parent
    if not query_path.exists():
        query_path = Path(query_path.drive or "C:\\")
    return shutil.disk_usage(query_path).free


def _can_auto_pull(models_path: Path, min_free_bytes: int) -> tuple[bool, int | None]:
    try:
        free_bytes = get_free_space(models_path)
        return free_bytes >= min_free_bytes, free_bytes
    except Exception:
        return False, None


def _pull_model(model: str, models_path: Path, timeout: int = 600) -> tuple[bool, str | None]:
    command = _ollama_cli_path()
    os.environ["OLLAMA_MODELS"] = str(models_path)
    result = _run_ollama_command([command, "pull", model], timeout=timeout)
    if result.returncode == 0:
        return True, None
    reason = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
    return False, reason


def _select_fallback_model(model_names: list[str]) -> str:
    for name in model_names:
        if "70b" in name:
            return name
    for name in model_names:
        if "13b" in name:
            return name
    for name in model_names:
        if name == "llama3.1:8b":
            return name
    return model_names[0] if model_names else "llama3.1:8b"


def build_status(
    selected_model: str,
    preferred_model: str,
    preferred_available: bool,
    available_models: list[str],
    storage_path: Path,
    free_bytes: int | None,
    can_auto_pull: bool,
    pull_attempted: bool,
    pull_succeeded: bool | None,
    pull_reason: str | None,
    selected_reason: str,
    error: str | None = None,
) -> OllamaModelInventoryResult:
    return OllamaModelInventoryResult(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        selected_model=selected_model,
        preferred_model=preferred_model,
        preferred_available=preferred_available,
        available_models=available_models,
        storage_path=str(storage_path),
        storage_path_exists=storage_path.exists(),
        free_bytes=free_bytes,
        can_auto_pull=can_auto_pull,
        pull_attempted=pull_attempted,
        pull_succeeded=pull_succeeded,
        pull_reason=pull_reason,
        selected_reason=selected_reason,
        error=error,
    )


def select_best_local_model(
    override: str | None = None,
    storage_path: Path | None = None,
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES,
    auto_pull: bool = True,
) -> OllamaModelInventoryResult:
    models_path = get_storage_path(storage_path)
    pull_attempted = False
    pull_succeeded: bool | None = None
    pull_reason: str | None = None
    selected_reason = ""
    available_models: list[str] = []
    preferred_available = False
    free_bytes: int | None = None
    can_auto = False

    try:
        free_bytes = get_free_space(models_path)
        can_auto, free_bytes = _can_auto_pull(models_path, min_free_bytes)
    except Exception:
        free_bytes = None
        can_auto = False

    if override is not None:
        selected_reason = "explicit override"
        return build_status(
            selected_model=override,
            preferred_model=override,
            preferred_available=override in list_local_models(),
            available_models=list_local_models(),
            storage_path=models_path,
            free_bytes=free_bytes,
            can_auto_pull=can_auto,
            pull_attempted=False,
            pull_succeeded=None,
            pull_reason=None,
            selected_reason=selected_reason,
        )

    try:
        available_models = list_local_models()
    except OllamaModelInventoryError as exc:
        return build_status(
            selected_model=PREFERRED_MODEL,
            preferred_model=PREFERRED_MODEL,
            preferred_available=False,
            available_models=[],
            storage_path=models_path,
            free_bytes=free_bytes,
            can_auto_pull=can_auto,
            pull_attempted=False,
            pull_succeeded=None,
            pull_reason=None,
            selected_reason="failed to list local models",
            error=str(exc),
        )

    preferred_available = PREFERRED_MODEL in available_models

    if preferred_available:
        selected_reason = "preferred model already installed"
        return build_status(
            selected_model=PREFERRED_MODEL,
            preferred_model=PREFERRED_MODEL,
            preferred_available=True,
            available_models=available_models,
            storage_path=models_path,
            free_bytes=free_bytes,
            can_auto_pull=can_auto,
            pull_attempted=False,
            pull_succeeded=None,
            pull_reason=None,
            selected_reason=selected_reason,
        )

    if auto_pull and can_auto:
        pull_attempted = True
        pull_succeeded, pull_reason = _pull_model(PREFERRED_MODEL, models_path)
        if pull_succeeded:
            try:
                available_models = list_local_models()
                preferred_available = PREFERRED_MODEL in available_models
            except OllamaModelInventoryError as exc:
                return build_status(
                    selected_model=PREFERRED_MODEL,
                    preferred_model=PREFERRED_MODEL,
                    preferred_available=False,
                    available_models=[],
                    storage_path=models_path,
                    free_bytes=free_bytes,
                    can_auto_pull=can_auto,
                    pull_attempted=pull_attempted,
                    pull_succeeded=pull_succeeded,
                    pull_reason=pull_reason,
                    selected_reason="preferred pull succeeded but failed to refresh model list",
                    error=str(exc),
                )

        if preferred_available:
            selected_reason = "preferred model pulled successfully"
            return build_status(
                selected_model=PREFERRED_MODEL,
                preferred_model=PREFERRED_MODEL,
                preferred_available=True,
                available_models=available_models,
                storage_path=models_path,
                free_bytes=free_bytes,
                can_auto_pull=can_auto,
                pull_attempted=pull_attempted,
                pull_succeeded=pull_succeeded,
                pull_reason=pull_reason,
                selected_reason=selected_reason,
            )

    if not can_auto and auto_pull:
        selected_reason = (
            "preferred model missing and auto-pull skipped due to low disk space"
            if free_bytes is not None
            else "preferred model missing and auto-pull unavailable"
        )
    elif pull_attempted and not pull_succeeded:
        selected_reason = "preferred model missing and pull failed"
    else:
        selected_reason = "preferred model missing"

    selected_model = _select_fallback_model(available_models)
    if selected_model == PREFERRED_MODEL:
        selected_reason = "preferred model missing but selected fallback equals preferred model"

    return build_status(
        selected_model=selected_model,
        preferred_model=PREFERRED_MODEL,
        preferred_available=preferred_available,
        available_models=available_models,
        storage_path=models_path,
        free_bytes=free_bytes,
        can_auto_pull=can_auto,
        pull_attempted=pull_attempted,
        pull_succeeded=pull_succeeded,
        pull_reason=pull_reason,
        selected_reason=selected_reason,
    )


def write_status(result: OllamaModelInventoryResult, path: Path | None = None) -> Path:
    output_path = path or STATUS_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return output_path


def format_bytes(bytes_value: int | None) -> str:
    if bytes_value is None:
        return "unknown"
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PiB"


def format_summary(result: OllamaModelInventoryResult) -> str:
    lines = [
        f"generated_at: {result.generated_at}",
        f"storage_path: {result.storage_path} ({'exists' if result.storage_path_exists else 'missing'})",
        f"free_space: {format_bytes(result.free_bytes)}",
        f"preferred_model: {result.preferred_model}",
        f"preferred_available: {result.preferred_available}",
        f"selected_model: {result.selected_model}",
        f"selected_reason: {result.selected_reason}",
        f"available_models: {', '.join(result.available_models) if result.available_models else 'none'}",
        f"pull_attempted: {result.pull_attempted}",
        f"pull_succeeded: {result.pull_succeeded}",
        f"pull_reason: {result.pull_reason or 'none'}",
        f"can_auto_pull: {result.can_auto_pull}",
        f"error: {result.error or 'none'}",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor local Ollama models, auto-pull preferred models, and write availability status."
    )
    parser.add_argument(
        "--storage-path",
        type=Path,
        default=None,
        help="Custom local Ollama models directory (default: env OLLAMA_MODELS or F:\\.ollama\\models).",
    )
    parser.add_argument(
        "--no-auto-pull",
        action="store_true",
        help="Detect missing models without attempting to pull them.",
    )
    parser.add_argument(
        "--min-free-gb",
        type=int,
        default=int(DEFAULT_MIN_FREE_BYTES / 1024**3),
        help="Minimum free space required to auto-pull the preferred model, in GiB.",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=None,
        help=f"Path to write JSON status output (default: {STATUS_FILE}).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    auto_pull = not args.no_auto_pull
    min_free_bytes = args.min_free_gb * 1024**3
    storage_path = args.storage_path
    try:
        result = select_best_local_model(
            storage_path=storage_path,
            min_free_bytes=min_free_bytes,
            auto_pull=auto_pull,
        )
    except OllamaModelInventoryError as exc:
        result = build_status(
            selected_model=PREFERRED_MODEL,
            preferred_model=PREFERRED_MODEL,
            preferred_available=False,
            available_models=[],
            storage_path=get_storage_path(storage_path),
            free_bytes=None,
            can_auto_pull=False,
            pull_attempted=False,
            pull_succeeded=None,
            pull_reason=None,
            selected_reason="failed to determine model inventory",
            error=str(exc),
        )
    status_file = args.status_file or STATUS_FILE
    write_status(result, status_file)
    print(f"[ollama_model_inventory] Status written to {status_file}")
    print(format_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
