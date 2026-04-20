# Workspace OWASP vulnerability + secret scanner.
# Scans Python source files across all three projects.
# Usage: C:\G\python.exe scan_vulnerabilities.py [--project all|infinitelife|heartmusic|quantum]
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field

PROJECT_ROOTS = {
    "infinitelife": Path(r"f:\executedcode\∞Life\src"),
    "heartmusic":   Path(r"f:\executedcode\❤Music\src"),
    "quantum":      Path(r"f:\executedcode\⟨ψ⟩Quantum\src"),
}

RULES: list[tuple[str, str, str]] = [
    # (category, severity, pattern)
    ("A03-Injection",          "HIGH",   r"execute\s*\(\s*[f\"'].*\{|execute\s*\(\s*\".*%|execute\s*\(\s*'.*%"),
    ("A03-Injection",          "HIGH",   r"\beval\s*\(|\bexec\s*\("),
    ("A03-Injection",          "HIGH",   r"shell\s*=\s*True"),
    ("A02-CryptoFailure",      "MEDIUM", r"hashlib\.(md5|sha1)\s*\("),
    ("A02-CryptoFailure",      "MEDIUM", r"http://(?!localhost|127\.0\.0\.1)"),
    ("A04-InsecureDesign",     "HIGH",   r"(?i)(api_key|password|secret|token|ibm_token|hf_token)\s*=\s*[\"'][^\"']{8,}[\"']"),
    ("A08-DataIntegrity",      "HIGH",   r"pickle\.loads?\s*\("),
    ("A09-LoggingFailure",     "MEDIUM", r"(?i)(password|token|secret|api_key).*\blog(ging)?\b|\blog(ging)?\b.*(password|token|secret|api_key)"),
    ("A10-SSRF",               "MEDIUM", r"requests\.(get|post|put|delete)\s*\(\s*[^\"'\s]"),
]

SECRET_PATTERNS = [
    re.compile(r"(?i)(ibm_quantum|ibm_token)\s*=\s*[\"'][^\"']{8,}[\"']"),
    re.compile(r"(?i)hf_token\s*=\s*[\"'][A-Za-z0-9_\-]{20,}[\"']"),
    re.compile(r"(?i)(api_key|apikey)\s*=\s*[\"'][^\"']{8,}[\"']"),
]

compiled_rules = [
    (cat, sev, re.compile(pat))
    for cat, sev, pat in RULES
]


@dataclass
class Finding:
    project: str
    file: str
    line: int
    category: str
    severity: str
    snippet: str


def scan_file(path: Path, project: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return findings
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # skip comments
        for cat, sev, pattern in compiled_rules:
            if pattern.search(line):
                findings.append(Finding(
                    project=project,
                    file=str(path),
                    line=lineno,
                    category=cat,
                    severity=sev,
                    snippet=stripped[:120],
                ))
    return findings


def scan_project(name: str, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not root.exists():
        return findings
    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        findings.extend(scan_file(py_file, name))
    return findings


def severity_rank(s: str) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(s, 0)


def main() -> None:
    project_filter = "all"
    for arg in sys.argv[1:]:
        if arg.startswith("--project="):
            project_filter = arg.split("=", 1)[1]

    projects = PROJECT_ROOTS if project_filter == "all" else {
        k: v for k, v in PROJECT_ROOTS.items() if k == project_filter
    }

    all_findings: list[Finding] = []
    for name, root in projects.items():
        all_findings.extend(scan_project(name, root))

    all_findings.sort(key=lambda f: (-severity_rank(f.severity), f.project, f.file, f.line))

    print("=" * 72)
    print("  WORKSPACE VULNERABILITY SCAN REPORT")
    print("=" * 72)

    if not all_findings:
        print("  ✅ No vulnerabilities found.")
    else:
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in all_findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(f.severity, "⚪")
            rel = Path(f.file).name
            print(f"  {icon} [{f.severity:8s}] [{f.category:20s}] {f.project}/{rel}:{f.line}")
            print(f"         {f.snippet[:90]}")
        print("-" * 72)
        print(f"  TOTALS — CRITICAL:{counts['CRITICAL']}  HIGH:{counts['HIGH']}  MEDIUM:{counts['MEDIUM']}  LOW:{counts['LOW']}")

    risk = "LOW"
    if any(f.severity == "CRITICAL" for f in all_findings):
        risk = "CRITICAL"
    elif any(f.severity == "HIGH" for f in all_findings):
        risk = "HIGH"
    elif any(f.severity == "MEDIUM" for f in all_findings):
        risk = "MEDIUM"

    print(f"  RISK LEVEL: {risk}")
    print("=" * 72)

    out = {
        "scanned_projects": list(projects.keys()),
        "total_findings": len(all_findings),
        "risk_level": risk,
        "findings": [
            {"project": f.project, "file": f.file, "line": f.line,
             "category": f.category, "severity": f.severity, "snippet": f.snippet}
            for f in all_findings
        ],
    }
    out_path = Path(r"f:\tmp\security_scan_results.json")
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Full results: {out_path}")


if __name__ == "__main__":
    main()
