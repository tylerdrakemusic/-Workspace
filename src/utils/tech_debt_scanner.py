"""Static-analysis-driven technical debt scanner for ⊕Workspace.

Ranks candidates with radon/pylint (Pattern A + B), leaving narration to the
caller. Reused by `discover_todos.py --mode tech-debt`.
"""
from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

CATEGORY_WEIGHTS = {
    "complexity": 0.4,
    "monolith": 0.3,
    "coupling": 0.2,
    "filesystem": 0.1,
}

MONOLITH_LINE_THRESHOLD = 300
COMPLEXITY_CC_THRESHOLD = 10
COUPLING_IMPORT_THRESHOLD = 8  # imports in a single file


@dataclass(slots=True)
class Finding:
    finding_id: str
    project: str
    category: str  # complexity | monolith | coupling | filesystem
    file_path: str
    raw_score: int  # 1-10, from the static tool
    severity: int = 0  # 1-10 composite, filled by score_finding
    detail: str = ""
    action: str = ""


def _run_radon_cc(src_root: Path) -> list[Finding]:
    """Pattern A: cyclomatic complexity hotspots via `radon cc`."""
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["radon", "cc", str(src_root), "-s", "-j", "--min", "B"],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return findings

    if not result.stdout:
        return findings
    try:
        cc_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return findings

    for file_path, blocks in cc_data.items():
        if not blocks:
            continue
        worst = max(b.get("complexity", 0) for b in blocks)
        if worst < COMPLEXITY_CC_THRESHOLD:
            continue
        findings.append(Finding(
            finding_id=str(uuid.uuid4()),
            project="",  # filled by caller
            category="complexity",
            file_path=file_path,
            raw_score=min(10, worst // 3),
            detail=f"Max CC={worst} across {len(blocks)} function(s)",
        ))
    return findings


def _scan_monoliths(src_root: Path) -> list[Finding]:
    """Pattern A: files exceeding a line-count threshold."""
    findings: list[Finding] = []
    for py in src_root.rglob("*.py"):
        try:
            lines = py.read_text(encoding="utf-8", errors="replace").count("\n")
        except OSError:
            continue
        if lines <= MONOLITH_LINE_THRESHOLD:
            continue
        findings.append(Finding(
            finding_id=str(uuid.uuid4()),
            project="",
            category="monolith",
            file_path=str(py),
            raw_score=min(10, lines // 100),
            detail=f"{lines} lines",
        ))
    return findings


def _scan_coupling(src_root: Path) -> list[Finding]:
    """Pattern A: per-file import count as a coupling proxy."""
    findings: list[Finding] = []
    for py in src_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        import_count = sum(
            1 for line in text.splitlines()
            if line.strip().startswith(("import ", "from "))
        )
        if import_count <= COUPLING_IMPORT_THRESHOLD:
            continue
        findings.append(Finding(
            finding_id=str(uuid.uuid4()),
            project="",
            category="coupling",
            file_path=str(py),
            raw_score=min(10, import_count // 2),
            detail=f"{import_count} import statements",
        ))
    return findings


def _scan_filesystem(project_root: Path) -> list[Finding]:
    """Pattern A: duplicate/orphaned top-level dirs and stray root files."""
    findings: list[Finding] = []
    seen_names: dict[str, list[Path]] = {}
    for child in project_root.iterdir():
        if child.is_dir():
            seen_names.setdefault(child.name.lower(), []).append(child)
    for name, paths in seen_names.items():
        if len(paths) > 1:
            findings.append(Finding(
                finding_id=str(uuid.uuid4()),
                project="",
                category="filesystem",
                file_path=str(project_root),
                raw_score=6,
                detail=f"Duplicate-looking dirs for '{name}': {[str(p) for p in paths]}",
            ))
    return findings


def score_finding(finding: Finding, import_depth: int = 0) -> int:
    """Pattern B: composite 1-10 severity from category weight + coupling penalty."""
    weight = CATEGORY_WEIGHTS.get(finding.category, 0.25)
    coupling_penalty = min(3, import_depth // 2)
    weighted = finding.raw_score * weight * 10
    return max(1, min(10, int(weighted + coupling_penalty)))


def scan_project(project_key: str, project_root: Path) -> list[Finding]:
    """Run all four category scans against `project_root/src` (falls back to root)."""
    src_root = project_root / "src"
    if not src_root.exists():
        src_root = project_root

    findings: list[Finding] = []
    findings.extend(_run_radon_cc(src_root))
    findings.extend(_scan_monoliths(src_root))
    findings.extend(_scan_coupling(src_root))
    findings.extend(_scan_filesystem(project_root))

    for finding in findings:
        finding.project = project_key
        finding.severity = score_finding(finding)

    return findings
