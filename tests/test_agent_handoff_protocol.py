from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from todo_execution_contracts import TodoContract
from todo_operational_runtime import OperationalRuntime
from agent_handoff_protocol import (
    HandoffStore,
    ResultExchangeError,
    SensitiveHandoffValueError,
    TakeoverNotAllowedError,
)
from todo_execution_lifecycle import LeaseOwnershipError


def test_handoff_envelope_is_versioned_checksummed_and_immutable() -> None:
    store = HandoffStore(sqlite3.connect(":memory:"))

    envelope = store.create_envelope(
        handoff_id="handoff-1",
        fr_id="FR-1",
        todo_id="todo-1",
        source_agent="agent-a",
        target_agent="agent-b",
        claim_id="claim-1",
        created_at=100.0,
        context={"state": "running", "attempt": 1},
    )

    assert envelope.version == 1
    assert envelope.payload_digest == store.verify_envelope(envelope)
    assert store.create_envelope(
        handoff_id="handoff-1",
        fr_id="FR-1",
        todo_id="todo-1",
        source_agent="agent-a",
        target_agent="agent-b",
        claim_id="claim-1",
        created_at=100.0,
        context={"state": "running", "attempt": 1},
    ) == envelope
    with pytest.raises(ValueError, match="immutable"):
        store.create_envelope(
            handoff_id="handoff-1",
            fr_id="FR-1",
            todo_id="todo-1",
            source_agent="agent-a",
            target_agent="agent-b",
            claim_id="claim-1",
            created_at=100.0,
            context={"state": "failed", "attempt": 1},
        )


@pytest.mark.parametrize("context", [{"health": "stable"}, {"api_token": "abc"}])
def test_handoff_rejects_sensitive_values_without_persisting_payload(context: dict[str, object]) -> None:
    connection = sqlite3.connect(":memory:")
    store = HandoffStore(connection)

    with pytest.raises(SensitiveHandoffValueError):
        store.create_envelope(
            handoff_id="handoff-1",
            fr_id="FR-1",
            todo_id="todo-1",
            source_agent="agent-a",
            target_agent="agent-b",
            claim_id="claim-1",
            created_at=100.0,
            context=context,
        )

    columns = {row[1] for row in connection.execute("PRAGMA table_info(agent_handoff_envelopes)")}
    assert "payload" not in columns


def test_results_exchange_is_bidirectional_and_durable_without_raw_result() -> None:
    connection = sqlite3.connect(":memory:")
    store = HandoffStore(connection)
    envelope = store.create_envelope(
        handoff_id="handoff-1", fr_id="FR-1", todo_id="todo-1",
        source_agent="agent-a", target_agent="agent-b", claim_id="claim-1",
        created_at=100.0, context={"state": "running"},
    )

    outbound = store.publish_result(
        envelope, sender_agent="agent-a", receiver_agent="agent-b",
        direction="outbound", result={"status": "completed", "attempt": 1},
        created_at=110.0,
    )
    inbound = store.publish_result(
        envelope, sender_agent="agent-b", receiver_agent="agent-a",
        direction="inbound", result={"status": "acknowledged", "attempt": 1},
        created_at=111.0,
    )

    assert [item.direction for item in store.results(envelope.handoff_id)] == ["outbound", "inbound"]
    assert outbound.result_digest != inbound.result_digest
    columns = {row[1] for row in connection.execute("PRAGMA table_info(agent_handoff_results)")}
    assert "result" not in columns

    with pytest.raises(ResultExchangeError):
        store.publish_result(
            envelope, sender_agent="agent-a", receiver_agent="agent-b",
            direction="sideways", result={"status": "completed"}, created_at=112.0,
        )


def test_results_require_authorized_endpoints_for_each_direction() -> None:
    store = HandoffStore(sqlite3.connect(":memory:"))
    envelope = store.create_envelope(
        handoff_id="handoff-1", fr_id="FR-1", todo_id="todo-1",
        source_agent="agent-a", target_agent="agent-b", claim_id="claim-1",
        created_at=100.0, context={"state": "running"},
    )

    with pytest.raises(ResultExchangeError, match="sender is not authorized"):
        store.publish_result(
            envelope, sender_agent="agent-x", receiver_agent="agent-b",
            direction="outbound", result={"status": "completed"}, created_at=110.0,
        )
    with pytest.raises(ResultExchangeError, match="receiver is not authorized"):
        store.publish_result(
            envelope, sender_agent="agent-b", receiver_agent="agent-x",
            direction="inbound", result={"status": "acknowledged"}, created_at=111.0,
        )


def test_results_reject_unknown_envelope_deterministically() -> None:
    store = HandoffStore(sqlite3.connect(":memory:"))
    envelope = store.create_envelope(
        handoff_id="handoff-missing", fr_id="FR-1", todo_id="todo-1",
        source_agent="agent-a", target_agent="agent-b", claim_id="claim-1",
        created_at=100.0, context={"state": "running"},
    )
    store.connection.execute("DELETE FROM agent_handoff_envelopes")
    store.connection.commit()

    with pytest.raises(ResultExchangeError, match="handoff envelope does not exist"):
        store.publish_result(
            envelope, sender_agent="agent-a", receiver_agent="agent-b",
            direction="outbound", result={"status": "completed"}, created_at=110.0,
        )


def test_runtime_owns_handoff_and_result_exchange_across_restart() -> None:
    connection = sqlite3.connect(":memory:")
    runtime = OperationalRuntime(
        connection, (TodoContract(todo_id="todo-1", fr_id="FR-1"),)
    )
    record = runtime.dispatch(now=100.0)[0]
    envelope = runtime.create_handoff(record, target_agent="agent-b", created_at=105.0)
    runtime.publish_result(
        envelope, sender_agent="worker-1", receiver_agent="agent-b",
        direction="outbound", result={"status": "completed"}, created_at=110.0,
    )

    restarted = OperationalRuntime(
        connection, (TodoContract(todo_id="todo-1", fr_id="FR-1"),)
    )
    assert len(restarted.handoff_results(envelope.handoff_id)) == 1


def test_runtime_rejects_fabricated_execution_record_before_handoff_persistence() -> None:
    connection = sqlite3.connect(":memory:")
    runtime = OperationalRuntime(
        connection, (TodoContract(todo_id="todo-1", fr_id="FR-1"),)
    )
    record = runtime.dispatch(now=100.0)[0]
    fabricated = replace(record, claim_id="claim-fabricated")

    with pytest.raises(LeaseOwnershipError, match="does not match current persisted execution"):
        runtime.create_handoff(fabricated, target_agent="agent-b", created_at=105.0)

    assert connection.execute("SELECT COUNT(*) FROM agent_handoff_envelopes").fetchone()[0] == 0


def test_runtime_rejects_stale_execution_record_after_claim_replacement() -> None:
    connection = sqlite3.connect(":memory:")
    runtime = OperationalRuntime(
        connection,
        (TodoContract(todo_id="todo-1", fr_id="FR-1"),),
        policy={
            "max_parallel_todos_per_fr": 1,
            "max_total_todo_workers": 1,
            "lease_seconds": 10,
            "max_retries": 1,
            "takeover_enabled": True,
        },
    )
    record = runtime.dispatch(now=100.0)[0]
    runtime.recover_stale(now=110.0)
    runtime.takeover_resume(
        todo_id=record.todo_id, worker_id="worker-b", claim_id="claim-b",
        lease_token="lease-b", now=111.0, approved=True,
    )

    with pytest.raises(LeaseOwnershipError, match="does not match current persisted execution"):
        runtime.create_handoff(record, target_agent="agent-b", created_at=112.0)


def test_handoff_schema_survives_file_close_reopen_and_enforces_foreign_keys(tmp_path) -> None:
    database_path = tmp_path / "handoff.sqlite3"
    connection = sqlite3.connect(database_path)
    runtime = OperationalRuntime(
        connection, (TodoContract(todo_id="todo-1", fr_id="FR-1"),)
    )
    record = runtime.dispatch(now=100.0)[0]
    envelope = runtime.create_handoff(record, target_agent="agent-b", created_at=105.0)
    runtime.publish_result(
        envelope, sender_agent="worker-1", receiver_agent="agent-b",
        direction="outbound", result={"status": "completed"}, created_at=110.0,
    )
    connection.close()

    reopened = sqlite3.connect(database_path)
    restarted = OperationalRuntime(
        reopened, (TodoContract(todo_id="todo-1", fr_id="FR-1"),)
    )

    assert reopened.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert restarted.lifecycle.get("todo-1").claim_id == record.claim_id
    assert len(restarted.handoff_results(envelope.handoff_id)) == 1
    with pytest.raises(sqlite3.IntegrityError):
        reopened.execute(
            "INSERT INTO agent_handoff_results "
            "(handoff_id, sender_agent, receiver_agent, direction, created_at, result_digest) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("handoff-missing", "worker-1", "agent-b", "outbound", 120.0, "digest"),
        )


def test_handoff_schema_migration_is_additive_for_existing_database_content(tmp_path) -> None:
    database_path = tmp_path / "existing.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE existing_marker (value TEXT NOT NULL)")
    connection.execute("INSERT INTO existing_marker (value) VALUES ('preserved')")
    connection.commit()
    connection.close()

    migrated = sqlite3.connect(database_path)
    OperationalRuntime(migrated, ())

    assert migrated.execute("SELECT value FROM existing_marker").fetchone()[0] == "preserved"
    tables = {
        row[0]
        for row in migrated.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {
        "todo_execution_lifecycle",
        "todo_execution_events",
        "todo_execution_stale_recoveries",
        "agent_handoff_envelopes",
        "agent_handoff_results",
    } <= tables


def test_takeover_resume_requires_policy_and_explicit_approval() -> None:
    runtime = OperationalRuntime(
        sqlite3.connect(":memory:"),
        (TodoContract(todo_id="todo-1", fr_id="FR-1"),),
        policy={
            "max_parallel_todos_per_fr": 1,
            "max_total_todo_workers": 1,
            "lease_seconds": 10,
            "max_retries": 1,
            "takeover_enabled": True,
        },
    )
    record = runtime.dispatch(now=100.0)[0]
    runtime.recover_stale(now=110.0)

    with pytest.raises(TakeoverNotAllowedError):
        runtime.takeover_resume(
            todo_id=record.todo_id, worker_id="worker-b", claim_id="claim-b",
            lease_token="lease-b", now=111.0, approved=False,
        )

    resumed = runtime.takeover_resume(
        todo_id=record.todo_id, worker_id="worker-b", claim_id="claim-b",
        lease_token="lease-b", now=111.0, approved=True,
    )
    assert resumed.state == "claimed"
    assert resumed.worker_id == "worker-b"
    assert runtime.lifecycle.get(record.todo_id).claim_id == "claim-b"