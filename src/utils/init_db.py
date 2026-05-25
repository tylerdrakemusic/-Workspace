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


def _backfill_perf_runs_agent(conn) -> None:
    """Backfill the new agent column from the name field using sigil+slug patterns."""
    import re

    SIGIL_RE = re.compile(
        r"^(\u2295workspace-[\w-]+|\u221elife-[\w-]+|\u2764music-[\w-]+|"
        r"\u27e8\u03c8\u27e9quantum-[\w-]+|\U0001f441ai-manifest-[\w-]+)"
    )
    FR_MAP = [
        (re.compile(r"^(?:fr-cycle-|ff-all-|ff-)", re.I), "\u2295workspace-ci"),
        (re.compile(r"^(?:FR[-\s]intake|FR intake)", re.I), "\u2295workspace-intake"),
        (re.compile(r"^bugfix-intake-", re.I), "\u2295workspace-intake"),
        (re.compile(r"^discover-", re.I), "\u2295workspace-discovery"),
        (re.compile(r"^overseer-", re.I), "\u2295workspace-overseer"),
        (re.compile(r"^Architecture review gate", re.I), "\u2295workspace-architecture-reviewer"),
        (re.compile(r"^(?:Bulk reprioritize|Apply selected discovery)", re.I), "\u2295workspace-discovery"),
        (re.compile(r"^(?:Create vocal pilot|FR intake)", re.I), "\u2295workspace-intake"),
        # New patterns (FR-20260525-agent-rationalization backfill)
        (re.compile(r"^qa[-\s]", re.I), "\u2295workspace-qa"),
        (re.compile(r"^intake\s", re.I), "\u2295workspace-intake"),
        (re.compile(r"^scope-approv", re.I), "\u2295workspace-intake"),
        (re.compile(r"^security-", re.I), "\u2295workspace-security"),
        (re.compile(r"^review\+PR", re.I), "\u2295workspace-reviewer"),
    ]

    rows = conn.execute("SELECT run_id, name FROM perf_runs WHERE agent IS NULL").fetchall()
    updates = []
    for run_id, name in rows:
        agent = None
        m = SIGIL_RE.match(name)
        if m:
            agent = m.group(1).rstrip(": ")
        else:
            for pattern, slug in FR_MAP:
                if pattern.match(name):
                    agent = slug
                    break
        if agent:
            updates.append((agent, run_id))
    if updates:
        conn.executemany("UPDATE perf_runs SET agent = ? WHERE run_id = ?", updates)
        conn.commit()


def _rebuild_proof_artifacts(conn) -> None:
    """Rebuild proof_artifacts without a hardcoded proof_type CHECK constraint.

    The old schema CHECK-constrained proof_type to a fixed list. Removing the
    constraint lets new types (e.g. perf_regression_alert, perf_low_data) be
    written without future rebuilds. Python-side PROOF_TYPES in proof_cli.py
    acts as soft validation going forward.
    """
    conn.execute("SAVEPOINT rebuild_proof")
    try:
        conn.execute("ALTER TABLE proof_artifacts RENAME TO _proof_artifacts_old")
        conn.execute("""
            CREATE TABLE proof_artifacts (
                proof_id      TEXT PRIMARY KEY,
                run_id        TEXT REFERENCES perf_runs(run_id),
                agent         TEXT NOT NULL,
                proof_type    TEXT NOT NULL,
                description   TEXT NOT NULL,
                artifact_path TEXT,
                artifact_hash TEXT,
                verified      INTEGER NOT NULL DEFAULT 0,
                verified_at   TEXT,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            INSERT INTO proof_artifacts
            SELECT proof_id, run_id, agent, proof_type, description,
                   artifact_path, artifact_hash, verified, verified_at, created_at
            FROM _proof_artifacts_old
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_proof_run ON proof_artifacts(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_proof_agent ON proof_artifacts(agent)")
        conn.execute("DROP TABLE _proof_artifacts_old")
        conn.execute("RELEASE SAVEPOINT rebuild_proof")
        conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT rebuild_proof")
        raise


def _run_migrations(conn) -> None:
    """Apply pending schema migrations idempotently."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(perf_runs)").fetchall()}

    if "last_heartbeat" not in cols:
        conn.execute("ALTER TABLE perf_runs ADD COLUMN last_heartbeat REAL")
        conn.commit()

    if "agent" not in cols:
        conn.execute("ALTER TABLE perf_runs ADD COLUMN agent TEXT")
        conn.commit()
        _backfill_perf_runs_agent(conn)

    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='proof_artifacts'"
    ).fetchone()
    if row and "CHECK(proof_type IN" in (row[0] or ""):
        _rebuild_proof_artifacts(conn)


def init_db() -> None:
    """Create all tables if they do not exist."""
    conn = get_connection()
    conn.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE IF NOT EXISTS perf_runs (
        run_id          TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        agent           TEXT,
        started_at      REAL NOT NULL,
        ended_at        REAL,
        status          TEXT,
        detail          TEXT,
        last_heartbeat  REAL
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
        proof_type    TEXT NOT NULL,
        description   TEXT NOT NULL,
        artifact_path TEXT,
        artifact_hash TEXT,
        verified      INTEGER NOT NULL DEFAULT 0,
        verified_at   TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_proof_run ON proof_artifacts(run_id);
    CREATE INDEX IF NOT EXISTS idx_proof_agent ON proof_artifacts(agent);

    CREATE TABLE IF NOT EXISTS scan_run_log (
        run_id           TEXT PRIMARY KEY,
        started_at       TEXT NOT NULL,
        completed_at     TEXT,
        projects_scanned TEXT NOT NULL DEFAULT '[]',
        new_vulns_count  INTEGER NOT NULL DEFAULT 0,
        total_findings   INTEGER NOT NULL DEFAULT 0,
        bandit_exit_code INTEGER,
        safety_exit_code INTEGER,
        status           TEXT NOT NULL DEFAULT 'ok' CHECK(status IN ('ok','error','partial')),
        error_detail     TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_scan_run_started ON scan_run_log(started_at);
    """)
    conn.commit()
    _run_migrations(conn)
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
