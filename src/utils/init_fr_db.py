"""Database connection utility for ⊕Workspace — encrypted FR ledger DB."""
import os
from pathlib import Path

from dotenv import load_dotenv
import sqlcipher3

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DB_PATH = Path(__file__).parent.parent / "data" / "fr_ledgers.db"


def _apply_cipher_pragmas(conn: sqlcipher3.Connection) -> None:
    conn.execute("PRAGMA cipher_page_size=4096")
    conn.execute("PRAGMA kdf_iter=256000")
    conn.execute("PRAGMA cipher_hmac_algorithm=HMAC_SHA512")


def _try_open_with_key(conn: sqlcipher3.Connection, key: str, *, use_hex: bool) -> bool:
    if use_hex:
        key_hex = key.encode().hex()
        conn.execute(f"PRAGMA key=\"x'{key_hex}'\"")  # nosec B608
    else:
        safe_key = key.replace("'", "''")
        conn.execute(f"PRAGMA key='{safe_key}'")  # nosec B608
    _apply_cipher_pragmas(conn)
    try:
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        return True
    except sqlcipher3.DatabaseError:
        return False


def get_connection() -> sqlcipher3.Connection:
    """Return a sqlcipher3 connection to the FR ledger database."""
    key = os.environ.get("FR_LEDGERS_DB_KEY", "") or os.environ.get("WORKSPACE_DB_KEY", "")
    if not key:
        raise RuntimeError("FR_LEDGERS_DB_KEY (or fallback WORKSPACE_DB_KEY) not set")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlcipher3.connect(str(DB_PATH))

    opened = _try_open_with_key(conn, key, use_hex=False)
    if not opened:
        opened = _try_open_with_key(conn, key, use_hex=True)
    if not opened:
        conn.close()
        raise RuntimeError("Failed to decrypt fr_ledgers.db with FR_LEDGERS_DB_KEY")

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlcipher3.Row
    return conn


def init_db() -> None:
    """Create all FR ledger tables if they do not exist."""
    conn = get_connection()
    conn.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE IF NOT EXISTS feature_requests (
        id                  TEXT PRIMARY KEY,
        title               TEXT NOT NULL,
        type                TEXT NOT NULL,
        risk                TEXT,
        projects            TEXT,
        state               TEXT NOT NULL DEFAULT 'OPEN',
        branch              TEXT,
        prs                 TEXT,
        owner               TEXT,
        opened_at           TEXT NOT NULL,
        updated_at          TEXT NOT NULL,
        merged_at           TEXT,
        signed_off_at       TEXT,
        closed_at           TEXT,
        final_state         TEXT,
        cycle_timer_run_id  TEXT,
        acceptance_criteria TEXT,
        concurrency_notes   TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_fr_state    ON feature_requests(state);
    CREATE INDEX IF NOT EXISTS idx_fr_opened   ON feature_requests(opened_at);
    CREATE INDEX IF NOT EXISTS idx_fr_updated  ON feature_requests(updated_at DESC);

    CREATE TABLE IF NOT EXISTS fr_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        fr_id       TEXT NOT NULL REFERENCES feature_requests(id),
        ts          TEXT NOT NULL,
        agent       TEXT NOT NULL,
        event_type  TEXT NOT NULL,
        summary     TEXT NOT NULL,
        details     TEXT,
        next_action TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_events_fr  ON fr_events(fr_id);
    CREATE INDEX IF NOT EXISTS idx_events_ts  ON fr_events(ts);

    CREATE TABLE IF NOT EXISTS fr_artifacts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        fr_id         TEXT NOT NULL REFERENCES feature_requests(id),
        ts            TEXT NOT NULL,
        artifact_type TEXT NOT NULL,
        label         TEXT NOT NULL,
        path_or_url   TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_artifacts_fr ON fr_artifacts(fr_id);
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"FR ledger database initialized at {DB_PATH}")
