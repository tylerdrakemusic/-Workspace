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
    Outbound delivery is operator-gated: an agent composes a local draft, but a
    message is sent only when an explicit operator-approval argument is
    ``True`` (and the ``allow_outbound`` policy switch, disabled by default, is
    enabled). Reads are filtered for sensitive content. Raw messages are
    retained for 30 days.

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

from .draft import EmailDraft
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
    # Outbound (staged draft + explicit operator approval)
    # ------------------------------------------------------------------

    def create_draft(self, to: str, subject: str, body: str) -> EmailDraft:
        """Compose and validate a local outbound draft — no network delivery.

        Enforces the outbound policy guard (recipient syntax + the
        ``allow_outbound`` master switch) and rejects CR/LF header injection in
        the subject, then returns an inert :class:`EmailDraft`. Nothing is sent:
        the Gmail API is never contacted here. Delivery is a separate,
        operator-gated step (:meth:`send_draft`).
        """
        self._policy.guard_outbound(to)
        _reject_header_injection(subject, "subject")
        return EmailDraft(to=to, subject=subject, body=body, from_address=self._address)

    def send_draft(self, draft: EmailDraft, *, operator_approved: bool = False) -> dict:
        """Deliver a previously-created draft — only on explicit approval.

        The message reaches Gmail **only** when *operator_approved* is exactly
        ``True``. Any other value (the default ``False``, ``None``, or a truthy
        proxy such as ``1``/``"yes"``) is refused with ``PermissionError`` and
        no Gmail API call is made. The recipient/subject are re-validated at
        delivery time so a tampered draft still cannot inject headers or reach
        an invalid address. The recipient is never logged.
        """
        if operator_approved is not True:
            # Refuse before any network I/O: an unapproved send never reaches Gmail.
            raise PermissionError(
                "Outbound delivery requires explicit operator approval "
                "(operator_approved=True). The draft was not sent."
            )
        self._policy.guard_outbound(draft.to)
        _reject_header_injection(draft.subject, "subject")
        self._policy.authorize(Action.SEND)
        return self._messages().send(userId="me", body={"raw": draft.as_raw()}).execute()

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        operator_approved: bool = False,
    ) -> dict:
        """Convenience wrapper: stage a draft then deliver it under approval.

        This never delivers directly from a bare agent call: without
        ``operator_approved=True`` it stages the draft and then refuses at the
        approval gate, so the Gmail API is never reached. Prefer the explicit
        :meth:`create_draft` + :meth:`send_draft` flow for auditability.
        """
        draft = self.create_draft(to, subject, body)
        return self.send_draft(draft, operator_approved=operator_approved)

    def authorize_signup(self, service: str) -> str:
        """Authorize an autonomous sign-up (policy decision). Returns the
        mailbox address to use, or raises if sign-ups are disabled."""
        self._policy.guard_signup(service)
        self._policy.authorize(Action.SIGNUP)
        return self._address

    # ------------------------------------------------------------------
    # Connectivity test (runtime-only recipient — never stored or logged)
    # ------------------------------------------------------------------

    def connectivity_test(
        self, recipient: str, *, operator_approved: bool = False
    ) -> dict:
        """Round-trip read/write check against a Tyler-approved recipient
        supplied at call time. Rides the same operator-gated draft path as any
        other outbound message: it stages a draft and delivers it only when
        *operator_approved* is explicitly ``True`` (the test-only approval).
        The recipient is never persisted or logged."""
        if not recipient:
            raise ValueError("connectivity_test requires a runtime recipient")

        marker = f"service-email-connectivity-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        draft = self.create_draft(recipient, "connectivity", marker)
        send_result = self.send_draft(draft, operator_approved=operator_approved)

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
