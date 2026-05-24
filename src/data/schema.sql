-- ⊕Workspace SQLCipher schema dump (no data)
-- Source: src/utils/init_db.py (authoritative).
-- Fallback path: pysqlcipher3 / sqlcipher CLI were unavailable on the build
-- machine, so this schema is extracted from the canonical init_db.py
-- executescript body rather than a live PRAGMA-keyed dump.
-- The actual DB at src/data/workspace.db is SQLCipher-encrypted; the key is
-- in $env:WORKSPACE_DB_KEY. To regenerate an empty DB from this schema:
--     sqlcipher src/data/workspace.db
--     sqlite> PRAGMA key = '...';
--     sqlite> .read src/data/schema.sql

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
