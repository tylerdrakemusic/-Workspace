"""Database connection utility for ⊕Workspace — encrypted agent perf DB."""
import os
from pathlib import Path

from dotenv import load_dotenv
import sqlcipher3

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DB_PATH = Path(__file__).parent.parent / "data" / "workspace.db"


def _apply_cipher_pragmas(conn: sqlcipher3.Connection) -> None:
    """Apply SQLCipher compatibility pragmas used by this workspace DB."""
    conn.execute("PRAGMA cipher_page_size=4096")
    conn.execute("PRAGMA kdf_iter=256000")
    conn.execute("PRAGMA cipher_hmac_algorithm=HMAC_SHA512")


def _try_open_with_key(conn: sqlcipher3.Connection, key: str, *, use_hex: bool) -> bool:
    """Try opening DB with a key mode and verify by probing sqlite_master."""
    if use_hex:
        key_hex = key.encode().hex()
        conn.execute(f"PRAGMA key=\"x'{key_hex}'\"")  # nosec B608 — hex-encoded env-var key, no user input
    else:
        safe_key = key.replace("'", "''")
        conn.execute(f"PRAGMA key='{safe_key}'")  # nosec B608 — quote-escaped env-var key, no user input

    _apply_cipher_pragmas(conn)

    try:
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        return True
    except sqlcipher3.DatabaseError:
        return False


def get_connection() -> sqlcipher3.Connection:
    """Return a sqlcipher3 connection to the ⊕Workspace database."""
    key = os.environ.get("WORKSPACE_DB_KEY", "")
    if not key:
        raise RuntimeError("WORKSPACE_DB_KEY not set")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlcipher3.connect(str(DB_PATH))

    # workspace.db is currently passphrase-keyed; keep hex fallback for compatibility.
    opened = _try_open_with_key(conn, key, use_hex=False)
    if not opened:
        opened = _try_open_with_key(conn, key, use_hex=True)
    if not opened:
        conn.close()
        raise RuntimeError("Failed to decrypt workspace.db with WORKSPACE_DB_KEY")

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlcipher3.Row
    return conn


def init_db() -> None:
    """Create all tables if they do not exist."""
    conn = get_connection()
    conn.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE IF NOT EXISTS perf_runs (
        run_id     TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        started_at REAL NOT NULL,
        ended_at   REAL,
        status     TEXT,
        detail     TEXT
    );

    CREATE TABLE IF NOT EXISTS perf_steps (
        step_id     TEXT PRIMARY KEY,
        run_id      TEXT NOT NULL REFERENCES perf_runs(run_id),
        agent       TEXT NOT NULL,
        description TEXT,
        started_at  REAL NOT NULL,
        ended_at    REAL,
        elapsed_ms  REAL,
        status      TEXT,
        detail      TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_steps_run ON perf_steps(run_id);

    CREATE TABLE IF NOT EXISTS vulnerabilities (
        vuln_id        TEXT PRIMARY KEY,
        scan_date      TEXT NOT NULL,
        category       TEXT NOT NULL,
        severity       TEXT NOT NULL CHECK(severity IN ('critical','high','medium','low','info')),
        file_path      TEXT,
        line_number    INTEGER,
        description    TEXT NOT NULL,
        owasp_id       TEXT,
        status         TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','remediated','accepted','false_positive')),
        override_note  TEXT,
        remediated_at  TEXT,
        created_at     TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_vuln_status ON vulnerabilities(status);
    CREATE INDEX IF NOT EXISTS idx_vuln_severity ON vulnerabilities(severity);

    CREATE TABLE IF NOT EXISTS proof_artifacts (
        proof_id      TEXT PRIMARY KEY,
        run_id        TEXT REFERENCES perf_runs(run_id),
        agent         TEXT NOT NULL,
        proof_type    TEXT NOT NULL CHECK(proof_type IN (
            'file_created','file_modified','db_write','command_output',
            'metric','screenshot','dashboard','test_pass'
        )),
        description   TEXT NOT NULL,
        artifact_path TEXT,
        artifact_hash TEXT,
        verified      INTEGER NOT NULL DEFAULT 0,
        verified_at   TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_proof_run ON proof_artifacts(run_id);
    CREATE INDEX IF NOT EXISTS idx_proof_agent ON proof_artifacts(agent);
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
