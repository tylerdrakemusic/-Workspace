#!/usr/bin/env python3
"""
health_data_audit.py — ∞Life pre-commit health data guard
FR-20260513-hooks-setup
Blocks accidental staging of sensitive health/genomic data in the ∞Life repo.
Only invoked when running in the ∞Life repository.
"""
import re
import subprocess
import sys

# Patterns that must never be committed in ∞Life
BLOCKED_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("SQLite database file",   re.compile(r'\.db(-wal|-shm)?$')),
    ("Subject profile",        re.compile(r'SUBJECT_PROFILE\.json$')),
    ("Bloodwork data",         re.compile(r'data[/\\]bloodwork[/\\]')),
    ("Medical records",        re.compile(r'data[/\\]medical_records[/\\]')),
    ("Genomics data",          re.compile(r'data[/\\]genomics[/\\]')),
    ("Baseline data",          re.compile(r'data[/\\]baseline[/\\]')),
    ("Biomarkers data",        re.compile(r'data[/\\]biomarkers[/\\]')),
    ("Log files",              re.compile(r'^logs[/\\]')),
    ("Temp files",             re.compile(r'^tmp[/\\]')),
    ("Private key / cert",     re.compile(r'\.(key|pem|p12|pfx)$')),
]


def main() -> int:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print(f"[health_data_audit] git diff failed: {result.stderr}", file=sys.stderr)
        return 1

    staged = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    violations: list[tuple[str, str]] = []

    for filepath in staged:
        for reason, pattern in BLOCKED_PATTERNS:
            if pattern.search(filepath):
                violations.append((filepath, reason))
                break

    if violations:
        print("")
        print("❌ pre-commit [health-data-audit]: sensitive ∞Life data must never be committed.")
        print("   Add these paths to .gitignore and unstage them.")
        print("")
        for filepath, reason in violations:
            print(f"   {filepath}  ({reason})")
        print("")
        print("   Run: git restore --staged <file>  to unstage.")
        print("   To bypass (only if confirmed safe): git commit --no-verify")
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
