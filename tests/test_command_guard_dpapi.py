import shutil
import subprocess
from pathlib import Path

import pytest


def _run_guard(guard_script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("pwsh") or "pwsh", "-NoProfile", "-File", str(guard_script), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is required")
def test_block_diagnostics_do_not_disclose_matched_pattern(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    guard_script = repository_root / "tools" / "deny-dangerous.ps1"
    patterns_file = tmp_path / "rules.txt"
    protected_file = tmp_path / "rules.dpapi"
    matched_pattern = r"rm\s+-rf\s+/"
    patterns_file.write_text(matched_pattern + "\n", encoding="utf-8")

    encrypted = _run_guard(
        guard_script,
        "-Maintenance",
        "-PlaintextPatternsFile",
        str(patterns_file),
        "-PatternsFile",
        str(protected_file),
    )
    result = _run_guard(
        guard_script,
        "-Command",
        "rm -rf /",
        "-PatternsFile",
        str(protected_file),
    )

    assert encrypted.returncode == 0, encrypted.stderr
    assert result.returncode == 2
    assert matched_pattern not in result.stderr


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is required")
def test_maintenance_encrypts_rules_and_runtime_preserves_regex_behavior(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    guard_script = repository_root / "tools" / "deny-dangerous.ps1"
    plaintext_file = tmp_path / "caller-rules.txt"
    protected_file = tmp_path / "rules.dpapi"
    plaintext_rules = r"rm\s+-rf\s+/" + "\n"
    plaintext_file.write_text(plaintext_rules, encoding="utf-8")

    encrypted = _run_guard(
        guard_script,
        "-Maintenance",
        "-PlaintextPatternsFile",
        str(plaintext_file),
        "-PatternsFile",
        str(protected_file),
    )

    assert encrypted.returncode == 0, encrypted.stderr
    assert plaintext_file.read_text(encoding="utf-8") == plaintext_rules
    assert protected_file.read_bytes() != plaintext_file.read_bytes()
    assert b"rm\\s+-rf\\s+/" not in protected_file.read_bytes()

    blocked = _run_guard(
        guard_script,
        "-Command",
        "RM -RF /",
        "-PatternsFile",
        str(protected_file),
    )
    allowed = _run_guard(
        guard_script,
        "-Command",
        "rm -rf ./build",
        "-PatternsFile",
        str(protected_file),
    )

    assert blocked.returncode == 2
    assert allowed.returncode == 0


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is required")
def test_maintenance_refuses_overwrite_without_explicit_override(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    guard_script = repository_root / "tools" / "deny-dangerous.ps1"
    plaintext_file = tmp_path / "caller-rules.txt"
    protected_file = tmp_path / "rules.dpapi"
    original_protected_bytes = b"existing-protected-rules"
    plaintext_file.write_text("blocked-command\n", encoding="utf-8")
    protected_file.write_bytes(original_protected_bytes)

    refused = _run_guard(
        guard_script,
        "-Maintenance",
        "-PlaintextPatternsFile",
        str(plaintext_file),
        "-PatternsFile",
        str(protected_file),
    )

    assert refused.returncode != 0
    assert protected_file.read_bytes() == original_protected_bytes

    replaced = _run_guard(
        guard_script,
        "-Maintenance",
        "-PlaintextPatternsFile",
        str(plaintext_file),
        "-PatternsFile",
        str(protected_file),
        "-Overwrite",
    )
    blocked = _run_guard(
        guard_script,
        "-Command",
        "blocked-command",
        "-PatternsFile",
        str(protected_file),
    )

    assert replaced.returncode == 0, replaced.stderr
    assert protected_file.read_bytes() != original_protected_bytes
    assert blocked.returncode == 2


@pytest.mark.parametrize("corrupt", [False, True], ids=["missing", "corrupt"])
@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is required")
def test_unavailable_protected_rules_allow_with_only_generic_warning(
    tmp_path: Path, corrupt: bool
) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    guard_script = repository_root / "tools" / "deny-dangerous.ps1"
    protected_file = tmp_path / "rules.dpapi"
    if corrupt:
        protected_file.write_bytes(b"private-corrupt-rule-details")

    result = _run_guard(
        guard_script,
        "-Command",
        "rm -rf /",
        "-PatternsFile",
        str(protected_file),
    )

    assert result.returncode == 0
    assert result.stderr.strip() == "Command guard rules unavailable; allowing command."


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell 7 is required")
def test_runtime_does_not_fall_back_to_plaintext_default_rules(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    guard_script = tmp_path / "deny-dangerous.ps1"
    shutil.copy2(repository_root / "tools" / "deny-dangerous.ps1", guard_script)
    (tmp_path / "dangerous-patterns.txt").write_text("rm\\s+-rf\\s+/\n", encoding="utf-8")

    result = _run_guard(guard_script, "-Command", "rm -rf /")

    assert result.returncode == 0
    assert result.stderr.strip() == "Command guard rules unavailable; allowing command."