#!/usr/bin/env python3
"""
⊕ Nightly Security Scanner — runs bandit + safety across all 5 project roots,
diffs new findings against the vulnerabilities table in workspace.db, and
auto-writes new vulns. Logs a scan_run_log row and appends to
logs/security_nightly.log per run.

Usage (manual):
    C:/G/python.exe f:/⊕Workspace/src/utils/security_scan_nightly.py

Scheduled nightly at 02:30 by tools/register_nightly_scan.ps1.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ──────────────────────────────────────────────────────────────────────
WORKSPACE_ROOT = Path("f:/")
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR.parent.parent / "logs" / "security_nightly.log"

PROJECT_ROOTS: list[Path] = [
    WORKSPACE_ROOT / "\u221eLife",
    WORKSPACE_ROOT / "\u2764Music",
    WORKSPACE_ROOT / "\u27e8\u03c8\u27e9Quantum",
    WORKSPACE_ROOT / "\U0001f441AI-Manifest",
    WORKSPACE_ROOT / "\u2295Workspace",
]

PYTHON = sys.executable


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _vuln_id(project: str, file_path: str, line: int, rule_id: str) -> str:
    """Stable dedup key: first 16 hex chars of sha256(project:file:line:rule)."""
    raw = f"{project}:{file_path}:{line}:{rule_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _log(msg: str, *, also_print: bool = True) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{_now_iso()}] {msg}"
    if also_print:
        print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ── Bandit ─────────────────────────────────────────────────────────────────────

def run_bandit(project: Path) -> tuple[list[dict[str, Any]], int]:
    """Run bandit on project/src (or project root). Returns (findings, exit_code)."""
    scan_target = project / "src" if (project / "src").exists() else project
    cmd = [PYTHON, "-m", "bandit", "-r", str(scan_target), "-f", "json", "--quiet"]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if not result.stdout.strip():
        return [], result.returncode

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        _log(f"  bandit JSON parse error for {project.name}: {result.stdout[:200]}")
        return [], 1

    sev_map = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    findings: list[dict[str, Any]] = []
    for issue in data.get("results", []):
        findings.append({
            "project": project.name,
            "file_path": issue.get("filename", ""),
            "line_number": issue.get("line_number", 0),
            "rule_id": issue.get("test_id", ""),
            "description": f"{issue.get('test_id', '')}: {issue.get('issue_text', '')}",
            "severity": sev_map.get(issue.get("issue_severity", "LOW"), "low"),
            "owasp_id": "A03:2021",
        })
    return findings, result.returncode


# ── Safety ─────────────────────────────────────────────────────────────────────

def run_safety(project: Path) -> tuple[list[dict[str, Any]], int]:
    """Run safety on project/requirements.txt. Returns (findings, exit_code)."""
    req_file = project / "requirements.txt"
    if not req_file.exists():
        return [], 0

    # Try safety 3.x first, then fall back to 2.x CLI syntax.
    candidates = [
        [PYTHON, "-m", "safety", "scan", "--file", str(req_file), "--output", "json", "--no-telemetry"],
        [PYTHON, "-m", "safety", "check", "-r", str(req_file), "--json"],
    ]
    for cmd in candidates:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        stdout = result.stdout.strip()
        if not stdout:
            continue
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            continue

        # safety 3.x: {"vulnerabilities": [...]}  /  2.x: [[pkg, specs, ver, advisory, id], ...]
        raw_vulns = (
            data.get("vulnerabilities")
            if isinstance(data, dict)
            else data
            if isinstance(data, list)
            else []
        )
        findings: list[dict[str, Any]] = []
        for v in raw_vulns:
            if isinstance(v, dict):
                cve = v.get("CVE") or v.get("vulnerability_id") or v.get("id", "")
                pkg = v.get("package_name") or v.get("package", "")
                desc = v.get("advisory") or v.get("more_info_url") or f"CVE {cve}"
            elif isinstance(v, list) and len(v) >= 5:
                pkg, _specs, _ver, desc, cve = v[0], v[1], v[2], v[3], str(v[4])
            else:
                continue
            findings.append({
                "project": project.name,
                "file_path": str(req_file).replace("\\", "/"),
                "line_number": 0,
                "rule_id": cve or "safety",
                "description": f"{pkg}: {desc}",
                "severity": "high",
                "owasp_id": "A06:2021",
            })
        return findings, result.returncode

    return [], 0


# ── DB writes ──────────────────────────────────────────────────────────────────

def _get_db_conn():
    sys.path.insert(0, str(SCRIPT_DIR))
    from init_db import get_connection, init_db  # noqa: PLC0415
    init_db()
    return get_connection()


def insert_new_vulns(conn: Any, findings: list[dict[str, Any]]) -> int:
    """Insert findings absent from vulnerabilities table. Returns inserted count."""
    inserted = 0
    scan_date = _now_iso()[:10]
    for f in findings:
        vid = _vuln_id(f["project"], f["file_path"], f["line_number"], f["rule_id"])
        if conn.execute(
            "SELECT 1 FROM vulnerabilities WHERE vuln_id=?", (vid,)
        ).fetchone():
            continue
        conn.execute(
            """INSERT INTO vulnerabilities
               (vuln_id, scan_date, category, severity, file_path, line_number,
                description, owasp_id, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))""",
            (
                vid, scan_date, "OWASP",
                f["severity"], f["file_path"], f["line_number"],
                f["description"], f.get("owasp_id", ""),
                "open",
            ),
        )
        inserted += 1
    conn.commit()
    return inserted


def write_scan_run_log(
    conn: Any,
    run_id: str,
    started_at: str,
    projects: list[str],
    new_vulns: int,
    total_findings: int,
    bandit_rc: int,
    safety_rc: int,
    status: str,
    error_detail: str | None,
) -> None:
    conn.execute(
        """INSERT INTO scan_run_log
           (run_id, started_at, completed_at, projects_scanned, new_vulns_count,
            total_findings, bandit_exit_code, safety_exit_code, status, error_detail)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id, started_at, _now_iso(),
            json.dumps(projects),
            new_vulns, total_findings,
            bandit_rc, safety_rc,
            status, error_detail,
        ),
    )
    conn.commit()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    run_id = str(uuid.uuid4())
    started_at = _now_iso()
    _log(f"=== Nightly Security Scan START run={run_id} ===")

    all_findings: list[dict[str, Any]] = []
    project_names: list[str] = []
    bandit_rc_max = 0
    safety_rc_max = 0
    error_parts: list[str] = []

    for project in PROJECT_ROOTS:
        if not project.exists():
            _log(f"  [SKIP] {project.name} — root not found")
            continue

        _log(f"  [bandit] {project.name} ...")
        try:
            b_findings, b_rc = run_bandit(project)
        except Exception as exc:
            _log(f"  [bandit] ERROR {project.name}: {exc}")
            b_findings, b_rc = [], 1
            error_parts.append(f"bandit/{project.name}: {exc}")

        _log(f"  [safety] {project.name} ...")
        try:
            s_findings, s_rc = run_safety(project)
        except Exception as exc:
            _log(f"  [safety] ERROR {project.name}: {exc}")
            s_findings, s_rc = [], 1
            error_parts.append(f"safety/{project.name}: {exc}")

        _log(
            f"    bandit={len(b_findings)} findings rc={b_rc},"
            f" safety={len(s_findings)} findings rc={s_rc}"
        )
        all_findings.extend(b_findings)
        all_findings.extend(s_findings)
        project_names.append(project.name)
        bandit_rc_max = max(bandit_rc_max, b_rc)
        safety_rc_max = max(safety_rc_max, s_rc)

    try:
        conn = _get_db_conn()
        new_count = insert_new_vulns(conn, all_findings)
        write_scan_run_log(
            conn, run_id, started_at, project_names,
            new_count, len(all_findings),
            bandit_rc_max, safety_rc_max,
            "error" if error_parts else "ok",
            "; ".join(error_parts) or None,
        )
        conn.close()
    except Exception as exc:
        _log(f"  [DB] ERROR writing results: {exc}")
        return 1

    _log(
        f"=== Nightly Security Scan END:"
        f" {new_count} new vulns written, {len(all_findings)} total findings ==="
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
