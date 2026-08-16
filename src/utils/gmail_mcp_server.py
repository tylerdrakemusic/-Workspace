"""Persistent stdio MCP server for the governed Gmail service capability."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.gmail import EmailDraft, GmailServiceClient, build_service, describe_capability
from integrations.gmail.client import _load_credentials

_TOKEN_ENV = "GMAIL_SERVICE_TOKEN"
_CAPABILITY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "service_email_capability.json"
)


def capability_discovery() -> dict[str, Any]:
    """Return the governed Gmail capability descriptor for MCP discovery."""
    capability = describe_capability()
    capability["actions"] = list(
        dict.fromkeys(
            [*capability.get("actions", []), "get", "draft", "connectivity_test"]
        )
    )
    capability.update(
        {
            "mcp_server": "gmail-service-email",
            "mcp_transport": "stdio",
            "mcp_tools": [
                "discover_capability",
                "health",
                "read_messages",
                "search_messages",
                "get_message",
                "create_draft",
                "send_draft",
                "connectivity_test",
            ],
            "outbound_requires_operator_approved_true": True,
            "health_tool": "capability_health",
        }
    )
    return capability


def _health(state: str, detail: str, *, reauthentication_required: bool) -> dict[str, Any]:
    return {
        "name": "dedicated-service-email",
        "available": state == "available",
        "state": state,
        "detail": detail,
        "reauthentication_required": reauthentication_required,
        "credential_env": _TOKEN_ENV,
        "secrets_exposed": False,
    }


def capability_health() -> dict[str, Any]:
    """Probe credentials and mailbox access without returning secret values."""
    if not os.environ.get(_TOKEN_ENV):
        return _health(
            "missing_credentials",
            f"{_TOKEN_ENV} is not configured; human OAuth bootstrap is required.",
            reauthentication_required=True,
        )

    try:
        credentials = _load_credentials()
    except EnvironmentError:
        return _health(
            "malformed_credentials",
            f"{_TOKEN_ENV} is malformed; human OAuth bootstrap is required.",
            reauthentication_required=True,
        )
    except (TypeError, ValueError):
        return _health(
            "malformed_credentials",
            f"{_TOKEN_ENV} is malformed; human OAuth bootstrap is required.",
            reauthentication_required=True,
        )

    if getattr(credentials, "expired", False) is True:
        return _health(
            "expired_credentials",
            "Gmail credentials are expired; human re-authentication is required.",
            reauthentication_required=True,
        )

    try:
        service = build_service(credentials)
        service.users().getProfile(userId="me").execute()
    except Exception as exc:  # noqa: BLE001 - classify external auth/API failures safely
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status == 401:
            state = "revoked_credentials"
            detail = "Gmail credentials were rejected; human re-authentication is required."
            reauth = True
        else:
            state = "inaccessible_credentials"
            detail = "Gmail credentials could not access the service mailbox."
            reauth = False
        return _health(state, detail, reauthentication_required=reauth)

    return _health("available", "Gmail service mailbox is reachable.", reauthentication_required=False)


def _unavailable() -> dict[str, Any] | None:
    health = capability_health()
    if health["available"]:
        return None
    return {"ok": False, "error": "gmail_unavailable", "health": health}


def _client() -> GmailServiceClient:
    return GmailServiceClient()


mcp = FastMCP(
    "gmail-service-email",
    instructions=(
        "Provides governed access to the dedicated Gmail service mailbox. "
        "Credentials remain in environment variables and outbound delivery "
        "requires policy plus exact operator_approved=True."
    ),
)


@mcp.tool()
def discover_capability() -> dict[str, Any]:
    """Discover Gmail actions and their governance boundaries."""
    return capability_discovery()


@mcp.tool()
def health() -> dict[str, Any]:
    """Report explicit availability and authentication state."""
    return capability_health()


@mcp.tool()
def read_messages(query: str = "") -> dict[str, Any]:
    """Read policy-filtered mailbox messages."""
    unavailable = _unavailable()
    if unavailable:
        return unavailable
    return {"ok": True, "messages": _client().list_messages(query=query)}


@mcp.tool()
def search_messages(query: str = "") -> dict[str, Any]:
    """Search policy-filtered mailbox messages."""
    return read_messages(query)


@mcp.tool()
def get_message(message_id: str) -> dict[str, Any]:
    """Read one policy-filtered mailbox message."""
    unavailable = _unavailable()
    if unavailable:
        return unavailable
    return {"ok": True, "message": _client().get_message(message_id)}


@mcp.tool()
def create_draft(to: str, subject: str, body: str) -> dict[str, Any]:
    """Create a local outbound draft without contacting Gmail."""
    unavailable = _unavailable()
    if unavailable:
        return unavailable
    draft = _client().create_draft(to, subject, body)
    return {"ok": True, "draft": {"to": draft.to, "subject": draft.subject, "body": draft.body}}


@mcp.tool()
def send_draft(
    draft: dict[str, str], *, operator_approved: bool = False
) -> dict[str, Any]:
    """Send a draft only when policy and exact operator approval permit it."""
    unavailable = _unavailable()
    if unavailable:
        return unavailable
    client = _client()
    email_draft = EmailDraft(
        to=draft["to"], subject=draft["subject"], body=draft["body"]
    )
    return {
        "ok": True,
        "result": client.send_draft(email_draft, operator_approved=operator_approved),
    }


@mcp.tool()
def connectivity_test(recipient: str, *, operator_approved: bool = False) -> dict[str, Any]:
    """Run the existing runtime-only, operator-gated connectivity test."""
    unavailable = _unavailable()
    if unavailable:
        return unavailable
    return {
        "ok": True,
        "result": _client().connectivity_test(
            recipient, operator_approved=operator_approved
        ),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")