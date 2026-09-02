from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"


def test_proof_health_registration_resolves_paths_from_checkout() -> None:
    source = (TOOLS / "register_proof_health_task.ps1").read_text(encoding="utf-8")

    assert "f:\\⊕Workspace" not in source
    assert "$WorkspaceRoot" in source
    assert "$WorkingDir = $WorkspaceRoot" in source


def test_hygiene_registration_resolves_paths_from_checkout() -> None:
    source = (TOOLS / "register_hygiene_task.ps1").read_text(encoding="utf-8")

    assert "f:\\⊕Workspace" not in source
    assert "$WorkspaceRoot" in source
    assert "$WorkingDir = $WorkspaceRoot" in source


def test_skill_sync_registration_uses_checkout_and_working_directory() -> None:
    source = (TOOLS / "register-skill-sync-task.ps1").read_text(encoding="utf-8")

    assert "f:\\⊕Workspace" not in source
    assert "$WorkspaceRoot" in source
    assert "-WorkingDirectory $WorkspaceRoot" in source