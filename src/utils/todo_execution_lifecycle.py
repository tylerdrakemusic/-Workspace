"""Durable worker lifecycle coordination for TODO execution."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


class LifecycleError(RuntimeError):
    """Base error for lifecycle coordination failures."""


class DuplicateClaimError(LifecycleError):
    """Raised when a TODO already has a different active claim."""


class LeaseOwnershipError(LifecycleError):
    """Raised when a worker presents the wrong lease credentials."""


class InvalidTransitionError(LifecycleError):
    """Raised when a lifecycle operation is not legal for the current state."""


class RetryExhaustedError(LifecycleError):
    """Raised when a failed or stale attempt has no retry budget left."""


@dataclass(frozen=True)
class ExecutionRecord:
    """Current durable execution state for one TODO attempt."""

    todo_id: str
    fr_id: str | None
    worker_id: str
    claim_id: str
    lease_token: str
    state: str
    lease_expires_at: float
    heartbeat_at: float
    attempt: int
    max_retries: int
    idempotency_key: str | None


class ExecutionLifecycle:
    """Coordinate TODO workers through one parameterized SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS todo_execution_lifecycle (
                todo_id TEXT PRIMARY KEY,
                fr_id TEXT,
                worker_id TEXT NOT NULL,
                claim_id TEXT NOT NULL UNIQUE,
                lease_token TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                lease_expires_at REAL NOT NULL,
                heartbeat_at REAL NOT NULL,
                attempt INTEGER NOT NULL,
                max_retries INTEGER NOT NULL,
                idempotency_key TEXT UNIQUE,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS todo_execution_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                todo_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                state TEXT NOT NULL,
                reason TEXT NOT NULL,
                error TEXT,
                occurred_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_todo_execution_events_todo
                ON todo_execution_events(todo_id, event_id);
            CREATE TABLE IF NOT EXISTS todo_execution_stale_recoveries (
                recovery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                todo_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                recovered_at REAL NOT NULL,
                reason TEXT NOT NULL,
                error TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def claim(
        self,
        *,
        todo_id: str,
        fr_id: str | None,
        worker_id: str,
        claim_id: str,
        lease_token: str,
        now: float,
        lease_seconds: int,
        max_retries: int = 0,
        idempotency_key: str | None = None,
    ) -> ExecutionRecord:
        """Atomically claim a TODO or return its exact repeated delivery."""
        if lease_seconds <= 0 or max_retries < 0:
            raise ValueError("invalid lease or retry policy")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self.connection.execute(
                "SELECT * FROM todo_execution_lifecycle WHERE todo_id = ?",
                (todo_id,),
            ).fetchone()
            if existing is not None:
                if idempotency_key and existing["idempotency_key"] == idempotency_key:
                    self.connection.commit()
                    return self._record(existing)
                if existing["state"] in {"claimed", "running"}:
                    raise DuplicateClaimError(f"TODO already has active claim: {todo_id}")

            record = ExecutionRecord(
                todo_id=todo_id,
                fr_id=fr_id,
                worker_id=worker_id,
                claim_id=claim_id,
                lease_token=lease_token,
                state="claimed",
                lease_expires_at=now + lease_seconds,
                heartbeat_at=now,
                attempt=(existing["attempt"] + 1 if existing is not None else 1),
                max_retries=max_retries,
                idempotency_key=idempotency_key,
            )
            self.connection.execute(
                """
                INSERT INTO todo_execution_lifecycle
                    (todo_id, fr_id, worker_id, claim_id, lease_token, state,
                     lease_expires_at, heartbeat_at, attempt, max_retries,
                     idempotency_key, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(todo_id) DO UPDATE SET
                    fr_id=excluded.fr_id, worker_id=excluded.worker_id,
                    claim_id=excluded.claim_id, lease_token=excluded.lease_token,
                    state=excluded.state, lease_expires_at=excluded.lease_expires_at,
                    heartbeat_at=excluded.heartbeat_at, attempt=excluded.attempt,
                    max_retries=excluded.max_retries,
                    idempotency_key=excluded.idempotency_key,
                    updated_at=excluded.updated_at
                """,
                (
                    record.todo_id, record.fr_id, record.worker_id, record.claim_id,
                    record.lease_token, record.state, record.lease_expires_at,
                    record.heartbeat_at, record.attempt, record.max_retries,
                    record.idempotency_key, now,
                ),
            )
            self._event(record, "claim accepted", None, now)
            self.connection.commit()
            return record
        except Exception:
            self.connection.rollback()
            raise

    def _event(
        self, record: ExecutionRecord, reason: str, error: str | None, occurred_at: float
    ) -> None:
        self.connection.execute(
            """INSERT INTO todo_execution_events
               (todo_id, claim_id, state, reason, error, occurred_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record.todo_id, record.claim_id, record.state, reason, error, occurred_at),
        )

    def heartbeat(
        self, todo_id: str, worker_id: str, lease_token: str,
        now: float, lease_seconds: int,
    ) -> ExecutionRecord:
        """Renew an owned live lease and transition it to running."""
        if lease_seconds <= 0:
            raise ValueError("lease duration must be positive")
        record = self._owned(todo_id, worker_id, lease_token, now)
        if now >= record.lease_expires_at:
            raise InvalidTransitionError("cannot heartbeat an expired lease")
        if record.state not in {"claimed", "running"}:
            raise InvalidTransitionError("heartbeat requires an active lease")
        return self._update(record, state="running", lease_expires_at=now + lease_seconds,
                            heartbeat_at=now, reason="heartbeat accepted", occurred_at=now)

    def complete(
        self, todo_id: str, worker_id: str, lease_token: str,
        now: float, reason: str,
    ) -> ExecutionRecord:
        """Complete an owned running execution exactly once."""
        return self._finish(todo_id, worker_id, lease_token, now, "completed", reason, None)

    def fail(
        self, todo_id: str, worker_id: str, lease_token: str,
        now: float, error: str,
    ) -> ExecutionRecord:
        """Record a terminal failure; retry is an explicit later operation."""
        return self._finish(todo_id, worker_id, lease_token, now, "failed", "execution failed", error)

    def retry(self, todo_id: str, now: float, reason: str) -> ExecutionRecord:
        """Move a failed or stale attempt back to queued when budget remains."""
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(todo_id)
            if row is None or row["state"] not in {"failed", "stale"}:
                self._record_invalid(todo_id, row, "retry requires failed or stale state", now)
                raise InvalidTransitionError("retry requires failed or stale state")
            if row["attempt"] > row["max_retries"]:
                self._record_invalid(todo_id, row, "retry budget exhausted", now)
                raise RetryExhaustedError(f"retry budget exhausted: {todo_id}")
            record = self._update_in_transaction(row, "queued", row["lease_expires_at"],
                                                 row["heartbeat_at"], reason, None, now)
            self.connection.commit()
            return record
        except Exception:
            if self.connection.in_transaction:
                self.connection.commit()
            raise

    def cancel(
        self, todo_id: str, worker_id: str, lease_token: str,
        now: float, reason: str,
    ) -> ExecutionRecord:
        """Cancel an owned active execution."""
        record = self._owned(todo_id, worker_id, lease_token, now)
        if record.state not in {"claimed", "running"}:
            raise InvalidTransitionError("cancellation requires an active lease")
        return self._update(record, state="cancelled", lease_expires_at=record.lease_expires_at,
                            heartbeat_at=record.heartbeat_at, reason=reason, occurred_at=now)

    def recover_stale(self, now: float) -> list[str]:
        """Mark expired active workers stale and persist a recovery record."""
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            rows = self.connection.execute(
                """SELECT * FROM todo_execution_lifecycle
                   WHERE state IN ('claimed', 'running') AND lease_expires_at <= ?""",
                (now,),
            ).fetchall()
            recovered: list[str] = []
            for row in rows:
                record = self._update_in_transaction(
                    row, "stale", row["lease_expires_at"], row["heartbeat_at"],
                    "lease expired; worker recovered", "lease expired", now,
                )
                self.connection.execute(
                    """INSERT INTO todo_execution_stale_recoveries
                       (todo_id, claim_id, recovered_at, reason, error)
                       VALUES (?, ?, ?, ?, ?)""",
                    (record.todo_id, record.claim_id, now,
                     "lease expired; worker recovered", "lease expired"),
                )
                recovered.append(record.todo_id)
            self.connection.commit()
            return recovered
        except Exception:
            self.connection.rollback()
            raise

    def get(self, todo_id: str) -> ExecutionRecord:
        """Return the current durable record for a TODO."""
        row = self._row(todo_id)
        if row is None:
            raise KeyError(todo_id)
        return self._record(row)

    def events(self, todo_id: str) -> list[sqlite3.Row]:
        """Return the append-only audit events for a TODO."""
        return self.connection.execute(
            "SELECT * FROM todo_execution_events WHERE todo_id = ? ORDER BY event_id",
            (todo_id,),
        ).fetchall()

    def _finish(
        self, todo_id: str, worker_id: str, lease_token: str, now: float,
        state: str, reason: str, error: str | None,
    ) -> ExecutionRecord:
        record = self._owned(todo_id, worker_id, lease_token, now)
        allowed_states = {"running"} | ({"claimed"} if state == "failed" else set())
        if record.state not in allowed_states:
            self._invalid_after_owned(record, "completion/failure requires running state", now)
            raise InvalidTransitionError("completion/failure requires running state")
        if now >= record.lease_expires_at:
            self._invalid_after_owned(record, "lease expired", now)
            raise InvalidTransitionError("lease expired")
        return self._update(record, state=state, lease_expires_at=record.lease_expires_at,
                            heartbeat_at=record.heartbeat_at, reason=reason, error=error,
                            occurred_at=now)

    def _owned(self, todo_id: str, worker_id: str, lease_token: str, now: float) -> ExecutionRecord:
        row = self._row(todo_id)
        if row is None or row["worker_id"] != worker_id or row["lease_token"] != lease_token:
            raise LeaseOwnershipError(f"lease ownership mismatch: {todo_id}")
        return self._record(row)

    def _update(
        self, record: ExecutionRecord, *, state: str, lease_expires_at: float,
        heartbeat_at: float, reason: str, occurred_at: float, error: str | None = None,
    ) -> ExecutionRecord:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(record.todo_id)
            if row is None or row["claim_id"] != record.claim_id or row["state"] != record.state:
                raise InvalidTransitionError("execution changed before transition")
            updated = self._update_in_transaction(row, state, lease_expires_at, heartbeat_at,
                                                  reason, error, occurred_at)
            self.connection.commit()
            return updated
        except Exception:
            self.connection.rollback()
            raise

    def _update_in_transaction(
        self, row: sqlite3.Row, state: str, lease_expires_at: float,
        heartbeat_at: float, reason: str, error: str | None, occurred_at: float,
    ) -> ExecutionRecord:
        self.connection.execute(
            """UPDATE todo_execution_lifecycle
               SET state = ?, lease_expires_at = ?, heartbeat_at = ?, updated_at = ?
               WHERE todo_id = ? AND claim_id = ?""",
            (state, lease_expires_at, heartbeat_at, occurred_at, row["todo_id"], row["claim_id"]),
        )
        updated = self._record(self._row(row["todo_id"]))
        self._event(updated, reason, error, occurred_at)
        return updated

    def _record_invalid(self, todo_id: str, row: sqlite3.Row | None, reason: str, now: float) -> None:
        if row is not None:
            self._event(self._record(row), "invalid transition", reason, now)

    def _invalid_after_owned(self, record: ExecutionRecord, error: str, now: float) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._event(record, "invalid transition", error, now)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _row(self, todo_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM todo_execution_lifecycle WHERE todo_id = ?", (todo_id,)
        ).fetchone()

    @staticmethod
    def _record(row: sqlite3.Row) -> ExecutionRecord:
        return ExecutionRecord(
            todo_id=row["todo_id"], fr_id=row["fr_id"], worker_id=row["worker_id"],
            claim_id=row["claim_id"], lease_token=row["lease_token"],
            state=row["state"], lease_expires_at=row["lease_expires_at"],
            heartbeat_at=row["heartbeat_at"], attempt=row["attempt"],
            max_retries=row["max_retries"], idempotency_key=row["idempotency_key"],
        )