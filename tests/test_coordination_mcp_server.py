from __future__ import annotations

import asyncio
import json
import subprocess
import sqlite3
import sys
from pathlib import Path
import re
from collections.abc import Iterator
from typing import Any

import pytest


@pytest.fixture
def todo_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def _todo_config(
    *,
    max_retries: int = 1,
    takeover_enabled: bool = False,
    max_parallel_per_fr: int = 8,
    global_worker_capacity: int = 16,
    pre_fr_capacity: int = 16,
) -> Any:
    from src.utils.todo_operational_runtime import OperationalConfig

    return OperationalConfig(
        lease_seconds=30,
        max_retries=max_retries,
        takeover_enabled=takeover_enabled,
        max_parallel_per_fr=max_parallel_per_fr,
        global_worker_capacity=global_worker_capacity,
        pre_fr_capacity=pre_fr_capacity,
    )


def _invoke_todo(
    server: Any,
    connection: sqlite3.Connection,
    config: Any,
    operation: str,
    payload: dict[str, Any] | None = None,
) -> str:
    return server.invoke_coordination(
        operation, payload or {}, connection=connection, config=config
    )


def _claim_key(purpose: str) -> str:
    return f"claim-replay-{purpose}-" + "0" * 43


def test_todo_claim_and_get_operations_support_sqlcipher_connections() -> None:
    import sqlcipher3

    from src.utils import coordination_mcp_server

    connection = sqlcipher3.connect(":memory:")
    config = _todo_config()
    try:
        queued = json.loads(
            _invoke_todo(
                coordination_mcp_server,
                connection,
                config,
                "todo.register_queued",
                {
                    "todo_id": "sqlcipher-operation",
                    "fr_id": "FR-sqlcipher-operation",
                    "idempotency_key": "dispatch-sqlcipher-operation",
                },
            )
        )
        claimed = json.loads(
            _invoke_todo(
                coordination_mcp_server,
                connection,
                config,
                "todo.claim",
                {
                    "todo_id": "sqlcipher-operation",
                    "fr_id": "FR-sqlcipher-operation",
                    "worker_id": "worker-sqlcipher-operation",
                    "claim_idempotency_key": _claim_key("sqlcipher-operation"),
                },
            )
        )
        current = json.loads(
            _invoke_todo(
                coordination_mcp_server,
                connection,
                config,
                "todo.get",
                {"todo_id": "sqlcipher-operation"},
            )
        )

        assert queued["state"] == "queued"
        assert claimed["state"] == "claimed"
        assert claimed["lease_token"]
        assert current["state"] == "claimed"
        assert current["worker_id"] == "worker-sqlcipher-operation"
    finally:
        connection.close()


def test_todo_mcp_registry_exposes_only_fixed_lifecycle_inputs():
    from src.utils.coordination_mcp_server import mcp

    expected = {
        "todo_register_queued": ({"todo_id", "idempotency_key", "fr_id"}, {"todo_id", "idempotency_key"}),
        "todo_claim": (
            {"todo_id", "worker_id", "claim_idempotency_key", "fr_id"},
            {"todo_id", "worker_id", "claim_idempotency_key"},
        ),
        "todo_heartbeat": ({"todo_id", "worker_id", "lease_token"}, {"todo_id", "worker_id", "lease_token"}),
        "todo_fail": ({"todo_id", "worker_id", "lease_token", "error"}, {"todo_id", "worker_id", "lease_token", "error"}),
        "todo_retry": ({"todo_id"}, {"todo_id"}),
        "todo_cancel": ({"todo_id", "worker_id", "lease_token"}, {"todo_id", "worker_id", "lease_token"}),
        "todo_recover_stale": (set(), set()),
        "todo_takeover": ({"todo_id", "worker_id", "approved"}, {"todo_id", "worker_id", "approved"}),
        "todo_complete": (
            {"todo_id", "worker_id", "lease_token", "validated_handoff", "handoff_evidence"},
            {"todo_id", "worker_id", "lease_token", "validated_handoff", "handoff_evidence"},
        ),
        "todo_get": ({"todo_id"}, {"todo_id"}),
        "todo_events": ({"todo_id"}, {"todo_id"}),
    }
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    assert set(expected) <= set(tools)
    for name, (fields, required) in expected.items():
        schema = tools[name].inputSchema
        assert set(schema["properties"]) == fields
        assert set(schema.get("required", [])) == required
        assert not {"db", "sql", "state", "now", "max_retries"}.intersection(fields)


def test_todo_get_does_not_create_schema_or_commit(todo_connection):
    from src.utils import coordination_mcp_server
    from src.utils.todo_execution_lifecycle import ExecutionLifecycle

    class TrackingConnection(sqlite3.Connection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.commit_calls = 0
            self.executescript_calls = 0

        def commit(self):
            self.commit_calls += 1
            super().commit()

        def executescript(self, script):
            self.executescript_calls += 1
            return super().executescript(script)

    source = sqlite3.connect(":memory:")
    ExecutionLifecycle(source).register_queued(
        todo_id="todo-read-only",
        fr_id="FR-test",
        now=10.0,
        max_retries=1,
        idempotency_key="dispatch-read-only",
    )
    connection = sqlite3.connect(":memory:", factory=TrackingConnection)
    source.backup(connection)
    source.close()
    schema_before = [
        tuple(row)
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master ORDER BY name"
        ).fetchall()
    ]

    result = json.loads(
        _invoke_todo(
            coordination_mcp_server, connection, _todo_config(), "todo.get",
            {"todo_id": "todo-read-only"},
        )
    )

    assert result["state"] == "queued"
    assert [
        tuple(row)
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master ORDER BY name"
        ).fetchall()
    ] == schema_before
    assert connection.executescript_calls == 0
    assert connection.commit_calls == 0
    connection.close()


def test_coordination_server_imports_as_a_package_without_test_path_setup():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", "import src.utils.coordination_mcp_server"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_todo_queued_registration_uses_an_isolated_connection(monkeypatch):
    from src.utils import coordination_mcp_server

    connection = sqlite3.connect(":memory:")
    monkeypatch.setattr(
        coordination_mcp_server,
        "_open_todo_connection",
        lambda: connection,
        raising=False,
    )

    result = coordination_mcp_server.invoke_coordination(
        "todo.register_queued",
        {
            "todo_id": "todo-test-registration",
            "fr_id": "FR-test",
            "idempotency_key": "dispatch-test-registration",
        },
    )

    assert json.loads(result)["state"] == "queued"


def test_todo_registration_is_idempotent_and_retry_budget_is_policy_owned(todo_connection):
    from src.utils import coordination_mcp_server

    config = _todo_config(max_retries=2)
    payload = {
        "todo_id": "todo-idempotent",
        "fr_id": "FR-test",
        "idempotency_key": "dispatch-idempotent",
    }
    first = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, config,
                     "todo.register_queued", payload)
    )
    replay = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, config,
                     "todo.register_queued", payload)
    )

    assert first == replay
    assert first["state"] == "queued"
    assert first["max_retries"] == 2
    assert todo_connection.execute(
        "SELECT COUNT(*) FROM todo_execution_events WHERE todo_id = ?",
        ("todo-idempotent",),
    ).fetchone()[0] == 1
    from src.utils.todo_execution_lifecycle import DuplicateClaimError

    with pytest.raises(DuplicateClaimError):
        _invoke_todo(
            coordination_mcp_server, todo_connection, config,
            "todo.register_queued",
            {**payload, "idempotency_key": "different-dispatch"},
        )


def test_todo_claim_and_owned_transitions_use_server_generated_lease(todo_connection, monkeypatch):
    from src.utils import coordination_mcp_server
    from src.utils.todo_execution_lifecycle import LeaseOwnershipError

    config = _todo_config()
    monkeypatch.setattr(coordination_mcp_server.time, "time", lambda: 100.0)
    _invoke_todo(coordination_mcp_server, todo_connection, config,
                 "todo.register_queued",
                 {"todo_id": "todo-worker", "idempotency_key": "dispatch-worker"})
    with pytest.raises(ValueError, match="43-128 characters"):
        _invoke_todo(
            coordination_mcp_server, todo_connection, config, "todo.claim",
            {"todo_id": "todo-worker", "worker_id": "worker-a",
             "claim_idempotency_key": "too-short"},
        )
    claim_key = _claim_key("worker")
    claimed = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, config, "todo.claim",
                     {"todo_id": "todo-worker", "worker_id": "worker-a",
                      "claim_idempotency_key": claim_key})
    )
    lease_token = claimed["lease_token"]
    assert claimed["state"] == "claimed"
    assert len(lease_token) >= 40
    assert claimed["lease_expires_at"] == 130.0
    assert claimed["attempt"] == 1

    with pytest.raises(ValueError, match="missing required arguments"):
        _invoke_todo(
            coordination_mcp_server, todo_connection, config, "todo.claim",
            {"todo_id": "todo-worker", "worker_id": "worker-a"},
        )

    replayed_claim = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, config,
                     "todo.claim",
                     {"todo_id": "todo-worker", "worker_id": "worker-a",
                      "claim_idempotency_key": claim_key})
    )
    assert replayed_claim["lease_token"] == lease_token
    assert replayed_claim["claim_id"] == claimed["claim_id"]
    assert claim_key not in json.dumps(claimed)
    assert claim_key not in json.dumps(replayed_claim)
    from src.utils.todo_execution_lifecycle import DuplicateClaimError

    with pytest.raises(DuplicateClaimError):
        _invoke_todo(
            coordination_mcp_server, todo_connection, config, "todo.claim",
            {"todo_id": "todo-worker", "worker_id": "worker-a",
             "claim_idempotency_key": _claim_key("different")},
        )

    for operation, worker_id, supplied_token in (
        ("todo.heartbeat", "worker-b", lease_token),
        ("todo.heartbeat", "worker-a", "wrong"),
        ("todo.fail", "worker-b", lease_token),
        ("todo.cancel", "worker-b", lease_token),
        ("todo.complete", "worker-b", lease_token),
    ):
        payload = {
            "todo_id": "todo-worker",
            "worker_id": worker_id,
            "lease_token": supplied_token,
        }
        if operation == "todo.fail":
            payload["error"] = "failure"
        elif operation == "todo.complete":
            payload.update(validated_handoff=True, handoff_evidence="verified")
        with pytest.raises(LeaseOwnershipError):
            _invoke_todo(coordination_mcp_server, todo_connection, config,
                         operation, payload)

    running = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, config,
                     "todo.heartbeat",
                     {"todo_id": "todo-worker", "worker_id": "worker-a",
                      "lease_token": lease_token})
    )
    assert running["state"] == "running"
    with pytest.raises(ValueError, match="validated handoff"):
        _invoke_todo(
            coordination_mcp_server, todo_connection, config, "todo.complete",
            {"todo_id": "todo-worker", "worker_id": "worker-a",
             "lease_token": lease_token, "validated_handoff": False,
             "handoff_evidence": "branch and worktree verified"},
        )
    for evidence in ("", "   "):
        with pytest.raises(ValueError, match="handoff_evidence"):
            _invoke_todo(
                coordination_mcp_server, todo_connection, config, "todo.complete",
                {"todo_id": "todo-worker", "worker_id": "worker-a",
                 "lease_token": lease_token, "validated_handoff": True,
                 "handoff_evidence": evidence},
            )

    completed = json.loads(
        _invoke_todo(
            coordination_mcp_server, todo_connection, config, "todo.complete",
            {"todo_id": "todo-worker", "worker_id": "worker-a",
             "lease_token": lease_token, "validated_handoff": True,
             "handoff_evidence": "branch and worktree verified"},
        )
    )
    assert completed["state"] == "completed"
    assert completed["validated_handoff"] is True
    assert "lease_token" not in completed

    ordinary_read = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, config,
                     "todo.get", {"todo_id": "todo-worker"})
    )
    assert "lease_token" not in ordinary_read
    assert lease_token not in json.dumps(ordinary_read)
    assert claim_key not in json.dumps(ordinary_read)
    event_read = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, config,
                     "todo.events", {"todo_id": "todo-worker"})
    )
    assert lease_token not in json.dumps(event_read)
    assert claim_key not in json.dumps(event_read)


def test_todo_claim_requires_prior_queued_registration(todo_connection):
    from src.utils import coordination_mcp_server
    from src.utils.todo_execution_lifecycle import InvalidTransitionError

    with pytest.raises(InvalidTransitionError, match="queued registration"):
        _invoke_todo(
            coordination_mcp_server, todo_connection, _todo_config(), "todo.claim",
            {"todo_id": "todo-unregistered", "worker_id": "worker-a",
             "claim_idempotency_key": _claim_key("unregistered")},
        )


@pytest.mark.parametrize(
    ("max_parallel_per_fr", "global_worker_capacity", "pre_fr_capacity", "fr_ids"),
    [
        (1, 2, 2, ("FR-test", "FR-test")),
        (2, 1, 2, ("FR-one", "FR-two")),
        (2, 2, 1, (None, None)),
    ],
)
def test_todo_claim_enforces_server_policy_capacity(
    todo_connection,
    max_parallel_per_fr,
    global_worker_capacity,
    pre_fr_capacity,
    fr_ids,
):
    from src.utils import coordination_mcp_server
    from src.utils.todo_execution_lifecycle import LifecycleError

    config = _todo_config(
        max_parallel_per_fr=max_parallel_per_fr,
        global_worker_capacity=global_worker_capacity,
        pre_fr_capacity=pre_fr_capacity,
    )
    for todo_id, fr_id in zip(("todo-capacity-a", "todo-capacity-b"), fr_ids):
        _invoke_todo(
            coordination_mcp_server,
            todo_connection,
            config,
            "todo.register_queued",
            {
                "todo_id": todo_id,
                "fr_id": fr_id,
                "idempotency_key": f"dispatch-{todo_id}",
            },
        )

    _invoke_todo(
        coordination_mcp_server,
        todo_connection,
        config,
        "todo.claim",
        {
            "todo_id": "todo-capacity-a",
            "worker_id": "worker-a",
            "claim_idempotency_key": _claim_key("capacity-a"),
        },
    )
    with pytest.raises(LifecycleError, match="capacity"):
        _invoke_todo(
            coordination_mcp_server,
            todo_connection,
            config,
            "todo.claim",
            {
                "todo_id": "todo-capacity-b",
                "worker_id": "worker-b",
                "claim_idempotency_key": _claim_key("capacity-b"),
            },
        )


def test_todo_failure_retry_and_cancellation_follow_bounded_policy(todo_connection, monkeypatch):
    from src.utils import coordination_mcp_server
    from src.utils.todo_execution_lifecycle import RetryExhaustedError

    config = _todo_config(max_retries=1)
    monkeypatch.setattr(coordination_mcp_server.time, "time", lambda: 100.0)
    _invoke_todo(coordination_mcp_server, todo_connection, config,
                 "todo.register_queued",
                 {"todo_id": "todo-failure", "idempotency_key": "dispatch-failure"})
    for attempt in (1, 2):
        claimed = json.loads(
            _invoke_todo(coordination_mcp_server, todo_connection, config, "todo.claim",
                         {"todo_id": "todo-failure", "worker_id": "worker-a",
                                                    "claim_idempotency_key": _claim_key(f"failure-{attempt}")})
        )
        assert claimed["max_retries"] == 1
        if attempt == 1:
            with pytest.raises(ValueError, match="lease credentials"):
                _invoke_todo(
                    coordination_mcp_server, todo_connection, config, "todo.fail",
                    {"todo_id": "todo-failure", "worker_id": "worker-a",
                     "lease_token": claimed["lease_token"],
                     "error": claimed["lease_token"]},
                )
        failed = json.loads(
            _invoke_todo(
                coordination_mcp_server, todo_connection, config, "todo.fail",
                {"todo_id": "todo-failure", "worker_id": "worker-a",
                 "lease_token": claimed["lease_token"], "error": "worker failed"},
            )
        )
        assert failed["state"] == "failed"
        if attempt == 1:
            assert json.loads(
                _invoke_todo(coordination_mcp_server, todo_connection, config,
                             "todo.retry", {"todo_id": "todo-failure"})
            )["state"] == "queued"
    with pytest.raises(RetryExhaustedError):
        _invoke_todo(coordination_mcp_server, todo_connection, config,
                     "todo.retry", {"todo_id": "todo-failure"})

    _invoke_todo(coordination_mcp_server, todo_connection, config,
                 "todo.register_queued",
                 {"todo_id": "todo-cancel", "idempotency_key": "dispatch-cancel"})
    cancel_claim = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, config, "todo.claim",
                     {"todo_id": "todo-cancel", "worker_id": "worker-a",
                      "claim_idempotency_key": _claim_key("cancel")})
    )
    cancelled = json.loads(
        _invoke_todo(
            coordination_mcp_server, todo_connection, config, "todo.cancel",
            {"todo_id": "todo-cancel", "worker_id": "worker-a",
             "lease_token": cancel_claim["lease_token"]},
        )
    )
    assert cancelled["state"] == "cancelled"


def test_todo_stale_recovery_and_takeover_require_policy_and_approval(todo_connection, monkeypatch):
    from src.utils import coordination_mcp_server

    enabled = _todo_config(takeover_enabled=True)
    disabled = _todo_config(takeover_enabled=False)
    now = [100.0]
    monkeypatch.setattr(coordination_mcp_server.time, "time", lambda: now[0])
    _invoke_todo(coordination_mcp_server, todo_connection, enabled,
                 "todo.register_queued",
                 {"todo_id": "todo-stale", "idempotency_key": "dispatch-stale"})
    first_claim = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, enabled, "todo.claim",
                     {"todo_id": "todo-stale", "worker_id": "worker-a",
                      "claim_idempotency_key": _claim_key("stale")})
    )
    now[0] = 131.0
    assert json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, enabled,
                     "todo.recover_stale")
    ) == ["todo-stale"]
    takeover_payload = {"todo_id": "todo-stale", "worker_id": "worker-b", "approved": True}
    with pytest.raises(PermissionError, match="policy"):
        _invoke_todo(coordination_mcp_server, todo_connection, disabled,
                     "todo.takeover", takeover_payload)
    with pytest.raises(PermissionError, match="approval"):
        _invoke_todo(coordination_mcp_server, todo_connection, enabled, "todo.takeover",
                     {**takeover_payload, "approved": False})

    resumed = json.loads(
        _invoke_todo(coordination_mcp_server, todo_connection, enabled,
                     "todo.takeover", takeover_payload)
    )
    assert resumed["state"] == "claimed"
    assert resumed["worker_id"] == "worker-b"
    assert resumed["lease_token"] != first_claim["lease_token"]
    assert resumed["lease_expires_at"] == 161.0


@pytest.mark.parametrize(
    ("max_parallel_per_fr", "global_worker_capacity", "pre_fr_capacity", "fr_ids"),
    [
        (1, 2, 2, ("FR-test", "FR-test")),
        (2, 1, 2, ("FR-one", "FR-two")),
        (2, 2, 1, (None, None)),
    ],
)
def test_todo_takeover_enforces_server_policy_capacity(
    todo_connection,
    monkeypatch,
    max_parallel_per_fr,
    global_worker_capacity,
    pre_fr_capacity,
    fr_ids,
):
    from src.utils import coordination_mcp_server
    from src.utils.todo_execution_lifecycle import CapacityLimitError

    config = _todo_config(
        takeover_enabled=True,
        max_parallel_per_fr=max_parallel_per_fr,
        global_worker_capacity=global_worker_capacity,
        pre_fr_capacity=pre_fr_capacity,
    )
    now = [100.0]
    monkeypatch.setattr(coordination_mcp_server.time, "time", lambda: now[0])
    todo_ids = ("todo-takeover-stale", "todo-takeover-capacity")
    for todo_id, fr_id in zip(todo_ids, fr_ids):
        _invoke_todo(
            coordination_mcp_server,
            todo_connection,
            config,
            "todo.register_queued",
            {
                "todo_id": todo_id,
                "fr_id": fr_id,
                "idempotency_key": f"dispatch-{todo_id}",
            },
        )

    _invoke_todo(
        coordination_mcp_server,
        todo_connection,
        config,
        "todo.claim",
        {
            "todo_id": todo_ids[0],
            "worker_id": "worker-stale",
            "claim_idempotency_key": _claim_key("takeover-stale"),
        },
    )
    now[0] = 131.0
    _invoke_todo(coordination_mcp_server, todo_connection, config, "todo.recover_stale")
    _invoke_todo(
        coordination_mcp_server,
        todo_connection,
        config,
        "todo.claim",
        {
            "todo_id": todo_ids[1],
            "worker_id": "worker-capacity",
            "claim_idempotency_key": _claim_key("takeover-capacity"),
        },
    )

    with pytest.raises(CapacityLimitError, match="capacity"):
        _invoke_todo(
            coordination_mcp_server,
            todo_connection,
            config,
            "todo.takeover",
            {"todo_id": todo_ids[0], "worker_id": "worker-new", "approved": True},
        )


@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        ("todo.register_queued", {"todo_id": "todo-x", "idempotency_key": "dispatch-x", "max_retries": 99}),
        ("todo.claim", {"todo_id": "todo-x", "worker_id": "worker-a", "now": 1}),
        ("todo.claim", {"todo_id": "todo-x", "worker_id": "worker-a", "db": "production"}),
        ("todo.heartbeat", {"todo_id": "todo-x", "worker_id": "worker-a", "lease_token": "x", "sql": "UPDATE"}),
        ("todo.retry", {"todo_id": "todo-x", "max_retries": 100}),
    ],
)
def test_todo_operations_reject_caller_controlled_policy_or_arbitrary_args(
    todo_connection, operation, payload
):
    from src.utils import coordination_mcp_server

    with pytest.raises(ValueError, match="arguments"):
        _invoke_todo(
            coordination_mcp_server, todo_connection, _todo_config(), operation, payload
        )


def test_todo_dispatch_rejects_generic_state_mutation(todo_connection):
    from src.utils import coordination_mcp_server

    with pytest.raises(ValueError, match="unsupported coordination operation"):
        _invoke_todo(
            coordination_mcp_server, todo_connection, _todo_config(),
            "todo.set_state", {"todo_id": "todo-x", "state": "completed"},
        )


def test_fr_event_operation_delegates_to_canonical_fr_cli(monkeypatch):
    from src.utils.coordination_mcp_server import invoke_coordination

    calls: list[tuple[str, dict]] = []

    def fake_run(operation: str, payload: dict) -> str:
        calls.append((operation, payload))
        return "event recorded"

    monkeypatch.setattr(
        "src.utils.coordination_mcp_server._run_fr_cli", fake_run
    )

    result = invoke_coordination(
        "fr.record_event",
        {
            "fr_id": "FR-20260809-example",
            "agent": "test-agent",
            "event_type": "finding",
            "summary": "coverage recorded",
        },
    )

    assert result == "event recorded"
    assert calls == [
        (
            "fr.record_event",
            {
                "fr_id": "FR-20260809-example",
                "agent": "test-agent",
                "event_type": "finding",
                "summary": "coverage recorded",
            },
        )
    ]


def test_cost_reconciliation_operation_delegates_fixed_arguments(monkeypatch):
    from src.utils.coordination_mcp_server import invoke_coordination

    calls: list[tuple[str, dict]] = []

    def fake_run(operation: str, payload: dict) -> str:
        calls.append((operation, payload))
        return "cost reconciliation recorded"

    monkeypatch.setattr(
        "src.utils.coordination_mcp_server._run_fr_cli", fake_run
    )

    result = invoke_coordination(
        "fr.reconcile_cost_unavailable",
        {
            "fr_id": "FR-20260912-workspace-server-startup-supervisor",
            "source": "historical-operator-reconciliation",
            "reason": "No retained usage payload",
        },
    )

    assert result == "cost reconciliation recorded"
    assert calls == [
        (
            "fr.reconcile_cost_unavailable",
            {
                "fr_id": "FR-20260912-workspace-server-startup-supervisor",
                "source": "historical-operator-reconciliation",
                "reason": "No retained usage payload",
            },
        )
    ]


def test_unknown_operation_is_rejected():
    from src.utils.coordination_mcp_server import invoke_coordination

    with pytest.raises(ValueError, match="unsupported coordination operation"):
        invoke_coordination("db.read_query", {})


def test_fr_cli_command_mapping_is_fixed(monkeypatch):
    from src.utils import coordination_mcp_server

    captured: dict[str, object] = {}

    class Result:
        stdout = "artifact recorded\n"

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(coordination_mcp_server.subprocess, "run", fake_run)

    result = coordination_mcp_server._run_fr_cli(
        "fr.record_artifact",
        {
            "fr_id": "FR-20260809-example",
            "artifact_type": "test_pass",
            "label": "focused tests",
            "path": "tests/test_coordination_mcp_server.py",
        },
    )

    assert result == "artifact recorded"
    assert captured["args"] == [
        coordination_mcp_server.sys.executable,
        str(coordination_mcp_server.FR_CLI_PATH),
        "record-artifact",
        "FR-20260809-example",
        "test_pass",
        "focused tests",
        "--path",
        "tests/test_coordination_mcp_server.py",
    ]


def test_fr_cli_subprocess_has_ten_second_timeout(monkeypatch):
    from src.utils import coordination_mcp_server

    captured: dict[str, object] = {}

    class Result:
        stdout = "fr details\n"

    def fake_run(args, **kwargs):
        captured["kwargs"] = kwargs
        if kwargs.get("timeout") != 10:
            raise coordination_mcp_server.subprocess.TimeoutExpired(args, 10)
        return Result()

    monkeypatch.setattr(coordination_mcp_server.subprocess, "run", fake_run)

    result = coordination_mcp_server._run_fr_cli(
        "fr.get", {"fr_id": "FR-20260811-example"}
    )

    assert result == "fr details"
    assert captured["kwargs"]["timeout"] == 10


def test_fr_cli_subprocess_preserves_non_zero_failure(monkeypatch):
    from src.utils import coordination_mcp_server

    expected = coordination_mcp_server.subprocess.CalledProcessError(
        2, ["fr_cli.py", "get", "FR-20260811-example"]
    )

    def fake_run(args, **kwargs):
        assert kwargs["check"] is True
        raise expected

    monkeypatch.setattr(coordination_mcp_server.subprocess, "run", fake_run)

    with pytest.raises(coordination_mcp_server.subprocess.CalledProcessError) as error:
        coordination_mcp_server._run_fr_cli(
            "fr.get", {"fr_id": "FR-20260811-example"}
        )

    assert error.value is expected


@pytest.mark.parametrize("field", ["db", "sql"])
def test_arbitrary_database_and_sql_inputs_are_rejected(field: str):
    from src.utils.coordination_mcp_server import invoke_coordination

    with pytest.raises(ValueError, match="database and SQL arguments are not supported"):
        invoke_coordination(
            "fr.record_event",
            {
                "fr_id": "FR-20260809-example",
                "agent": "test-agent",
                "event_type": "finding",
                "summary": "coverage recorded",
                field: "SELECT * FROM anything",
            },
        )


def test_coordination_mcp_docs_define_deterministic_routing_and_fallback():
    repo_root = Path(__file__).resolve().parents[1]
    registry = (repo_root / "MCP_REGISTRY.md").read_text(encoding="utf-8")
    instructions = (
        repo_root / ".github" / "instructions" / "feature-request-flow.instructions.md"
    ).read_text(encoding="utf-8")
    registry = re.sub(r"\s+", " ", registry)
    instructions = re.sub(r"\s+", " ", instructions)

    required_phrases = (
        "deterministic MCP-first invocation",
        "fixed allowlisted operations",
        "explicit local fallback",
        "coordination MCP is unavailable",
    )
    for phrase in required_phrases:
        assert phrase in registry
        assert phrase in instructions