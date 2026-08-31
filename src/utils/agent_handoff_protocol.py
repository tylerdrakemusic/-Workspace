"""Durable, policy-filtered exchange primitives for agent handoffs."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Mapping


class SensitiveHandoffValueError(ValueError):
    """Raised when a handoff contains a forbidden sensitive value."""


class ResultExchangeError(ValueError):
    """Raised when a result cannot be exchanged for a handoff."""


class TakeoverNotAllowedError(PermissionError):
    """Raised when policy or operator approval does not permit takeover."""


_SENSITIVE = re.compile(
    r"(?:health|medical|genomic|blood|financial|account|routing|password|secret|token|credential|api[-_ ]?key)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HandoffEnvelope:
    """Immutable metadata describing one agent-to-agent handoff."""

    version: int
    handoff_id: str
    fr_id: str
    todo_id: str
    source_agent: str
    target_agent: str
    claim_id: str
    created_at: float
    context: Mapping[str, object]
    payload_digest: str


@dataclass(frozen=True)
class HandoffResult:
    """Immutable digest and routing metadata for one exchanged result."""

    result_id: int
    handoff_id: str
    sender_agent: str
    receiver_agent: str
    direction: str
    created_at: float
    result_digest: str


class HandoffStore:
    """Persist checksummed handoff metadata without raw payloads."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_handoff_envelopes (
                handoff_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                fr_id TEXT NOT NULL,
                todo_id TEXT NOT NULL,
                source_agent TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                context_json TEXT NOT NULL,
                payload_digest TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS agent_handoff_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                handoff_id TEXT NOT NULL,
                sender_agent TEXT NOT NULL,
                receiver_agent TEXT NOT NULL,
                direction TEXT NOT NULL,
                created_at REAL NOT NULL,
                result_digest TEXT NOT NULL,
                FOREIGN KEY (handoff_id) REFERENCES agent_handoff_envelopes(handoff_id)
            );
            """
        )
        self.connection.commit()

    def create_envelope(
        self,
        *,
        handoff_id: str,
        fr_id: str,
        todo_id: str,
        source_agent: str,
        target_agent: str,
        claim_id: str,
        created_at: float,
        context: Mapping[str, object],
    ) -> HandoffEnvelope:
        """Create or return an identical immutable envelope."""
        _validate_value(context)
        canonical_context = _canonical_json(context)
        digest = hashlib.sha256(canonical_context.encode("utf-8")).hexdigest()
        envelope = HandoffEnvelope(
            version=1,
            handoff_id=handoff_id,
            fr_id=fr_id,
            todo_id=todo_id,
            source_agent=source_agent,
            target_agent=target_agent,
            claim_id=claim_id,
            created_at=created_at,
            context=dict(context),
            payload_digest=digest,
        )
        row = self.connection.execute(
            "SELECT * FROM agent_handoff_envelopes WHERE handoff_id = ?",
            (handoff_id,),
        ).fetchone()
        if row is not None:
            existing = self._from_row(row)
            if existing != envelope:
                raise ValueError("handoff envelope is immutable")
            return existing
        self.connection.execute(
            """INSERT INTO agent_handoff_envelopes
               (handoff_id, version, fr_id, todo_id, source_agent, target_agent,
                claim_id, created_at, context_json, payload_digest)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (envelope.handoff_id, envelope.version, envelope.fr_id, envelope.todo_id,
             envelope.source_agent, envelope.target_agent, envelope.claim_id,
             envelope.created_at, canonical_context, envelope.payload_digest),
        )
        self.connection.commit()
        return envelope

    def publish_result(
        self,
        envelope: HandoffEnvelope,
        *,
        sender_agent: str,
        receiver_agent: str,
        direction: str,
        result: Mapping[str, object],
        created_at: float,
    ) -> HandoffResult:
        """Persist a directional result digest without the result payload."""
        if direction not in {"inbound", "outbound"}:
            raise ResultExchangeError("result direction must be inbound or outbound")
        stored_envelope = self.connection.execute(
            "SELECT source_agent, target_agent FROM agent_handoff_envelopes WHERE handoff_id = ?",
            (envelope.handoff_id,),
        ).fetchone()
        if stored_envelope is None:
            raise ResultExchangeError("handoff envelope does not exist")
        expected_sender, expected_receiver = (
            (stored_envelope["source_agent"], stored_envelope["target_agent"])
            if direction == "outbound"
            else (stored_envelope["target_agent"], stored_envelope["source_agent"])
        )
        if sender_agent != expected_sender:
            raise ResultExchangeError("sender is not authorized for handoff direction")
        if receiver_agent != expected_receiver:
            raise ResultExchangeError("receiver is not authorized for handoff direction")
        _validate_value(result, "result")
        digest = hashlib.sha256(_canonical_json(result).encode("utf-8")).hexdigest()
        cursor = self.connection.execute(
            """INSERT INTO agent_handoff_results
               (handoff_id, sender_agent, receiver_agent, direction, created_at, result_digest)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (envelope.handoff_id, sender_agent, receiver_agent, direction, created_at, digest),
        )
        self.connection.commit()
        return HandoffResult(cursor.lastrowid, envelope.handoff_id, sender_agent,
                             receiver_agent, direction, created_at, digest)

    def results(self, handoff_id: str) -> tuple[HandoffResult, ...]:
        """Return exchanged result metadata in durable insertion order."""
        rows = self.connection.execute(
            "SELECT * FROM agent_handoff_results WHERE handoff_id = ? ORDER BY result_id",
            (handoff_id,),
        ).fetchall()
        return tuple(HandoffResult(row["result_id"], row["handoff_id"], row["sender_agent"],
                                   row["receiver_agent"], row["direction"], row["created_at"],
                                   row["result_digest"]) for row in rows)

    @staticmethod
    def verify_envelope(envelope: HandoffEnvelope) -> str:
        """Return the digest recomputed from the envelope context."""
        _validate_value(envelope.context)
        return hashlib.sha256(_canonical_json(envelope.context).encode("utf-8")).hexdigest()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> HandoffEnvelope:
        return HandoffEnvelope(
            version=row["version"], handoff_id=row["handoff_id"], fr_id=row["fr_id"],
            todo_id=row["todo_id"], source_agent=row["source_agent"],
            target_agent=row["target_agent"], claim_id=row["claim_id"],
            created_at=row["created_at"], context=json.loads(row["context_json"]),
            payload_digest=row["payload_digest"],
        )


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _validate_value(value: object, path: str = "context") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _SENSITIVE.search(str(key)):
                raise SensitiveHandoffValueError(f"sensitive handoff field: {path}.{key}")
            _validate_value(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_value(item, f"{path}[{index}]")
    elif isinstance(value, str) and _SENSITIVE.search(value):
        raise SensitiveHandoffValueError(f"sensitive handoff value: {path}")