#!/usr/bin/env python3
"""
\u2295 Proof Artifact Staleness Verifier \u2014 weekly sweep of all proof_artifacts rows.

Iterates every row in the proof_artifacts table, checks whether each
referenced file still exists and whether its SHA-256 hash matches the
stored value, and writes a health report to reports/proof_health.json.

Classification:
  healthy  \u2014 file exists and hash matches (or no stored hash)
  stale    \u2014 artifact_path is set but the file is missing
  corrupt  \u2014 file exists but SHA-256 does not match the stored hash
  skipped  \u2014 no artifact_path (db_write / metric / command_output / test_pass);
             existence is implied by the DB row itself

Exit codes:
  0  \u2014 healthy: failure_rate = (stale + corrupt) / total_with_paths \u2264 10 %
  1  \u2014 unhealthy: failure_rate > 10 %

Usage (manual):
    C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\proof_health_verifier.py

Scheduled weekly at Sunday 04:00 by
    f:\\⊕Workspace\\tools\\register_proof_health_task.ps1

FR: FR-20260524-proof-artifact-staleness-verifier
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# \u2500\u2500 Path bootstrap \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
SCRIPT_DIR     = Path(__file__).resolve().parent          # src/utils/
WORKSPACE_ROOT = SCRIPT_DIR.parent.parent                 # f:\⊕Workspace
REPORTS_DIR    = WORKSPACE_ROOT / "reports"
LOG_FILE       = WORKSPACE_ROOT / "logs" / "proof_health.log"
JSON_OUT       = REPORTS_DIR / "proof_health.json"

sys.path.insert(0, str(SCRIPT_DIR))
from init_db import get_connection, init_db  # type: ignore[import]

# \u2500\u2500 Thresholds \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
FAILURE_RATE_THRESHOLD = 0.10  # exit 1 when > 10 % of path-bearing rows fail


# \u2500\u2500 Helpers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{_now_iso()}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _hash_file(path: Path) -> str:
    """Return SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# \u2500\u2500 Core sweep \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def sweep() -> dict[str, Any]:
    """
    Sweep all proof_artifacts rows and return a health dict.

    Returns:
        {
            "run_at": str,
            "total": int,
            "total_with_paths": int,
            "healthy": int,
            "stale": int,
            "corrupt": int,
            "skipped": int,
            "failure_rate_pct": float,
            "failed_rows": list[dict]
        }
    """
    init_db()
    conn = get_connection()

    rows = conn.execute(
        """SELECT proof_id, agent, proof_type, description,
                  artifact_path, artifact_hash
           FROM proof_artifacts
           ORDER BY created_at"""
    ).fetchall()
    conn.close()

    total            = len(rows)
    total_with_paths = 0
    healthy          = 0
    stale            = 0
    corrupt          = 0
    skipped          = 0
    failed_rows: list[dict[str, Any]] = []

    for row in rows:
        pid          = row["proof_id"]
        agent        = row["agent"]
        ptype        = row["proof_type"]
        description  = row["description"]
        path_str     = row["artifact_path"]
        stored_hash  = row["artifact_hash"]

        if not path_str:
            # Path-less proof types — verified by DB existence; not stale
            skipped += 1
            continue

        total_with_paths += 1
        p = Path(path_str)

        if not p.exists():
            stale += 1
            failed_rows.append({
                "proof_id":     pid,
                "agent":        agent,
                "proof_type":   ptype,
                "description":  description,
                "artifact_path": path_str,
                "stored_hash":  stored_hash,
                "current_hash": None,
                "reason":       "stale",
            })
            continue

        current_hash = _hash_file(p)

        if stored_hash and current_hash != stored_hash:
            corrupt += 1
            failed_rows.append({
                "proof_id":     pid,
                "agent":        agent,
                "proof_type":   ptype,
                "description":  description,
                "artifact_path": path_str,
                "stored_hash":  stored_hash,
                "current_hash": current_hash,
                "reason":       "corrupt",
            })
            continue

        healthy += 1

    failure_rate = (stale + corrupt) / total_with_paths if total_with_paths else 0.0

    return {
        "run_at":            _now_iso(),
        "total":             total,
        "total_with_paths":  total_with_paths,
        "healthy":           healthy,
        "stale":             stale,
        "corrupt":           corrupt,
        "skipped":           skipped,
        "failure_rate_pct":  round(failure_rate * 100, 2),
        "failed_rows":       failed_rows,
    }


# \u2500\u2500 Entry point \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def main() -> int:
    _log("proof_health_verifier: sweep started")

    result = sweep()

    # Write JSON report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with JSON_OUT.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    rate    = result["failure_rate_pct"]
    stale   = result["stale"]
    corrupt = result["corrupt"]
    total   = result["total"]
    healthy = result["healthy"]
    skipped = result["skipped"]

    _log(
        f"proof_health_verifier: done \u2014 total={total} healthy={healthy} "
        f"stale={stale} corrupt={corrupt} skipped={skipped} "
        f"failure_rate={rate:.1f}%"
    )
    _log(f"proof_health_verifier: report written \u2192 {JSON_OUT}")

    if result["total_with_paths"] > 0 and (rate / 100) > FAILURE_RATE_THRESHOLD:
        _log(
            f"proof_health_verifier: UNHEALTHY \u2014 failure rate {rate:.1f}% "
            f"exceeds threshold {FAILURE_RATE_THRESHOLD * 100:.0f}% \u2014 exit 1"
        )
        return 1

    _log("proof_health_verifier: HEALTHY \u2014 exit 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
