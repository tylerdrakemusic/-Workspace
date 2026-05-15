"""
SQLCipher MCP Server — encrypted multi-DB access for all workspace DBs.

Exposes four workspace databases via MCP tools:
  - workspace  → ⊕Workspace/src/data/workspace.db      (WORKSPACE_DB_KEY)
  - infinitelife → ∞Life/src/data/infinitelife.db       (INFINITELIFE_DB_KEY)
  - heartmusic → ❤Music/src/data/heartmusic.db         (HEARTMUSIC_DB_KEY)
  - quantum    → ⟨ψ⟩Quantum/src/data/quantumpsi.db     (QUANTUM_DB_KEY)

Tools exposed:
  - list_tables(db)                — list tables + row counts
  - describe_table(db, table)      — column names, types, and constraints
  - read_query(db, sql, params)    — SELECT only (read-only access)
  - write_query(db, sql, params)   — INSERT/UPDATE/DELETE (∞Life blocked — read-only)

Security:
  - DB keys read from Windows System Environment Variables only (never args/config)
  - ∞Life DB is READ-ONLY — write_query is blocked for infinitelife
  - SQL injection guard: read_query rejects statements that don't start with SELECT
  - No keys or connection details are returned to the caller

FR: FR-20260424-sqlcipher-mcp-server
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import sqlcipher3
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# DB registry
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[3]  # f:\

DB_REGISTRY: dict[str, dict[str, Any]] = {
    "workspace": {
        "path": _ROOT / "⊕Workspace" / "src" / "data" / "workspace.db",
        "env_key": "WORKSPACE_DB_KEY",
        "readonly": False,
        "hex_key": False,  # passphrase mode with hex fallback
        "pragmas": {
            "cipher_page_size": "4096",
            "kdf_iter": "256000",
            "cipher_hmac_algorithm": "HMAC_SHA512",
        },
    },
    "infinitelife": {
        "path": _ROOT / "∞Life" / "src" / "data" / "infinitelife.db",
        "env_key": "INFINITELIFE_DB_KEY",
        "readonly": True,   # health/genomic data — never allow writes via MCP
        "hex_key": True,
        "pragmas": {
            "cipher_page_size": "4096",
            "kdf_iter": "256000",
            "cipher_hmac_algorithm": "HMAC_SHA512",
        },
    },
    "heartmusic": {
        "path": _ROOT / "❤Music" / "src" / "data" / "heartmusic.db",
        "env_key": "HEARTMUSIC_DB_KEY",
        "readonly": False,
        "hex_key": True,
        "pragmas": {
            "cipher_page_size": "4096",
            "kdf_iter": "256000",
            "cipher_hmac_algorithm": "HMAC_SHA512",
        },
    },
    "quantum": {
        "path": _ROOT / "⟨ψ⟩Quantum" / "src" / "data" / "quantumpsi.db",
        "env_key": "QUANTUM_DB_KEY",
        "readonly": False,
        "hex_key": True,
        "pragmas": {
            "cipher_page_size": "4096",
            "kdf_iter": "256000",
            "cipher_hmac_algorithm": "HMAC_SHA512",
        },
    },
}

VALID_DBS = list(DB_REGISTRY.keys())

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _apply_pragmas(conn: sqlcipher3.Connection, pragmas: dict) -> None:
    for pragma, val in pragmas.items():
        conn.execute(f"PRAGMA {pragma}={val}")  # nosec B608 — pragma names/values from hardcoded config dict


def _try_key(conn: sqlcipher3.Connection, key: str, hex_mode: bool, pragmas: dict) -> bool:
    """Apply key + pragmas and probe sqlite_master. Returns True on success."""
    if hex_mode:
        conn.execute(f"PRAGMA key=\"x'{key.encode().hex()}'\"")  # nosec B608 — hex-encoded env-var key
    else:
        conn.execute(f"PRAGMA key='{key.replace(chr(39), chr(39)*2)}'")  # nosec B608 — quote-escaped env-var key
    _apply_pragmas(conn, pragmas)
    try:
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        return True
    except sqlcipher3.DatabaseError:
        return False


def _open_db(db_name: str) -> sqlcipher3.Connection:
    """Open and return an authenticated sqlcipher3 connection."""
    if db_name not in DB_REGISTRY:
        raise ValueError(f"Unknown db '{db_name}'. Valid options: {VALID_DBS}")

    cfg = DB_REGISTRY[db_name]
    db_path = cfg["path"]

    if not db_path.exists():
        raise RuntimeError(f"Database file not found: {db_path}")

    key = os.environ.get(cfg["env_key"], "")
    if not key:
        raise RuntimeError(f"Environment variable {cfg['env_key']} is not set.")

    pragmas = cfg["pragmas"]

    # Try primary key mode, then fallback to the opposite mode
    conn = sqlcipher3.connect(str(db_path))
    if _try_key(conn, key, cfg["hex_key"], pragmas):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlcipher3.Row
        return conn
    conn.close()

    # Fallback: opposite hex mode
    conn = sqlcipher3.connect(str(db_path))
    if _try_key(conn, key, not cfg["hex_key"], pragmas):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlcipher3.Row
        return conn
    conn.close()

    raise RuntimeError(f"Failed to decrypt '{db_name}' — check {cfg['env_key']}")


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "sqlcipher-workspace",
    instructions=(
        "Provides read/write access to all four encrypted workspace SQLite databases "
        "(workspace, infinitelife, heartmusic, quantum). "
        "The 'infinitelife' DB is READ-ONLY — health and genomic data must never be modified via MCP. "
        "Always use read_query for SELECT statements. Use write_query only when explicitly requested."
    ),
)


@mcp.tool()
def list_tables(db: str) -> str:
    """
    List all tables in the specified workspace database with their row counts.

    Args:
        db: Database name — one of: workspace, infinitelife, heartmusic, quantum
    """
    conn = _open_db(db)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        if not tables:
            return f"[{db}] No tables found."
        lines = [f"[{db}] Tables:"]
        for row in tables:
            tname = row[0]
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]  # nosec B608 — tname from sqlite_master (trusted)
            except Exception:
                count = "?"
            lines.append(f"  {tname} ({count} rows)")
        return "\n".join(lines)
    finally:
        conn.close()


@mcp.tool()
def describe_table(db: str, table: str) -> str:
    """
    Describe the schema of a table — column names, types, and constraints.

    Args:
        db: Database name — one of: workspace, infinitelife, heartmusic, quantum
        table: Table name to describe
    """
    if not re.match(r"^[A-Za-z0-9_]+$", table):
        return "Error: invalid table name."
    conn = _open_db(db)
    try:
        rows = conn.execute(f"PRAGMA table_info([{table}])").fetchall()  # nosec B608 — table validated by ^[A-Za-z0-9_]+$ allowlist
        if not rows:
            return f"[{db}.{table}] Table not found or has no columns."
        lines = [f"[{db}.{table}] Schema:"]
        for r in rows:
            pk = " PRIMARY KEY" if r["pk"] else ""
            notnull = " NOT NULL" if r["notnull"] else ""
            default = f" DEFAULT {r['dflt_value']}" if r["dflt_value"] is not None else ""
            lines.append(f"  {r['name']}  {r['type']}{pk}{notnull}{default}")
        return "\n".join(lines)
    finally:
        conn.close()


@mcp.tool()
def read_query(db: str, sql: str, params: list[Any] | None = None) -> str:
    """
    Execute a SELECT query against a workspace database. Read-only.

    Args:
        db: Database name — one of: workspace, infinitelife, heartmusic, quantum
        sql: A SELECT SQL statement
        params: Optional list of positional parameters for the query
    """
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        return "Error: read_query only accepts SELECT statements."
    conn = _open_db(db)
    try:
        rows = conn.execute(sql, params or []).fetchall()
        if not rows:
            return f"[{db}] Query returned 0 rows."
        keys = rows[0].keys()
        header = " | ".join(keys)
        separator = "-" * len(header)
        lines = [f"[{db}] {len(rows)} row(s):", header, separator]
        for r in rows[:200]:  # cap at 200 rows for safety
            lines.append(" | ".join(str(r[k]) for k in keys))
        if len(rows) > 200:
            lines.append(f"... ({len(rows) - 200} more rows truncated)")
        return "\n".join(lines)
    finally:
        conn.close()


@mcp.tool()
def write_query(db: str, sql: str, params: list[Any] | None = None) -> str:
    """
    Execute an INSERT, UPDATE, or DELETE query. Blocked for 'infinitelife' (health data).

    Args:
        db: Database name — one of: workspace, heartmusic, quantum (NOT infinitelife)
        sql: An INSERT, UPDATE, or DELETE SQL statement
        params: Optional list of positional parameters
    """
    if db == "infinitelife":
        return "Error: write_query is blocked for 'infinitelife'. Health and genomic data is read-only via MCP."
    stripped = sql.strip().upper()
    if stripped.startswith("SELECT"):
        return "Error: use read_query for SELECT statements."
    if any(stripped.startswith(kw) for kw in ("DROP", "ALTER", "CREATE", "ATTACH", "DETACH", "PRAGMA")):
        return "Error: DDL and PRAGMA statements are not allowed via write_query."
    conn = _open_db(db)
    try:
        cur = conn.execute(sql, params or [])
        conn.commit()
        return f"[{db}] OK — {cur.rowcount} row(s) affected."
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
