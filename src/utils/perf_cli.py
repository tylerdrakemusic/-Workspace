"""
perf_cli.py — Agent performance tracking CLI for ⊕Workspace.

Wraps perf_runs / perf_steps tables in workspace.db (SQLCipher).
Designed for minimal terminal calls: start once, end+report once.

Usage:
    python perf_cli.py start "<run-name>"        → prints run_id
    python perf_cli.py end <run_id> --status ok --detail "<summary>"
    python perf_cli.py report <run_id>
    python perf_cli.py list                       → last 20 runs
"""
import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_db import get_connection, init_db


def _conn():
    init_db()
    return get_connection()


def cmd_start(name: str) -> None:
    run_id = str(uuid.uuid4())
    conn = _conn()
    conn.execute(
        "INSERT INTO perf_runs (run_id, name, started_at) VALUES (?, ?, ?)",
        (run_id, name, time.time()),
    )
    conn.commit()
    conn.close()
    print(run_id)


def cmd_end(run_id: str, status: str, detail: str) -> None:
    conn = _conn()
    row = conn.execute("SELECT started_at FROM perf_runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        print(f"[perf_cli] run_id not found: {run_id}", file=sys.stderr)
        sys.exit(1)
    elapsed_ms = (time.time() - row[0]) * 1000
    conn.execute(
        "UPDATE perf_runs SET ended_at=?, status=?, detail=? WHERE run_id=?",
        (time.time(), status, detail, run_id),
    )
    conn.commit()
    conn.close()
    print(f"[perf_cli] run closed — {elapsed_ms:,.0f}ms — {status}")


def cmd_report(run_id: str) -> None:
    conn = _conn()
    run = conn.execute(
        "SELECT name, started_at, ended_at, status, detail FROM perf_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if not run:
        print(f"[perf_cli] run_id not found: {run_id}", file=sys.stderr)
        sys.exit(1)
    name, started, ended, status, detail = run
    elapsed = ((ended or time.time()) - started) * 1000
    steps = conn.execute(
        "SELECT agent, description, elapsed_ms, status, detail FROM perf_steps WHERE run_id = ? ORDER BY started_at",
        (run_id,),
    ).fetchall()
    conn.close()

    bar = "=" * 64
    print(f"\n{bar}")
    print(f"  PERF REPORT: {name}")
    print(bar)
    if steps:
        for agent, desc, ms, st, det in steps:
            icon = "+" if st == "ok" else ("!" if st == "error" else "-")
            ms_str = f"{ms:>10,.0f}ms" if ms else "        —"
            print(f"  {icon} [{ms_str}]  {agent or '':<28}  {desc or ''}")
            if det:
                print(f"             {' ':<28}  -> {det[:80]}")
    print(f"{'-' * 64}")
    print(f"  WALL-CLOCK: {elapsed:,.0f}ms  ({elapsed/1000:.1f}s)")
    print(f"  STATUS:     {status or 'open'}")
    if detail:
        print(f"  DETAIL:     {detail}")
    print(f"{bar}\n")


def cmd_list() -> None:
    conn = _conn()
    rows = conn.execute(
        """SELECT name, run_id, started_at,
                  ROUND((COALESCE(ended_at, started_at) - started_at) * 1000) as ms,
                  status, detail
           FROM perf_runs ORDER BY started_at DESC LIMIT 20"""
    ).fetchall()
    conn.close()
    if not rows:
        print("[perf_cli] no runs on record")
        return
    print(f"\n{'Name':<40} {'ms':>8}  {'Status':<10}  Detail")
    print("-" * 80)
    for name, run_id, _, ms, status, detail in rows:
        detail_short = (detail or "")[:40]
        print(f"  {name:<38} {(ms or 0):>8,.0f}  {(status or 'open'):<10}  {detail_short}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="⊕Workspace perf CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_start = sub.add_parser("start")
    p_start.add_argument("name")

    p_end = sub.add_parser("end")
    p_end.add_argument("run_id")
    p_end.add_argument("--status", default="ok", choices=["ok", "error", "timeout"])
    p_end.add_argument("--detail", default="")

    p_rep = sub.add_parser("report")
    p_rep.add_argument("run_id")

    sub.add_parser("list")

    args = parser.parse_args()

    if args.cmd == "start":
        cmd_start(args.name)
    elif args.cmd == "end":
        cmd_end(args.run_id, args.status, args.detail)
    elif args.cmd == "report":
        cmd_report(args.run_id)
    elif args.cmd == "list":
        cmd_list()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
