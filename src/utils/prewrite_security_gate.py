"""Run the canonical agent and external-skill integrity gate before cross-project writes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_VERIFIER_COMPLETE_MARKER = "=== Agent File Integrity Check ==="
_SOURCE_DRIFT_MARKER = "SOURCE DRIFT (approval required)"


def run_prewrite_security_gate(repo_root: Path) -> int:
    """Return 1 for confirmed integrity findings, otherwise allow with operational warnings."""
    verifier = repo_root / ".github" / "!!☾⛧security" / "update_manifest.py"
    try:
        result = subprocess.run(
            [sys.executable, str(verifier), "--verify"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=30,
        )
    except OSError as error:
        print(
            f"WARNING: integrity verifier could not start; allowing write: {error}",
            file=sys.stderr,
        )
        return 0
    except subprocess.TimeoutExpired:
        print(
            "WARNING: integrity verifier timed out; allowing write",
            file=sys.stderr,
        )
        return 0

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    verifier_completed = _VERIFIER_COMPLETE_MARKER in result.stdout
    confirmed_source_drift = _SOURCE_DRIFT_MARKER in result.stdout
    if confirmed_source_drift or (verifier_completed and result.returncode == 2):
        print(
            "BLOCKED: canonical integrity verification found an unapproved mismatch.",
            file=sys.stderr,
        )
        return 1

    if not verifier_completed or result.returncode != 0:
        print(
            "WARNING: canonical integrity verification did not complete cleanly; allowing write",
            file=sys.stderr,
        )
        return 0

    print("INTEGRITY_OK: canonical verifier passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the cross-project pre-write integrity gate")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    args = parser.parse_args()
    return run_prewrite_security_gate(args.repo_root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
