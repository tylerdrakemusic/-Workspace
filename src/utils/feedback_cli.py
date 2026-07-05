"""
feedback_cli.py — Agent/prompt feedback capture CLI for ⊕Workspace.

Wraps the agent_feedback table in workspace.db (SQLCipher).
Mirrors the fr_cli / perf_cli conventions agents already know.

Usage:
    python feedback_cli.py log <agent_name> <artifact_type> <target_file> <finding_text> <severity> [--fr-id <id>]
    python feedback_cli.py list [--status <status>] [--severity <severity>]
    python feedback_cli.py apply <id> [--applied-by <name>]
    python feedback_cli.py auto-apply-trivial
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_db import get_connection, init_db

ARTIFACT_TYPES = {"agent", "instructions", "prompt", "skill", "reference"}
SEVERITIES = {"trivial", "substantive"}
STATUSES = {"pending", "auto_applied", "approved", "rejected", "applied"}


def _conn():
    init_db()
    return get_connection()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_log(args: argparse.Namespace) -> None:
    """Insert a pending agent_feedback row."""
    if args.artifact_type not in ARTIFACT_TYPES:
        print(f"[feedback_cli] invalid artifact_type: {args.artifact_type} (must be one of {sorted(ARTIFACT_TYPES)})", file=sys.stderr)
        sys.exit(1)
    if args.severity not in SEVERITIES:
        print(f"[feedback_cli] invalid severity: {args.severity} (must be one of {sorted(SEVERITIES)})", file=sys.stderr)
        sys.exit(1)
    conn = _conn()
    cur = conn.execute(
        """INSERT INTO agent_feedback
           (timestamp, agent_or_prompt_name, artifact_type, target_file_path,
            finding_text, severity, status, fr_id)
           VALUES (?,?,?,?,?,?,'pending',?)""",
        (_now(), args.agent_name, args.artifact_type, args.target_file,
         args.finding_text, args.severity, getattr(args, "fr_id", None)),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    print(f"[feedback_cli] feedback logged → id={row_id}")


def cmd_list(args: argparse.Namespace) -> None:
    """List agent_feedback rows, optionally filtered by status/severity."""
    conn = _conn()
    where_parts: list[str] = []
    params: list[str] = []
    if getattr(args, "status", None):
        where_parts.append("status=?")
        params.append(args.status)
    if getattr(args, "severity", None):
        where_parts.append("severity=?")
        params.append(args.severity)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    rows = conn.execute(
        f"SELECT id, timestamp, agent_or_prompt_name, artifact_type, target_file_path, "  # nosec B608
        f"finding_text, severity, status, fr_id FROM agent_feedback {where} ORDER BY id DESC LIMIT 100",
        params,
    ).fetchall()
    conn.close()
    if not rows:
        print("[feedback_cli] no feedback found")
        return
    for r in rows:
        print(
            f"{r['id']:>5}  {r['timestamp']}  {r['severity']:<11}  {r['status']:<12}  "
            f"{r['agent_or_prompt_name']:<28}  {r['target_file_path']}  — {r['finding_text'][:60]}"
        )


def cmd_apply(args: argparse.Namespace) -> None:
    """Mark a feedback row applied, recording applied_at/applied_by."""
    conn = _conn()
    row = conn.execute("SELECT id FROM agent_feedback WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"[feedback_cli] feedback id not found: {args.id}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    conn.execute(
        "UPDATE agent_feedback SET status='applied', applied_at=?, applied_by=? WHERE id=?",
        (_now(), getattr(args, "applied_by", None), args.id),
    )
    conn.commit()
    conn.close()
    print(f"[feedback_cli] feedback applied → id={args.id}")


def cmd_auto_apply_trivial(args: argparse.Namespace) -> None:
    """Bulk-mark all severity=trivial, status=pending rows as auto_applied."""
    conn = _conn()
    cur = conn.execute(
        "UPDATE agent_feedback SET status='auto_applied' WHERE severity='trivial' AND status='pending'"
    )
    conn.commit()
    count = cur.rowcount
    conn.close()
    print(f"[feedback_cli] auto-applied {count} trivial finding(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="⊕Workspace agent feedback CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_log = sub.add_parser("log", help="Log a new feedback finding")
    p_log.add_argument("agent_name")
    p_log.add_argument("artifact_type", choices=sorted(ARTIFACT_TYPES))
    p_log.add_argument("target_file")
    p_log.add_argument("finding_text")
    p_log.add_argument("severity", choices=sorted(SEVERITIES))
    p_log.add_argument("--fr-id", dest="fr_id", default=None)

    p_list = sub.add_parser("list", help="List feedback rows")
    p_list.add_argument("--status", default=None, choices=sorted(STATUSES))
    p_list.add_argument("--severity", default=None, choices=sorted(SEVERITIES))

    p_apply = sub.add_parser("apply", help="Mark a feedback row applied")
    p_apply.add_argument("id", type=int)
    p_apply.add_argument("--applied-by", dest="applied_by", default=None)

    sub.add_parser("auto-apply-trivial", help="Auto-apply all pending trivial findings")

    args = parser.parse_args()

    if args.cmd == "log":
        cmd_log(args)
    elif args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "apply":
        cmd_apply(args)
    elif args.cmd == "auto-apply-trivial":
        cmd_auto_apply_trivial(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
