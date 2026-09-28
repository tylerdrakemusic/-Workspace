"""Governed MCP operations for the workspace FR ledger."""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from mcp.server.fastmcp import FastMCP

try:
    from .todo_execution_lifecycle import (
        ExecutionLifecycle,
        ExecutionRecord,
        InvalidTransitionError,
    )
except ImportError:
    from todo_execution_lifecycle import (
        ExecutionLifecycle,
        ExecutionRecord,
        InvalidTransitionError,
    )

FR_CLI_PATH = Path(__file__).with_name("fr_cli.py")
_ALLOWED_OPERATIONS = frozenset(
    {
        "fr.get",
        "fr.record_event",
        "fr.record_artifact",
        "fr.reconcile_cost_unavailable",
    }
)
_TODO_ALLOWED_OPERATIONS = frozenset(
    {
        "todo.register_queued",
        "todo.claim",
        "todo.heartbeat",
        "todo.fail",
        "todo.retry",
        "todo.cancel",
        "todo.recover_stale",
        "todo.takeover",
        "todo.complete",
        "todo.get",
        "todo.events",
    }
)
_FORBIDDEN_ARGUMENTS = frozenset({"db", "sql"})
_TODO_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "todo_execution_policy.json"
_TODO_ARGUMENTS = {
    "todo.register_queued": ({"todo_id", "idempotency_key"}, {"fr_id"}),
    "todo.claim": (
        {"todo_id", "worker_id", "claim_idempotency_key"},
        {"fr_id"},
    ),
    "todo.heartbeat": ({"todo_id", "worker_id", "lease_token"}, set()),
    "todo.fail": ({"todo_id", "worker_id", "lease_token", "error"}, set()),
    "todo.retry": ({"todo_id"}, set()),
    "todo.cancel": ({"todo_id", "worker_id", "lease_token"}, set()),
    "todo.recover_stale": (set(), set()),
    "todo.takeover": ({"todo_id", "worker_id", "approved"}, set()),
    "todo.complete": (
        {"todo_id", "worker_id", "lease_token", "validated_handoff", "handoff_evidence"},
        set(),
    ),
    "todo.get": ({"todo_id"}, set()),
    "todo.events": ({"todo_id"}, set()),
}


@dataclass(frozen=True)
class _TodoLifecyclePolicy:
    max_parallel_per_fr: int
    global_worker_capacity: int
    pre_fr_capacity: int
    lease_seconds: int
    max_retries: int
    takeover_enabled: bool


def _load_todo_policy() -> _TodoLifecyclePolicy:
    policy = json.loads(_TODO_POLICY_PATH.read_text(encoding="utf-8"))
    required = {
        "max_parallel_todos_per_fr",
        "max_total_todo_workers",
        "lease_seconds",
        "max_retries",
    }
    allowed = required | {"pre_fr_capacity", "takeover_enabled", "tuning"}
    if not isinstance(policy, dict) or required - set(policy) or set(policy) - allowed:
        raise ValueError("TODO execution policy has an invalid shape")
    if any(type(policy[key]) is not int for key in required):
        raise ValueError("TODO execution policy limits must be integers")
    pre_fr_capacity = policy.get("pre_fr_capacity", policy["max_total_todo_workers"])
    if type(pre_fr_capacity) is not int:
        raise ValueError("TODO execution policy pre_fr_capacity must be an integer")
    if (
        policy["lease_seconds"] <= 0
        or policy["max_retries"] < 0
        or policy["max_parallel_todos_per_fr"] <= 0
        or policy["max_total_todo_workers"] <= 0
        or pre_fr_capacity <= 0
    ):
        raise ValueError("TODO execution policy limits are invalid")
    takeover_enabled = policy.get("takeover_enabled", False)
    if type(takeover_enabled) is not bool:
        raise ValueError("TODO execution policy takeover_enabled must be boolean")
    return _TodoLifecyclePolicy(
        max_parallel_per_fr=policy["max_parallel_todos_per_fr"],
        global_worker_capacity=policy["max_total_todo_workers"],
        pre_fr_capacity=pre_fr_capacity,
        lease_seconds=policy["lease_seconds"],
        max_retries=policy["max_retries"],
        takeover_enabled=takeover_enabled,
    )


def _run_fr_cli(operation: str, payload: dict[str, Any]) -> str:
    """Run one fixed fr_cli command; callers cannot supply a command or SQL."""
    if operation == "fr.get":
        args = ["get", payload["fr_id"]]
    elif operation == "fr.record_event":
        args = [
            "record-event",
            payload["fr_id"],
            payload["agent"],
            payload["event_type"],
            payload["summary"],
        ]
    elif operation == "fr.record_artifact":
        args = [
            "record-artifact",
            payload["fr_id"],
            payload["artifact_type"],
            payload["label"],
        ]
    else:
        args = [
            "cost-reconcile-unavailable",
            payload["fr_id"],
            "--source",
            payload["source"],
            "--reason",
            payload["reason"],
        ]
    if operation == "fr.record_artifact" and payload.get("path"):
        args.extend(["--path", payload["path"]])
    result = subprocess.run(  # nosec B603 — executable and arguments are fixed above
        [sys.executable, str(FR_CLI_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=10,
    )
    return result.stdout.strip()


def _open_todo_connection():
    """Open the canonical encrypted workspace database."""
    try:
        from . import init_db
    except ImportError:
        import init_db

    init_db.use_worktree_aware_db_path(Path(__file__).resolve().parents[2])
    return init_db.get_connection()


def _required_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _required_claim_idempotency_key(payload: Mapping[str, Any]) -> str:
    value = _required_string(payload, "claim_idempotency_key")
    if not 43 <= len(value) <= 128:
        raise ValueError("claim_idempotency_key must be 43-128 characters")
    return value


def _record_payload(record: ExecutionRecord, *, include_lease_token: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "todo_id": record.todo_id,
        "fr_id": record.fr_id,
        "worker_id": record.worker_id,
        "claim_id": record.claim_id,
        "state": record.state,
        "lease_expires_at": record.lease_expires_at,
        "heartbeat_at": record.heartbeat_at,
        "attempt": record.attempt,
        "max_retries": record.max_retries,
        "validated_handoff": record.validated_handoff,
        "handoff_evidence": record.handoff_evidence,
    }
    if include_lease_token:
        payload["lease_token"] = record.lease_token
    return payload


def _run_todo_operation(
    operation: str,
    payload: Mapping[str, Any],
    *,
    connection: Any | None = None,
    config: Any | None = None,
) -> str:
    owns_connection = connection is None
    if connection is None:
        connection = _open_todo_connection()
    if config is None:
        config = _load_todo_policy()
    read_only = operation in {"todo.get", "todo.events"}
    lifecycle = (
        ExecutionLifecycle.read_only(connection)
        if read_only
        else ExecutionLifecycle(connection)
    )
    try:
        now = time.time()
        if operation == "todo.register_queued":
            record = lifecycle.register_queued(
                todo_id=_required_string(payload, "todo_id"),
                fr_id=payload.get("fr_id"),
                now=now,
                max_retries=config.max_retries,
                idempotency_key=_required_string(payload, "idempotency_key"),
            )
            result: Any = _record_payload(record)
        elif operation == "todo.claim":
            worker_id = _required_string(payload, "worker_id")
            try:
                queued_record = lifecycle.get(_required_string(payload, "todo_id"))
            except KeyError as error:
                raise InvalidTransitionError(
                    "claim requires queued registration"
                ) from error
            requested_fr_id = payload.get("fr_id")
            if queued_record.fr_id and requested_fr_id and queued_record.fr_id != requested_fr_id:
                raise ValueError("fr_id does not match the queued TODO registration")
            record = lifecycle.claim(
                todo_id=queued_record.todo_id,
                fr_id=queued_record.fr_id or requested_fr_id,
                worker_id=worker_id,
                claim_id=uuid.uuid4().hex,
                lease_token=secrets.token_urlsafe(32),
                now=now,
                lease_seconds=config.lease_seconds,
                max_retries=config.max_retries,
                idempotency_key=_required_claim_idempotency_key(payload),
                max_parallel_per_fr=config.max_parallel_per_fr,
                global_worker_capacity=config.global_worker_capacity,
                pre_fr_capacity=config.pre_fr_capacity,
            )
            result = _record_payload(record, include_lease_token=True)
        elif operation == "todo.heartbeat":
            record = lifecycle.heartbeat(
                _required_string(payload, "todo_id"),
                _required_string(payload, "worker_id"),
                _required_string(payload, "lease_token"),
                now,
                config.lease_seconds,
            )
            result = _record_payload(record)
        elif operation == "todo.fail":
            lease_token = _required_string(payload, "lease_token")
            error = _required_string(payload, "error")
            if lease_token in error:
                raise ValueError("failure details must not contain lease credentials")
            record = lifecycle.fail(
                _required_string(payload, "todo_id"),
                _required_string(payload, "worker_id"),
                lease_token,
                now,
                error,
            )
            result = _record_payload(record)
        elif operation == "todo.retry":
            record = lifecycle.retry(
                _required_string(payload, "todo_id"), now, "bounded retry requested"
            )
            result = _record_payload(record)
        elif operation == "todo.cancel":
            record = lifecycle.cancel(
                _required_string(payload, "todo_id"),
                _required_string(payload, "worker_id"),
                _required_string(payload, "lease_token"),
                now,
                "worker cancellation requested",
            )
            result = _record_payload(record)
        elif operation == "todo.recover_stale":
            result = lifecycle.recover_stale(now)
        elif operation == "todo.takeover":
            if not config.takeover_enabled:
                raise PermissionError("takeover is disabled by execution policy")
            if payload.get("approved") is not True:
                raise PermissionError("takeover requires explicit approval")
            record = lifecycle.takeover(
                todo_id=_required_string(payload, "todo_id"),
                worker_id=_required_string(payload, "worker_id"),
                claim_id=uuid.uuid4().hex,
                lease_token=secrets.token_urlsafe(32),
                now=now,
                lease_seconds=config.lease_seconds,
                reason="approved takeover resumed",
                max_parallel_per_fr=config.max_parallel_per_fr,
                global_worker_capacity=config.global_worker_capacity,
                pre_fr_capacity=config.pre_fr_capacity,
            )
            result = _record_payload(record, include_lease_token=True)
        elif operation == "todo.complete":
            if payload.get("validated_handoff") is not True:
                raise ValueError("completion requires validated handoff")
            record = lifecycle.complete(
                _required_string(payload, "todo_id"),
                _required_string(payload, "worker_id"),
                _required_string(payload, "lease_token"),
                now,
                "validated handoff completed",
                validated_handoff=True,
                handoff_evidence=_required_string(payload, "handoff_evidence"),
            )
            result = _record_payload(record)
        elif operation == "todo.get":
            result = _record_payload(lifecycle.get(_required_string(payload, "todo_id")))
        else:
            result = [
                {
                    "event_id": event["event_id"],
                    "state": event["state"],
                    "occurred_at": event["occurred_at"],
                }
                for event in lifecycle.events(_required_string(payload, "todo_id"))
            ]
        return json.dumps(result, sort_keys=True)
    finally:
        if owns_connection:
            connection.close()


def invoke_coordination(
    operation: str,
    payload: Mapping[str, Any],
    *,
    connection: Any | None = None,
    config: Any | None = None,
) -> str:
    """Invoke one fixed FR ledger or TODO lifecycle operation."""
    if operation not in _ALLOWED_OPERATIONS | _TODO_ALLOWED_OPERATIONS:
        raise ValueError(f"unsupported coordination operation: {operation}")
    if _FORBIDDEN_ARGUMENTS.intersection(payload):
        raise ValueError("database and SQL arguments are not supported")
    if operation in _TODO_ALLOWED_OPERATIONS:
        required_fields, optional_fields = _TODO_ARGUMENTS[operation]
        fields = set(payload)
        if fields - required_fields - optional_fields:
            raise ValueError("unexpected arguments for TODO lifecycle operation")
        if required_fields - fields:
            raise ValueError("missing required arguments for TODO lifecycle operation")
        if "fr_id" in payload and payload["fr_id"] is not None:
            _required_string(payload, "fr_id")
        return _run_todo_operation(
            operation, payload, connection=connection, config=config
        )
    if connection is not None or config is not None:
        raise ValueError("lifecycle dependencies are only valid for TODO operations")
    allowed_fields = {
        "fr.get": {"fr_id"},
        "fr.record_event": {"fr_id", "agent", "event_type", "summary"},
        "fr.record_artifact": {"fr_id", "artifact_type", "label", "path"},
        "fr.reconcile_cost_unavailable": {"fr_id", "source", "reason"},
    }[operation]
    if set(payload) - allowed_fields:
        raise ValueError("unexpected arguments for coordination operation")
    return _run_fr_cli(operation, dict(payload))


mcp = FastMCP(
    "workspace-coordination",
    instructions=(
        "Governed FR ledger and TODO lifecycle operations only. FR state mutations "
        "remain canonical through fr_cli.py. TODO lifecycle tools use the canonical "
        "workspace database and server policy. Claim replay requires a private "
        "client-held idempotency key; worker identity alone does not authorize replay. "
        "Takeover requires enabled policy and explicit approval. Arbitrary database "
        "names, SQL, and generic state setters are unsupported."
    ),
)


@mcp.tool()
def get_fr(fr_id: str) -> str:
    """Read one feature request from the canonical FR ledger."""
    return invoke_coordination("fr.get", {"fr_id": fr_id})


@mcp.tool()
def record_fr_event(fr_id: str, agent: str, event_type: str, summary: str) -> str:
    """Append an event through the canonical FR CLI."""
    return invoke_coordination(
        "fr.record_event",
        {"fr_id": fr_id, "agent": agent, "event_type": event_type, "summary": summary},
    )


@mcp.tool()
def record_fr_artifact(
    fr_id: str, artifact_type: str, label: str, path: str | None = None
) -> str:
    """Append an artifact through the canonical FR CLI."""
    payload: dict[str, Any] = {
        "fr_id": fr_id,
        "artifact_type": artifact_type,
        "label": label,
    }
    if path is not None:
        payload["path"] = path
    return invoke_coordination("fr.record_artifact", payload)


@mcp.tool()
def reconcile_fr_cost_unavailable(fr_id: str, source: str, reason: str) -> str:
    """Record an explicit unavailable historical cost outcome."""
    return invoke_coordination(
        "fr.reconcile_cost_unavailable",
        {"fr_id": fr_id, "source": source, "reason": reason},
    )


@mcp.tool()
def todo_register_queued(
    todo_id: str, idempotency_key: str, fr_id: str | None = None
) -> str:
    """Persist one idempotent queued TODO using server policy limits."""
    payload: dict[str, Any] = {"todo_id": todo_id, "idempotency_key": idempotency_key}
    if fr_id is not None:
        payload["fr_id"] = fr_id
    return invoke_coordination("todo.register_queued", payload)


@mcp.tool()
def todo_claim(
    todo_id: str,
    worker_id: str,
    claim_idempotency_key: str,
    fr_id: str | None = None,
) -> str:
    """Claim queued work with a private replay key and return its lease credential."""
    payload: dict[str, Any] = {
        "todo_id": todo_id,
        "worker_id": worker_id,
        "claim_idempotency_key": claim_idempotency_key,
    }
    if fr_id is not None:
        payload["fr_id"] = fr_id
    return invoke_coordination("todo.claim", payload)


@mcp.tool()
def todo_heartbeat(todo_id: str, worker_id: str, lease_token: str) -> str:
    """Renew an owned TODO lease and mark the execution running."""
    return invoke_coordination(
        "todo.heartbeat",
        {"todo_id": todo_id, "worker_id": worker_id, "lease_token": lease_token},
    )


@mcp.tool()
def todo_fail(todo_id: str, worker_id: str, lease_token: str, error: str) -> str:
    """Record failure for an owned TODO lease."""
    return invoke_coordination(
        "todo.fail",
        {"todo_id": todo_id, "worker_id": worker_id, "lease_token": lease_token, "error": error},
    )


@mcp.tool()
def todo_retry(todo_id: str) -> str:
    """Queue a failed or stale TODO when its persisted retry budget allows."""
    return invoke_coordination("todo.retry", {"todo_id": todo_id})


@mcp.tool()
def todo_cancel(todo_id: str, worker_id: str, lease_token: str) -> str:
    """Cancel an active TODO execution owned by the caller."""
    return invoke_coordination(
        "todo.cancel",
        {"todo_id": todo_id, "worker_id": worker_id, "lease_token": lease_token},
    )


@mcp.tool()
def todo_recover_stale() -> str:
    """Mark expired TODO leases stale using the server clock."""
    return invoke_coordination("todo.recover_stale", {})


@mcp.tool()
def todo_takeover(todo_id: str, worker_id: str, approved: bool) -> str:
    """Take over stale work only with explicit approval and enabled policy."""
    return invoke_coordination(
        "todo.takeover",
        {"todo_id": todo_id, "worker_id": worker_id, "approved": approved},
    )


@mcp.tool()
def todo_complete(
    todo_id: str,
    worker_id: str,
    lease_token: str,
    validated_handoff: bool,
    handoff_evidence: str,
) -> str:
    """Complete owned work only with validated handoff evidence."""
    return invoke_coordination(
        "todo.complete",
        {"todo_id": todo_id, "worker_id": worker_id, "lease_token": lease_token,
         "validated_handoff": validated_handoff, "handoff_evidence": handoff_evidence},
    )


@mcp.tool()
def todo_get(todo_id: str) -> str:
    """Read TODO execution state without creating or migrating lifecycle schema."""
    return invoke_coordination("todo.get", {"todo_id": todo_id})


@mcp.tool()
def todo_events(todo_id: str) -> str:
    """Read TODO lifecycle event summaries without returning lease credentials."""
    return invoke_coordination("todo.events", {"todo_id": todo_id})


if __name__ == "__main__":
    mcp.run(transport="stdio")