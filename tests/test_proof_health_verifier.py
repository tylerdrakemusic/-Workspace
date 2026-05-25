"""Tests for proof_health_verifier — proof artifact staleness sweep.

FR: FR-20260524-proof-artifact-staleness-verifier
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

# ── Ensure src/utils is importable ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_UTILS = PROJECT_ROOT / "src" / "utils"
sys.path.insert(0, str(SRC_UTILS))

import proof_health_verifier as phv  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────

_PROOF_SCHEMA = """
CREATE TABLE IF NOT EXISTS proof_artifacts (
    proof_id      TEXT PRIMARY KEY,
    run_id        TEXT,
    agent         TEXT NOT NULL,
    proof_type    TEXT NOT NULL,
    description   TEXT NOT NULL,
    artifact_path TEXT,
    artifact_hash TEXT,
    verified      INTEGER NOT NULL DEFAULT 0,
    verified_at   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@pytest.fixture
def mem_db() -> Generator[sqlite3.Connection, None, None]:
    """Fresh in-memory DB with the proof_artifacts table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_PROOF_SCHEMA)
    yield conn
    conn.close()


def _pid() -> str:
    return uuid.uuid4().hex[:12]


def _insert(conn: sqlite3.Connection, *, agent: str = "test-agent",
            proof_type: str = "file_created", description: str = "test proof",
            artifact_path: str | None = None, artifact_hash: str | None = None) -> str:
    pid = _pid()
    conn.execute(
        """INSERT INTO proof_artifacts
           (proof_id, agent, proof_type, description, artifact_path, artifact_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (pid, agent, proof_type, description, artifact_path, artifact_hash),
    )
    conn.commit()
    return pid


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Tests ────────────────────────────────────────────────────────────────────

class TestSweepEmptyDB:
    def test_empty_db_returns_zeros(self, mem_db: sqlite3.Connection) -> None:
        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert result["total"] == 0
        assert result["total_with_paths"] == 0
        assert result["healthy"] == 0
        assert result["stale"] == 0
        assert result["corrupt"] == 0
        assert result["skipped"] == 0
        assert result["failure_rate_pct"] == 0.0
        assert result["failed_rows"] == []


class TestSweepHealthy:
    def test_existing_file_no_stored_hash_is_healthy(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        f = tmp_path / "artifact.txt"
        f.write_bytes(b"hello")
        _insert(mem_db, artifact_path=str(f), artifact_hash=None)

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert result["healthy"] == 1
        assert result["stale"] == 0
        assert result["corrupt"] == 0
        assert result["failed_rows"] == []

    def test_existing_file_matching_hash_is_healthy(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        data = b"some content"
        f = tmp_path / "artifact.txt"
        f.write_bytes(data)
        _insert(mem_db, artifact_path=str(f), artifact_hash=_sha256(data))

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert result["healthy"] == 1
        assert result["failed_rows"] == []


class TestSweepStale:
    def test_missing_file_is_stale(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        missing = str(tmp_path / "does_not_exist.txt")
        _insert(mem_db, artifact_path=missing, artifact_hash=None)

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert result["stale"] == 1
        assert result["healthy"] == 0
        assert len(result["failed_rows"]) == 1
        assert result["failed_rows"][0]["reason"] == "stale"
        assert result["failed_rows"][0]["artifact_path"] == missing
        assert result["failed_rows"][0]["current_hash"] is None


class TestSweepCorrupt:
    def test_hash_mismatch_is_corrupt(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        f = tmp_path / "tampered.txt"
        f.write_bytes(b"original")
        old_hash = _sha256(b"original")
        f.write_bytes(b"tampered")  # overwrite with different content

        _insert(mem_db, artifact_path=str(f), artifact_hash=old_hash)

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert result["corrupt"] == 1
        assert result["stale"] == 0
        assert len(result["failed_rows"]) == 1
        row = result["failed_rows"][0]
        assert row["reason"] == "corrupt"
        assert row["stored_hash"] == old_hash
        assert row["current_hash"] == _sha256(b"tampered")


class TestSweepSkipped:
    def test_pathless_rows_are_skipped(self, mem_db: sqlite3.Connection) -> None:
        for ptype in ("db_write", "metric", "command_output", "test_pass"):
            _insert(mem_db, proof_type=ptype, artifact_path=None)

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert result["skipped"] == 4
        assert result["total_with_paths"] == 0
        assert result["healthy"] == 0
        assert result["failed_rows"] == []


class TestSweepMixed:
    def test_mixed_rows_counted_correctly(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        # 2 healthy files
        for i in range(2):
            f = tmp_path / f"healthy_{i}.txt"
            f.write_bytes(b"data")
            _insert(mem_db, artifact_path=str(f), artifact_hash=_sha256(b"data"))

        # 1 stale (missing)
        _insert(mem_db, artifact_path=str(tmp_path / "gone.txt"))

        # 1 skipped (no path)
        _insert(mem_db, proof_type="metric", artifact_path=None)

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert result["total"] == 4
        assert result["total_with_paths"] == 3
        assert result["healthy"] == 2
        assert result["stale"] == 1
        assert result["skipped"] == 1
        assert result["corrupt"] == 0


class TestFailureRate:
    def test_failure_rate_below_threshold_exits_zero(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        # 10 healthy, 0 stale → 0% failure rate
        for i in range(10):
            f = tmp_path / f"f{i}.txt"
            f.write_bytes(b"x")
            _insert(mem_db, artifact_path=str(f))

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"), \
             patch.object(phv, "_log"):
            result = phv.sweep()

        assert result["failure_rate_pct"] == 0.0

    def test_failure_rate_above_threshold_reflected_in_result(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        # 8 healthy, 3 stale → 3/11 ≈ 27.3% > 10%
        for i in range(8):
            f = tmp_path / f"good_{i}.txt"
            f.write_bytes(b"x")
            _insert(mem_db, artifact_path=str(f))
        for i in range(3):
            _insert(mem_db, artifact_path=str(tmp_path / f"missing_{i}.txt"))

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert result["failure_rate_pct"] > 10.0
        assert result["stale"] == 3


class TestJsonOutput:
    def test_json_schema_keys_present(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        f = tmp_path / "a.txt"
        f.write_bytes(b"z")
        _insert(mem_db, artifact_path=str(f))

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        required = {
            "run_at", "total", "total_with_paths", "healthy",
            "stale", "corrupt", "skipped", "failure_rate_pct", "failed_rows",
        }
        assert required.issubset(result.keys())

    def test_failed_row_schema_keys_present(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        _insert(mem_db, artifact_path=str(tmp_path / "missing.txt"))

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        assert len(result["failed_rows"]) == 1
        row = result["failed_rows"][0]
        required = {
            "proof_id", "agent", "proof_type", "description",
            "artifact_path", "stored_hash", "current_hash", "reason",
        }
        assert required.issubset(row.keys())

    def test_result_is_json_serialisable(
        self, mem_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        _insert(mem_db, artifact_path=str(tmp_path / "nope.txt"))

        with patch.object(phv, "get_connection", return_value=mem_db), \
             patch.object(phv, "init_db"):
            result = phv.sweep()

        # Should not raise
        serialised = json.dumps(result)
        roundtripped = json.loads(serialised)
        assert roundtripped["stale"] == result["stale"]
