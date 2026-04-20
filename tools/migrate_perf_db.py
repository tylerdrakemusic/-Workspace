"""
Migrate unencrypted agent_perf.db → encrypted workspace.db (SQLCipher)

Run once:
    cd f:\executedcode\⊕Workspace
    C:\G\python.exe tools/migrate_perf_db.py

Prerequisites:
    - WORKSPACE_DB_KEY environment variable set
    - sqlcipher3 package installed
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from utils.init_db import get_connection, init_db, DB_PATH

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "data"
OLD_DB = DATA_DIR / "agent_perf.db"


def migrate() -> None:
    if not OLD_DB.exists():
        print(f"No unencrypted DB found at {OLD_DB}. Nothing to migrate.")
        return

    # Read all data from the old plaintext DB
    old_conn = sqlite3.connect(str(OLD_DB))
    old_conn.row_factory = sqlite3.Row

    runs = old_conn.execute("SELECT * FROM perf_runs ORDER BY started_at").fetchall()
    steps = old_conn.execute("SELECT * FROM perf_steps ORDER BY started_at").fetchall()
    old_conn.close()

    print(f"Found {len(runs)} runs and {len(steps)} steps in plaintext DB.")

    # Ensure encrypted DB schema exists
    init_db()
    conn = get_connection()

    for r in runs:
        conn.execute(
            "INSERT OR IGNORE INTO perf_runs (run_id, name, started_at, ended_at, status, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (r["run_id"], r["name"], r["started_at"], r["ended_at"], r["status"], r["detail"]),
        )

    for s in steps:
        conn.execute(
            "INSERT OR IGNORE INTO perf_steps (step_id, run_id, agent, description, started_at, ended_at, elapsed_ms, status, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (s["step_id"], s["run_id"], s["agent"], s["description"],
             s["started_at"], s["ended_at"], s["elapsed_ms"], s["status"], s["detail"]),
        )

    conn.commit()

    # Verify
    check_runs = conn.execute("SELECT COUNT(*) FROM perf_runs").fetchone()[0]
    check_steps = conn.execute("SELECT COUNT(*) FROM perf_steps").fetchone()[0]
    conn.close()

    print(f"Migrated: {check_runs} runs, {check_steps} steps → {DB_PATH}")
    print(f"\nOld DB preserved at {OLD_DB}. Delete manually after confirming.")


if __name__ == "__main__":
    migrate()
