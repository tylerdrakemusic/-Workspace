"""GmailServiceClient — dedicated service-email capability for the workspace.

FR-20260808-dedicated-service-email.

Auth:
    Reads ``GMAIL_SERVICE_TOKEN`` (base64-encoded OAuth *authorized-user* JSON:
    client id/secret + refresh token). The account, OAuth consent, and token
    are all produced by a human out-of-band — never by an agent. The token is
    decoded in memory at construction time and is never written to disk, logs,
    or the FR ledger.

    ``GMAIL_SERVICE_ADDRESS`` optionally names the mailbox identity.

Governance:
    Every action is gated by :class:`integrations.gmail.policy.ServiceEmailPolicy`.
    Outbound sending is guarded (disabled by default). Reads are filtered for
    sensitive content. Raw messages are retained for 30 days.

Usage::

    from integrations.gmail import GmailServiceClient, ServiceEmailPolicy
    client = GmailServiceClient(policy=ServiceEmailPolicy.from_config())
    inbox = client.list_messages(query="in:inbox is:unread")
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Optional

from .policy import ALL_SCOPES, Action, ServiceEmailPolicy

_SERVICE_ADDRESS_ENV = "GMAIL_SERVICE_ADDRESS"
_TOKEN_ENV = "GMAIL_SERVICE_TOKEN"  # nosec B105 - env var name, not a secret value


def build_service(credentials):
    """Build and return the Gmail v1 service resource.

    Isolated so tests can patch ``integrations.gmail.client.build_service``.
    """
    from googleapiclient.discovery import build  # noqa: PLC0415

    return build("gmail", "v1", credentials=credentials)


def _load_credentials():
    """Decode ``GMAIL_SERVICE_TOKEN`` and return google-auth credentials."""
    raw = os.environ.get(_TOKEN_ENV)
    if not raw:
        raise EnvironmentError(
            f"{_TOKEN_ENV} environment variable is not set. Set it to the "
            "base64-encoded OAuth authorized-user JSON for the dedicated "
            "service mailbox. The account and token are created by a human "
            "out-of-band; agents never mint credentials."
        )
    try:
        info = json.loads(base64.b64decode(raw))
    except Exception as exc:
        raise EnvironmentError(f"{_TOKEN_ENV} could not be decoded: {exc}") from exc

    from google.oauth2.credentials import Credentials  # noqa: PLC0415

    return Credentials.from_authorized_user_info(info, scopes=list(ALL_SCOPES))


def _reject_header_injection(value: str, field: str) -> None:
    if value and ("\r" in value or "\n" in value):
        raise ValueError(f"Illegal newline in {field} (header-injection attempt)")


class GmailServiceClient:
    """Thin, policy-governed wrapper around the Gmail v1 API."""

    def __init__(self, policy: Optional[ServiceEmailPolicy] = None) -> None:
        self._policy = policy or ServiceEmailPolicy.from_config()
        credentials = _load_credentials()
        self._service = build_service(credentials)
        self._address = os.environ.get(_SERVICE_ADDRESS_ENV, "")
        if self._address:
            print(f"[GmailServiceClient] service mailbox: {self._address}")

    @property
    def policy(self) -> ServiceEmailPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Reading (action-scoped + content-filtered)
    # ------------------------------------------------------------------

    def _messages(self):
        return self._service.users().messages()

    def _parse_message(self, raw: dict) -> dict:
        payload = raw.get("payload", {}) or {}
        headers = payload.get("headers", []) or []
        subject = ""
        for h in headers:
            if h.get("name", "").lower() == "subject":
                subject = h.get("value", "")
                break
        body = ""
        data = (payload.get("body", {}) or {}).get("data", "")
        if data:
            try:
                body = base64.urlsafe_b64decode(data.encode()).decode("utf-8", "replace")
            except Exception:
                body = ""
        return {"id": raw.get("id", ""), "subject": subject, "body": body}

    def get_message(self, msg_id: str, action: Action = Action.READ) -> dict:
        self._policy.authorize(action)
        raw = self._messages().get(userId="me", id=msg_id, format="full").execute()
        return self._policy.apply_content_policy(self._parse_message(raw))

    def list_messages(
        self, query: Optional[str] = None, action: Action = Action.SEARCH
    ) -> list[dict]:
        """List messages matching *query*, returning policy-filtered copies."""
        self._policy.authorize(action)
        resp = self._messages().list(userId="me", q=query or "").execute()
        results: list[dict] = []
        for stub in resp.get("messages", []) or []:
            results.append(self.get_message(stub["id"], action=Action.READ))
        return results

    # ------------------------------------------------------------------
    # Outbound (guarded)
    # ------------------------------------------------------------------

    def _build_raw(self, to: str, subject: str, body: str) -> str:
        from email.message import EmailMessage  # noqa: PLC0415

        msg = EmailMessage()
        msg["To"] = to
        if self._address:
            msg["From"] = self._address
        msg["Subject"] = subject
        msg.set_content(body)
        return base64.urlsafe_b64encode(msg.as_bytes()).decode()

    def send_message(self, to: str, subject: str, body: str) -> dict:
        """Send an outbound message. Guarded: raises unless policy allows
        outbound and the recipient is valid. Never logs the recipient."""
        self._policy.guard_outbound(to)
        _reject_header_injection(subject, "subject")
        self._policy.authorize(Action.SEND)
        raw = self._build_raw(to, subject, body)
        return self._messages().send(userId="me", body={"raw": raw}).execute()

    def authorize_signup(self, service: str) -> str:
        """Authorize an autonomous sign-up (policy decision). Returns the
        mailbox address to use, or raises if sign-ups are disabled."""
        self._policy.guard_signup(service)
        self._policy.authorize(Action.SIGNUP)
        return self._address

    # ------------------------------------------------------------------
    # Connectivity test (runtime-only recipient — never stored or logged)
    # ------------------------------------------------------------------

    def connectivity_test(self, recipient: str) -> dict:
        """Round-trip read/write check against a Tyler-approved recipient
        supplied at call time. The recipient is never persisted or logged."""
        if not recipient:
            raise ValueError("connectivity_test requires a runtime recipient")
        # guard_outbound validates format + injection and enforces the guard.
        self._policy.guard_outbound(recipient)

        marker = f"service-email-connectivity-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        send_result = self.send_message(recipient, "connectivity", marker)

        read_back = False
        try:
            found = self.list_messages(query="subject:connectivity")
            read_back = len(found) > 0
        except Exception:
            read_back = False

        return {
            "sent": bool(send_result.get("id")),
            "read_back": read_back,
            "marker": marker,
        }

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def prune_expired(self, now: Optional[datetime] = None) -> int:
        """Delete raw messages older than the retention window. Idempotent:
        a second pass over an already-pruned mailbox deletes nothing."""
        now = now or datetime.now(timezone.utc)
        self._policy.authorize(Action.READ)
        resp = self._messages().list(userId="me", q="").execute()
        pruned = 0
        for stub in resp.get("messages", []) or []:
            raw = self._messages().get(userId="me", id=stub["id"], format="metadata").execute()
            internal = raw.get("internalDate")
            if internal is None:
                continue
            ts = datetime.fromtimestamp(int(internal) / 1000, tz=timezone.utc)
            if self._policy.is_expired(ts, now=now):
                self._messages().delete(userId="me", id=stub["id"]).execute()
                pruned += 1
        return pruned
