from __future__ import annotations

import os
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_direct_launcher_starts_without_external_pythonpath():
    repo_root = Path(__file__).resolve().parents[1]
    launcher = repo_root / "src" / "utils" / "gmail_mcp_server.py"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [sys.executable, str(launcher)],
        cwd=repo_root,
        env=environment,
        input="",
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert "ModuleNotFoundError: No module named 'integrations'" not in completed.stderr


def test_capability_health_reports_missing_credentials_without_secrets():
    from utils import gmail_mcp_server

    with patch.dict(os.environ, {}, clear=True):
        health = gmail_mcp_server.capability_health()

    assert health["name"] == "dedicated-service-email"
    assert health["available"] is False
    assert health["state"] == "missing_credentials"
    assert health["reauthentication_required"] is True
    assert "GMAIL_SERVICE_TOKEN" in health["detail"]
    assert "token" not in health["detail"].lower().replace("gmail_service_token", "")


def test_capability_discovery_exposes_governed_actions():
    from utils import gmail_mcp_server

    capability = gmail_mcp_server.capability_discovery()

    assert capability["name"] == "dedicated-service-email"
    assert set(capability["actions"]) >= {
        "read",
        "search",
        "get",
        "draft",
        "send",
        "connectivity_test",
    }
    assert capability["outbound_requires_operator_approved_true"] is True
    assert capability["credential_env"] == "GMAIL_SERVICE_TOKEN"
    assert capability["mcp_tools"] == [
        "discover_capability",
        "health",
        "read_messages",
        "search_messages",
        "get_message",
        "create_draft",
        "send_draft",
        "connectivity_test",
    ]


def test_capability_health_reports_malformed_credentials_without_exception_details():
    from utils import gmail_mcp_server

    with patch.dict(os.environ, {"GMAIL_SERVICE_TOKEN": "not-a-token"}, clear=True):
        health = gmail_mcp_server.capability_health()

    assert health["state"] == "malformed_credentials"
    assert health["reauthentication_required"] is True
    assert "not-a-token" not in health["detail"]


def test_capability_health_reports_expired_credentials_as_reauthentication_required(
    monkeypatch: pytest.MonkeyPatch,
):
    from utils import gmail_mcp_server

    monkeypatch.setenv("GMAIL_SERVICE_TOKEN", "opaque-runtime-value")
    monkeypatch.setattr(
        gmail_mcp_server,
        "_load_credentials",
        lambda: SimpleNamespace(expired=True),
    )

    health = gmail_mcp_server.capability_health()

    assert health["state"] == "expired_credentials"
    assert health["reauthentication_required"] is True


def test_capability_health_refreshes_expired_access_token(
    monkeypatch: pytest.MonkeyPatch,
):
    from utils import gmail_mcp_server

    class RefreshableCredentials:
        expired = True

        def refresh(self, request):
            self.expired = False

    credentials = RefreshableCredentials()
    monkeypatch.setenv("GMAIL_SERVICE_TOKEN", "opaque-runtime-value")
    monkeypatch.setattr(gmail_mcp_server, "_load_credentials", lambda: credentials)
    monkeypatch.setattr(
        gmail_mcp_server,
        "build_service",
        lambda loaded_credentials: SimpleNamespace(
            users=lambda: SimpleNamespace(
                getProfile=lambda **kwargs: SimpleNamespace(
                    execute=lambda: {"emailAddress": "service@example.com"}
                )
            )
        ),
    )

    health = gmail_mcp_server.capability_health()

    assert health["state"] == "available"
    assert health["reauthentication_required"] is False


@pytest.mark.parametrize(
    ("status", "expected_state", "reauthentication_required"),
    [
        (401, "revoked_credentials", True),
        (403, "inaccessible_credentials", False),
    ],
)
def test_capability_health_classifies_mailbox_access_failures(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    expected_state: str,
    reauthentication_required: bool,
):
    from utils import gmail_mcp_server

    class AccessError(Exception):
        resp = SimpleNamespace(status=status)

    monkeypatch.setenv("GMAIL_SERVICE_TOKEN", "opaque-runtime-value")
    monkeypatch.setattr(
        gmail_mcp_server,
        "_load_credentials",
        lambda: SimpleNamespace(expired=False),
    )
    monkeypatch.setattr(gmail_mcp_server, "build_service", lambda credentials: None)
    monkeypatch.setattr(
        gmail_mcp_server,
        "build_service",
        lambda credentials: SimpleNamespace(
            users=lambda: SimpleNamespace(
                getProfile=lambda **kwargs: SimpleNamespace(
                    execute=lambda: (_ for _ in ()).throw(AccessError())
                )
            )
        ),
    )

    health = gmail_mcp_server.capability_health()

    assert health["state"] == expected_state
    assert health["reauthentication_required"] is reauthentication_required

def test_read_messages_is_a_distinct_mcp_operation(monkeypatch: pytest.MonkeyPatch):
    from utils import gmail_mcp_server

    class FakeClient:
        def list_messages(self, query: str):
            assert query == "in:inbox"
            return [{"id": "m1", "policy_redacted": False}]

    monkeypatch.setattr(
        gmail_mcp_server,
        "capability_health",
        lambda: {"available": True, "state": "available"},
    )
    monkeypatch.setattr(gmail_mcp_server, "_client", lambda: FakeClient())

    result = gmail_mcp_server.read_messages("in:inbox")

    assert result == {"ok": True, "messages": [{"id": "m1", "policy_redacted": False}]}


def test_read_messages_returns_structured_unavailable_health(monkeypatch: pytest.MonkeyPatch):
    from utils import gmail_mcp_server

    expected_health = {
        "available": False,
        "state": "revoked_credentials",
        "reauthentication_required": True,
    }
    monkeypatch.setattr(gmail_mcp_server, "capability_health", lambda: expected_health)

    result = gmail_mcp_server.read_messages("in:inbox")

    assert result == {
        "ok": False,
        "error": "gmail_unavailable",
        "health": expected_health,
    }


def test_send_draft_forwards_exact_operator_approval(monkeypatch: pytest.MonkeyPatch):
    from utils import gmail_mcp_server

    approvals: list[object] = []

    class FakeClient:
        def send_draft(self, draft, *, operator_approved: bool):
            approvals.append(operator_approved)
            return {"id": "sent1"}

    monkeypatch.setattr(
        gmail_mcp_server,
        "capability_health",
        lambda: {"available": True, "state": "available"},
    )
    monkeypatch.setattr(gmail_mcp_server, "_client", lambda: FakeClient())

    result = gmail_mcp_server.send_draft(
        {"to": "destination@example.com", "subject": "Hi", "body": "Body"},
        operator_approved=1,  # type: ignore[arg-type]
    )

    assert result == {"ok": True, "result": {"id": "sent1"}}
    assert approvals == [1]


@pytest.mark.parametrize("tool_name", ["send_draft", "connectivity_test"])
@pytest.mark.parametrize("operator_approved", [1, "yes", None, [], {}])
def test_registered_outbound_tools_reject_non_boolean_approval(
    tool_name: str, operator_approved: object
):
    from pydantic import ValidationError

    from utils import gmail_mcp_server

    tool = gmail_mcp_server.mcp._tool_manager._tools[tool_name]
    arguments = (
        {"draft": {"to": "destination@example.com", "subject": "Hi", "body": "Body"}}
        if tool_name == "send_draft"
        else {"recipient": "destination@example.com"}
    )
    arguments["operator_approved"] = operator_approved

    with pytest.raises(ValidationError):
        tool.fn_metadata.arg_model.model_validate(arguments)


@pytest.mark.parametrize("tool_name", ["send_draft", "connectivity_test"])
def test_registered_outbound_tools_do_not_authorize_json_false(
    monkeypatch: pytest.MonkeyPatch, tool_name: str
):
    from utils import gmail_mcp_server

    class FakeClient:
        def send_draft(self, draft, *, operator_approved: bool):
            if operator_approved is not True:
                raise PermissionError("approval required")
            raise AssertionError("false approval reached delivery")

        def connectivity_test(self, recipient: str, *, operator_approved: bool):
            if operator_approved is not True:
                raise PermissionError("approval required")
            raise AssertionError("false approval reached delivery")

    monkeypatch.setattr(
        gmail_mcp_server,
        "capability_health",
        lambda: {"available": True, "state": "available"},
    )
    monkeypatch.setattr(gmail_mcp_server, "_client", lambda: FakeClient())

    tool = gmail_mcp_server.mcp._tool_manager._tools[tool_name]
    arguments = (
        {"draft": {"to": "destination@example.com", "subject": "Hi", "body": "Body"}}
        if tool_name == "send_draft"
        else {"recipient": "destination@example.com"}
    )
    arguments["operator_approved"] = False
    validated_arguments = tool.fn_metadata.arg_model.model_validate(arguments)

    with pytest.raises(PermissionError, match="approval required"):
        tool.fn(**validated_arguments.model_dump())


@pytest.mark.parametrize("tool_name", ["send_draft", "connectivity_test"])
def test_registered_outbound_tools_accept_only_json_true_for_delivery(
    monkeypatch: pytest.MonkeyPatch, tool_name: str
):
    from utils import gmail_mcp_server

    approvals: list[object] = []

    class FakeClient:
        def send_draft(self, draft, *, operator_approved: bool):
            approvals.append(operator_approved)
            return {"id": "sent1"}

        def connectivity_test(self, recipient: str, *, operator_approved: bool):
            approvals.append(operator_approved)
            return {"sent": True}

    monkeypatch.setattr(
        gmail_mcp_server,
        "capability_health",
        lambda: {"available": True, "state": "available"},
    )
    monkeypatch.setattr(gmail_mcp_server, "_client", lambda: FakeClient())

    tool = gmail_mcp_server.mcp._tool_manager._tools[tool_name]
    arguments = (
        {"draft": {"to": "destination@example.com", "subject": "Hi", "body": "Body"}}
        if tool_name == "send_draft"
        else {"recipient": "destination@example.com"}
    )
    arguments["operator_approved"] = True
    validated_arguments = tool.fn_metadata.arg_model.model_validate(arguments)

    result = tool.fn(**validated_arguments.model_dump())

    assert result["ok"] is True
    assert approvals == [True]
