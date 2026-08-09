"""Dedicated service-email (Gmail) capability for the workspace ecosystem.

FR-20260808-dedicated-service-email.

Discoverable, importable from every project::

    from integrations.gmail import (
        GmailServiceClient, ServiceEmailPolicy, Action, describe_capability,
    )

The capability is governed by :class:`ServiceEmailPolicy`: action-scoped
authorization, guarded outbound sending, a policy-level autonomous-sign-up
decision, best-effort sensitive-content filtering over a full-visibility
mailbox, and a 30-day raw-retention window. Credentials and the connectivity
test recipient are supplied at run time and are never stored here.
"""
from __future__ import annotations

import json
from pathlib import Path

from .client import GmailServiceClient, build_service
from .policy import ALL_SCOPES, RAW_RETENTION_DAYS, Action, ServiceEmailPolicy

_CAPABILITY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "service_email_capability.json"
)

__all__ = [
    "GmailServiceClient",
    "ServiceEmailPolicy",
    "Action",
    "ALL_SCOPES",
    "RAW_RETENTION_DAYS",
    "build_service",
    "describe_capability",
]


def describe_capability() -> dict:
    """Return the machine-readable capability descriptor for discovery.

    Any workspace agent can call this (or read
    ``src/config/service_email_capability.json``) to learn what the mailbox
    does and how it is governed, including the documented residual risk of
    full-mailbox content filtering.
    """
    return json.loads(_CAPABILITY_PATH.read_text(encoding="utf-8"))
