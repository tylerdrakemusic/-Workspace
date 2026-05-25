"""
⊕ Proof-in-the-Pudding CLI — agent proof artifact recorder and verifier.

Agents call this at lifecycle boundaries to record concrete evidence of work done.
Proofs link to perf_runs via run_id, creating an auditable chain:
  perf_run → proof_artifacts → verified files/DB writes/outputs.

Usage:
    python proof_cli.py record <run_id> <agent> <proof_type> <description> [--path FILE] [--hash HASH]
    python proof_cli.py verify <run_id>           # verify all proofs for a run
    python proof_cli.py verify --all              # verify all unverified proofs
    python proof_cli.py report <run_id>           # proof report for a single run
    python proof_cli.py report --all              # full proof audit report
    python proof_cli.py summary                   # agent proof coverage summary
"""

import argparse
import hashlib
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from init_db import get_connection, init_db

PROOF_TYPES = [
    "file_created", "file_modified", "db_write", "command_output",
    "metric", "screenshot", "dashboard", "test_pass",
    "perf_regression_alert", "perf_low_data",
]


def _connect():
    init_db()
    return get_connection()


def _hash_file(path: str) -> str | None:
    """SHA-256 of file contents, or None if missing."""
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Commands ───────────────────────────────────────────────────

def cmd_record(args) -> None:
    conn = _connect()
    proof_id = uuid.uuid4().hex[:12]

    artifact_hash = args.hash
    if not artifact_hash and args.path:
        artifact_hash = _hash_file(args.path)

    conn.execute(
        """INSERT INTO proof_artifacts
           (proof_id, run_id, agent, proof_type, description, artifact_path, artifact_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (proof_id, args.run_id, args.agent, args.proof_type,
         args.description, args.path, artifact_hash),
    )
    conn.commit()
    conn.close()
    print(proof_id)


def cmd_verify(args) -> None:
    conn = _connect()

    if args.all:
        rows = conn.execute(
            "SELECT proof_id, artifact_path, artifact_hash, proof_type FROM proof_artifacts WHERE verified = 0"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT proof_id, artifact_path, artifact_hash, proof_type FROM proof_artifacts WHERE run_id = ?",
            (args.run_id,),
        ).fetchall()

    verified = 0
    failed = 0
    skipped = 0

    for row in rows:
        pid = row["proof_id"]
        ptype = row["proof_type"]
        path = row["artifact_path"]
        stored_hash = row["artifact_hash"]

        # Types without file paths are verified by existence in DB
        if ptype in ("db_write", "command_output", "metric", "test_pass") and not path:
            conn.execute(
                "UPDATE proof_artifacts SET verified = 1, verified_at = ? WHERE proof_id = ?",
                (datetime.now().isoformat(), pid),
            )
            verified += 1
            continue

        if not path:
            skipped += 1
            continue

        p = Path(path)
        if not p.exists():
            print(f"  ✗ {pid}: file missing → {path}")
            failed += 1
            continue

        current_hash = _hash_file(path)
        if stored_hash and current_hash != stored_hash:
            print(f"  ⚠ {pid}: hash mismatch → {path}")
            print(f"      stored:  {stored_hash[:16]}...")
            print(f"      current: {current_hash[:16]}...")
            failed += 1
            continue

        # Update hash if not stored (file existed at verify time)
        conn.execute(
            "UPDATE proof_artifacts SET verified = 1, verified_at = ?, artifact_hash = ? WHERE proof_id = ?",
            (datetime.now().isoformat(), current_hash or stored_hash, pid),
        )
        verified += 1

    conn.commit()
    conn.close()

    total = len(rows)
    print(f"  Verified: {verified}/{total}  Failed: {failed}  Skipped: {skipped}")
    if failed > 0:
        sys.exit(1)


def cmd_report(args) -> None:
    conn = _connect()

    if args.all:
        runs = conn.execute(
            """SELECT DISTINCT p.run_id, r.name, r.status, r.started_at, r.ended_at
               FROM proof_artifacts p
               LEFT JOIN perf_runs r ON p.run_id = r.run_id
               ORDER BY r.started_at DESC"""
        ).fetchall()
    else:
        runs = conn.execute(
            """SELECT r.run_id, r.name, r.status, r.started_at, r.ended_at
               FROM perf_runs r WHERE r.run_id = ?""",
            (args.run_id,),
        ).fetchall()

    if not runs:
        print("  No runs found.")
        return

    print("=" * 72)
    print("  PROOF-IN-THE-PUDDING REPORT")
    print("=" * 72)

    for run in runs:
        rid = run["run_id"]
        name = run["name"] or "unnamed"
        status = run["status"] or "running"

        proofs = conn.execute(
            """SELECT proof_id, agent, proof_type, description,
                      artifact_path, verified, created_at
               FROM proof_artifacts WHERE run_id = ?
               ORDER BY created_at""",
            (rid,),
        ).fetchall()

        total = len(proofs)
        v_count = sum(1 for p in proofs if p["verified"])
        coverage = (v_count / total * 100) if total else 0

        print(f"\n  Run: {name} [{rid}]  Status: {status}")
        print(f"  Proofs: {total}  Verified: {v_count}  Coverage: {coverage:.0f}%")
        print("-" * 72)

        if not proofs:
            print("  (no proof artifacts recorded)")
            continue

        for p in proofs:
            v_mark = "✓" if p["verified"] else "○"
            ptype = p["proof_type"]
            desc = p["description"]
            agent = p["agent"]
            path = p["artifact_path"] or ""
            short_path = path.replace("f:\\", "").replace("\\", "/") if path else ""
            print(f"  {v_mark} [{ptype:15s}] {agent:30s} {desc}")
            if short_path:
                print(f"    → {short_path}")

    print("\n" + "=" * 72)
    conn.close()


def cmd_summary(args) -> None:
    conn = _connect()

    # Agent proof coverage
    agents = conn.execute(
        """SELECT agent,
                  COUNT(*) as total,
                  SUM(verified) as verified,
                  COUNT(DISTINCT run_id) as runs
           FROM proof_artifacts
           GROUP BY agent
           ORDER BY total DESC"""
    ).fetchall()

    # Runs without proofs
    orphan_runs = conn.execute(
        """SELECT r.run_id, r.name, r.status
           FROM perf_runs r
           LEFT JOIN proof_artifacts p ON r.run_id = p.run_id
           WHERE p.proof_id IS NULL
             AND r.ended_at IS NOT NULL
           ORDER BY r.started_at DESC
           LIMIT 20"""
    ).fetchall()

    print("=" * 72)
    print("  PROOF COVERAGE SUMMARY")
    print("=" * 72)

    if agents:
        print(f"\n  {'Agent':<35s} {'Proofs':>6s} {'Verified':>9s} {'Rate':>6s} {'Runs':>5s}")
        print("  " + "-" * 65)
        total_proofs = 0
        total_verified = 0
        for a in agents:
            rate = (a["verified"] / a["total"] * 100) if a["total"] else 0
            total_proofs += a["total"]
            total_verified += a["verified"]
            print(f"  {a['agent']:<35s} {a['total']:>6d} {a['verified']:>9d} {rate:>5.0f}% {a['runs']:>5d}")
        overall_rate = (total_verified / total_proofs * 100) if total_proofs else 0
        print("  " + "-" * 65)
        print(f"  {'TOTAL':<35s} {total_proofs:>6d} {total_verified:>9d} {overall_rate:>5.0f}%")
    else:
        print("\n  No proof artifacts recorded yet.")

    if orphan_runs:
        print(f"\n  Runs without proof ({len(orphan_runs)}):")
        for r in orphan_runs:
            print(f"    ○ {r['name'] or 'unnamed'} [{r['run_id']}] — {r['status'] or '?'}")

    print("\n" + "=" * 72)
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="⊕ Proof-in-the-Pudding CLI")
    sub = parser.add_subparsers(dest="command")

    # record
    p_rec = sub.add_parser("record", help="Record a proof artifact")
    p_rec.add_argument("run_id", help="Perf run ID to attach proof to")
    p_rec.add_argument("agent", help="Agent name (e.g. ⊕workspace-overseer)")
    p_rec.add_argument("proof_type", choices=PROOF_TYPES, help="Type of proof")
    p_rec.add_argument("description", help="What this proves")
    p_rec.add_argument("--path", help="Path to artifact file")
    p_rec.add_argument("--hash", help="Pre-computed SHA-256 hash")

    # verify
    p_ver = sub.add_parser("verify", help="Verify proof artifacts")
    p_ver.add_argument("run_id", nargs="?", help="Run ID to verify")
    p_ver.add_argument("--all", action="store_true", help="Verify all unverified")

    # report
    p_rep = sub.add_parser("report", help="Proof report")
    p_rep.add_argument("run_id", nargs="?", help="Run ID to report")
    p_rep.add_argument("--all", action="store_true", help="Report all runs")

    # summary
    sub.add_parser("summary", help="Agent proof coverage summary")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {"record": cmd_record, "verify": cmd_verify, "report": cmd_report, "summary": cmd_summary}[args.command](args)


if __name__ == "__main__":
    main()
