#!/usr/bin/env python3
"""
secret_scan.py — staged-diff secret scanner
FR-20260513-hooks-setup
Scans only added lines (+) in staged diffs for known secret patterns.
"""
import re
import subprocess
import sys

# Pattern registry: (name, compiled_regex)
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("OpenAI key",              re.compile(r'sk-[A-Za-z0-9]{20,}')),
    ("GitHub PAT (ghp)",        re.compile(r'ghp_[A-Za-z0-9]{36}')),
    ("GitHub OAuth",            re.compile(r'gho_[A-Za-z0-9]{36}')),
    ("GitHub fine-grained PAT", re.compile(r'github_pat_[A-Za-z0-9_]{82}')),
    ("JWT token",               re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')),
    ("AWS access key ID",       re.compile(r'AKIA[0-9A-Z]{16}')),
    ("AWS secret key",          re.compile(r'(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[=:]\s*[A-Za-z0-9/+=]{40}')),
    ("ElevenLabs key",          re.compile(r'(?i)elevenlabs[_\-]?api[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}')),
    ("Qiskit/IBM token",        re.compile(r'(?i)qiskit[_\-]?token\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}')),
    ("Generic API key/secret",  re.compile(r'(?i)(api[_\-]?key|api[_\-]?secret|access[_\-]?token|auth[_\-]?token|secret[_\-]?key)\s*[=:]\s*["\']?[A-Za-z0-9_\-\.]{16,}["\']?')),
    ("Workspace env var with value", re.compile(
        r'(?i)(OPENAPI_TOKEN|QISKIT_TOKEN|GOOGLE_API_KEY|HF_TOKEN|FACEBOOK_USER_TOKEN|FACEBOOK_APP_TOKEN|ELEVENLABS_API_KEY|WORKSPACE_DB_KEY|INFINITELIFE_DB_KEY|HEARTMUSIC_DB_KEY|QUANTUM_DB_KEY)\s*[=]\s*["\']?[A-Za-z0-9_\-\.]{8,}["\']?'
    )),
]

SKIP_PATH_PATTERNS = re.compile(r'(test_|fixture|\.example|sample|\.env\.example)', re.IGNORECASE)


def redact(value: str) -> str:
    return value[:4] + "..." if len(value) > 4 else "****"


def main() -> int:
    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print(f"[secret_scan] git diff failed: {result.stderr}", file=sys.stderr)
        return 1

    diff = result.stdout
    violations: list[str] = []
    current_file = "<unknown>"

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            # Extract filename: "diff --git a/path b/path" → "path"
            parts = line.split(" b/", 1)
            current_file = parts[1] if len(parts) > 1 else "<unknown>"
        elif line.startswith("+++"):
            fname = line[4:].strip()
            if fname != "/dev/null":
                current_file = fname.lstrip("b/")
        elif line.startswith("+") and not line.startswith("+++"):
            if SKIP_PATH_PATTERNS.search(current_file):
                continue
            added_line = line[1:]  # strip leading +
            for name, pattern in PATTERNS:
                m = pattern.search(added_line)
                if m:
                    violations.append(
                        f"  [{name}] in {current_file}: ...{redact(m.group(0))}..."
                    )

    if violations:
        print("")
        print("❌ pre-commit [secret-scan]: potential secrets detected in staged changes.")
        print("   Review and remove before committing. Use env vars instead of hardcoded values.")
        for v in violations:
            print(v)
        print("")
        print("   To bypass (only if false positive): git commit --no-verify")
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
