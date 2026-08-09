"""Typed, staged outbound draft for the dedicated service-email capability.

FR-20260808-dedicated-service-email.

An :class:`EmailDraft` is a purely local, immutable representation of an
outbound message. Building one performs *no* network I/O and delivers nothing.
Delivery is a separate, operator-gated step
(:meth:`integrations.gmail.client.GmailServiceClient.send_draft`) that requires
explicit operator approval. Keeping the draft as inert data means an agent can
compose and inspect an outbound message without any risk of it reaching Gmail.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailDraft:
    """An immutable, validated outbound message staged for operator approval.

    The recipient and subject are validated when the draft is created by the
    client (recipient syntax + CR/LF header-injection rejection); the draft
    itself never mutates and never performs I/O.
    """

    to: str
    subject: str
    body: str
    from_address: str = ""

    def as_raw(self) -> str:
        """Return the base64url-encoded RFC 5322 message for the Gmail API.

        This only serialises the already-validated fields; it performs no
        network I/O and does not deliver the message.
        """
        from email.message import EmailMessage  # noqa: PLC0415

        msg = EmailMessage()
        msg["To"] = self.to
        if self.from_address:
            msg["From"] = self.from_address
        msg["Subject"] = self.subject
        msg.set_content(self.body)
        return base64.urlsafe_b64encode(msg.as_bytes()).decode()
