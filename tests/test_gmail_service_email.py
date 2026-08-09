"""Unit tests for the dedicated service-email (Gmail) capability.

FR-20260808-dedicated-service-email — heavy TDD (written before implementation).

Scope: WORKSPACE-SIDE capability only. No account creation, no OAuth, no real
send. Every external Gmail call is mocked. No credentials or test recipients
are hardcoded here — the connectivity-test recipient is always supplied at
call time and must never be logged.

All tests fail on first run (ImportError) until the implementation lands.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Allow import from the worktree src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# A fake, clearly-not-real OAuth authorized-user token blob. Contains no real
# secret — it is only structurally valid enough to exercise decode paths.
_FAKE_TOKEN = base64.b64encode(
    json.dumps(
        {
            "type": "authorized_user",
            "client_id": "fake.apps.googleusercontent.com",
            "client_secret": "not-a-real-secret",
            "refresh_token": "fake-refresh-token",
        }
    ).encode()
).decode()


# ─────────────────────────────────────────────────────────────────────────────
# Policy: secure defaults & config loading
# ─────────────────────────────────────────────────────────────────────────────


def test_default_policy_has_secure_defaults():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default()
    # Outbound is guarded off by default; must be explicitly enabled.
    assert policy.allow_outbound is False
    # Autonomous sign-ups were the agreed policy decision (broad allow).
    assert policy.allow_autonomous_signups is True
    # 30-day raw retention.
    assert policy.raw_retention_days == 30


def test_policy_loads_from_config_json():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.from_config()
    assert policy.raw_retention_days == 30
    assert isinstance(policy.allow_outbound, bool)


# ─────────────────────────────────────────────────────────────────────────────
# Action-scoped authorization
# ─────────────────────────────────────────────────────────────────────────────


def test_authorize_read_returns_readonly_scope():
    from integrations.gmail import Action, ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default()
    scope = policy.authorize(Action.READ)
    assert scope.endswith("gmail.readonly")


def test_authorize_send_returns_send_scope():
    from integrations.gmail import Action, ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default()
    scope = policy.authorize(Action.SEND)
    assert scope.endswith("gmail.send")


def test_authorize_disabled_action_raises_permission_error():
    from integrations.gmail import Action, ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_disabled({Action.SEND})
    with pytest.raises(PermissionError):
        policy.authorize(Action.SEND)
    # Non-disabled actions still work.
    assert policy.authorize(Action.READ).endswith("gmail.readonly")


# ─────────────────────────────────────────────────────────────────────────────
# Guarded outbound sending
# ─────────────────────────────────────────────────────────────────────────────


def test_guard_outbound_blocks_when_disabled():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default()  # allow_outbound=False
    with pytest.raises(PermissionError):
        policy.guard_outbound("someone@example.com")


def test_guard_outbound_rejects_invalid_recipient():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_outbound(True)
    with pytest.raises(ValueError):
        policy.guard_outbound("not-an-email")
    with pytest.raises(ValueError):
        policy.guard_outbound("")


def test_guard_outbound_rejects_header_injection():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_outbound(True)
    with pytest.raises(ValueError):
        policy.guard_outbound("victim@example.com\r\nBcc: evil@example.com")


def test_guard_outbound_allows_valid_recipient_when_enabled():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_outbound(True)
    # Should not raise.
    policy.guard_outbound("valid.person@example.com")


# ─────────────────────────────────────────────────────────────────────────────
# Autonomous sign-up as a policy decision
# ─────────────────────────────────────────────────────────────────────────────


def test_guard_signup_allows_when_enabled():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default()  # allow_autonomous_signups=True
    policy.guard_signup("some-newsletter")  # should not raise


def test_guard_signup_blocks_when_disabled():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_autonomous_signups(False)
    with pytest.raises(PermissionError):
        policy.guard_signup("some-newsletter")


# ─────────────────────────────────────────────────────────────────────────────
# Full-mailbox policy filtering (sensitive-content redaction)
# ─────────────────────────────────────────────────────────────────────────────


def test_content_policy_redacts_sensitive_message():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default()
    msg = {
        "id": "m1",
        "subject": "Your account statement",
        "body": "Your bank account routing number is 021000021 balance $4,210.",
    }
    filtered = policy.apply_content_policy(msg)
    assert filtered["policy_redacted"] is True
    assert "021000021" not in filtered["body"]
    # Original object is not mutated.
    assert "021000021" in msg["body"]


def test_content_policy_passes_benign_message():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default()
    msg = {"id": "m2", "subject": "Welcome!", "body": "Thanks for signing up."}
    filtered = policy.apply_content_policy(msg)
    assert filtered["policy_redacted"] is False
    assert filtered["body"] == "Thanks for signing up."


# ─────────────────────────────────────────────────────────────────────────────
# 30-day raw retention
# ─────────────────────────────────────────────────────────────────────────────


def test_retention_expiry_boundary():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default()
    now = datetime(2026, 8, 8, tzinfo=timezone.utc)
    fresh = now - timedelta(days=29)
    stale = now - timedelta(days=30, seconds=1)
    assert policy.is_expired(fresh, now=now) is False
    assert policy.is_expired(stale, now=now) is True


# ─────────────────────────────────────────────────────────────────────────────
# Capability discoverability
# ─────────────────────────────────────────────────────────────────────────────


def test_describe_capability_is_discoverable():
    from integrations.gmail import describe_capability  # noqa: PLC0415

    cap = describe_capability()
    assert cap["name"]
    # Actions are enumerated for discovery.
    actions = {a.lower() for a in cap["actions"]}
    assert {"read", "send"}.issubset(actions)
    assert cap["raw_retention_days"] == 30
    # Residual risk of full-mailbox filtering is documented in the descriptor.
    assert cap["residual_risk"].strip()


# ─────────────────────────────────────────────────────────────────────────────
# Client: credential handling
# ─────────────────────────────────────────────────────────────────────────────


def test_client_missing_env_var_raises():
    from integrations.gmail import GmailServiceClient  # noqa: PLC0415

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("GMAIL_SERVICE_TOKEN", None)
        with pytest.raises(EnvironmentError, match="GMAIL_SERVICE_TOKEN"):
            GmailServiceClient()


def _mock_client(policy=None):
    """Construct a GmailServiceClient with google auth + service mocked out."""
    from integrations.gmail import GmailServiceClient  # noqa: PLC0415

    mock_service = MagicMock()
    with patch.dict(os.environ, {"GMAIL_SERVICE_TOKEN": _FAKE_TOKEN}):
        with patch(
            "integrations.gmail.client._load_credentials", return_value=MagicMock()
        ):
            with patch(
                "integrations.gmail.client.build_service", return_value=mock_service
            ):
                client = GmailServiceClient(policy=policy)
    return client, mock_service


# ─────────────────────────────────────────────────────────────────────────────
# Client: list applies content policy
# ─────────────────────────────────────────────────────────────────────────────


def test_list_messages_applies_content_policy():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    client, service = _mock_client(policy=ServiceEmailPolicy.default())

    users = service.users.return_value
    messages = users.messages.return_value
    messages.list.return_value.execute.return_value = {"messages": [{"id": "m1"}]}
    messages.get.return_value.execute.return_value = {
        "id": "m1",
        "payload": {
            "headers": [{"name": "Subject", "value": "Statement"}],
            "body": {"data": base64.urlsafe_b64encode(b"routing number 021000021").decode()},
        },
    }

    results = client.list_messages(query="in:inbox")
    assert len(results) == 1
    assert results[0]["policy_redacted"] is True
    assert "021000021" not in results[0]["body"]


# ─────────────────────────────────────────────────────────────────────────────
# Client: guarded outbound send
# ─────────────────────────────────────────────────────────────────────────────


def test_send_message_blocked_by_default_policy():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    client, service = _mock_client(policy=ServiceEmailPolicy.default())
    with pytest.raises(PermissionError):
        client.send_message("dest@example.com", "Hi", "Body")
    # The Gmail send API must never be reached when blocked.
    service.users.return_value.messages.return_value.send.assert_not_called()


def test_send_message_allowed_calls_api_once():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_outbound(True)
    client, service = _mock_client(policy=policy)

    send = service.users.return_value.messages.return_value.send
    send.return_value.execute.return_value = {"id": "sent1"}

    result = client.send_message("dest@example.com", "Hi", "Body")
    assert result["id"] == "sent1"
    send.assert_called_once()


def test_send_message_does_not_log_recipient():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_outbound(True)
    client, service = _mock_client(policy=policy)
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "sent1"
    }

    secret_recipient = "runtime.only.person@example.com"
    buf = io.StringIO()
    with redirect_stdout(buf):
        client.send_message(secret_recipient, "Hi", "Body")
    assert secret_recipient not in buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Client: read/write connectivity test with runtime-only recipient
# ─────────────────────────────────────────────────────────────────────────────


def test_connectivity_test_requires_runtime_recipient():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_outbound(True)
    client, _ = _mock_client(policy=policy)
    with pytest.raises(ValueError):
        client.connectivity_test("")
    with pytest.raises(ValueError):
        client.connectivity_test(None)  # type: ignore[arg-type]


def test_connectivity_test_read_write_roundtrip():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_outbound(True)
    client, service = _mock_client(policy=policy)

    messages = service.users.return_value.messages.return_value
    messages.send.return_value.execute.return_value = {"id": "sent1", "threadId": "t1"}
    messages.list.return_value.execute.return_value = {"messages": [{"id": "sent1"}]}
    messages.get.return_value.execute.return_value = {
        "id": "sent1",
        "payload": {
            "headers": [{"name": "Subject", "value": "connectivity"}],
            "body": {"data": base64.urlsafe_b64encode(b"ping").decode()},
        },
    }

    result = client.connectivity_test("runtime.person@example.com")
    assert result["sent"] is True
    assert result["read_back"] is True


def test_connectivity_test_does_not_log_recipient():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_outbound(True)
    client, service = _mock_client(policy=policy)
    messages = service.users.return_value.messages.return_value
    messages.send.return_value.execute.return_value = {"id": "sent1"}
    messages.list.return_value.execute.return_value = {"messages": [{"id": "sent1"}]}
    messages.get.return_value.execute.return_value = {
        "id": "sent1",
        "payload": {"headers": [], "body": {"data": ""}},
    }

    recipient = "do.not.log@example.com"
    buf = io.StringIO()
    with redirect_stdout(buf):
        client.connectivity_test(recipient)
    assert recipient not in buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Client: retention pruning is idempotent
# ─────────────────────────────────────────────────────────────────────────────


def test_prune_expired_is_idempotent():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    client, service = _mock_client(policy=ServiceEmailPolicy.default())
    now = datetime(2026, 8, 8, tzinfo=timezone.utc)
    old_ms = int((now - timedelta(days=45)).timestamp() * 1000)

    messages = service.users.return_value.messages.return_value

    # First pass: one stale message present, then it is deleted so the second
    # pass sees an empty mailbox.
    list_states = [
        {"messages": [{"id": "old1"}]},
        {"messages": []},
    ]
    messages.list.return_value.execute.side_effect = list_states
    messages.get.return_value.execute.return_value = {
        "id": "old1",
        "internalDate": str(old_ms),
        "payload": {"headers": [], "body": {"data": ""}},
    }
    messages.delete.return_value.execute.return_value = {}

    first = client.prune_expired(now=now)
    second = client.prune_expired(now=now)
    assert first == 1
    assert second == 0


# ─────────────────────────────────────────────────────────────────────────────
# Client: sign-up authorization delegates to policy
# ─────────────────────────────────────────────────────────────────────────────


def test_authorize_signup_blocked_by_policy():
    from integrations.gmail import ServiceEmailPolicy  # noqa: PLC0415

    policy = ServiceEmailPolicy.default().with_autonomous_signups(False)
    client, _ = _mock_client(policy=policy)
    with pytest.raises(PermissionError):
        client.authorize_signup("newsletter")
