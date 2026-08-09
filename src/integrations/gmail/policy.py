"""Policy boundaries for the dedicated service-email (Gmail) capability.

FR-20260808-dedicated-service-email.

This module holds *only* policy toggles and enforcement logic. It never holds
secrets, never performs network I/O, and never logs recipients or message
bodies. The Gmail client (``integrations.gmail.client``) delegates every
authorization decision here so the boundaries live in one auditable place.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Actions & OAuth scopes
# ---------------------------------------------------------------------------

_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class Action(str, Enum):
    """Action-scoped capabilities the mailbox can perform."""

    READ = "read"
    SEARCH = "search"
    SEND = "send"
    SIGNUP = "signup"


# Least-privilege mapping: each action authorizes exactly the scope it needs.
_ACTION_SCOPES: dict[Action, str] = {
    Action.READ: _READONLY_SCOPE,
    Action.SEARCH: _READONLY_SCOPE,
    Action.SEND: _SEND_SCOPE,
    Action.SIGNUP: _SEND_SCOPE,
}

# Union of scopes the client requests when building credentials.
ALL_SCOPES: tuple[str, ...] = (_READONLY_SCOPE, _SEND_SCOPE)

RAW_RETENTION_DAYS = 30

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "service_email_policy.json"

# Reasonably conservative default heuristics; overridden by config when present.
_DEFAULT_SENSITIVE_PATTERNS: tuple[str, ...] = (
    r"\brouting number\b",
    r"\baccount number\b",
    r"\bssn\b",
    r"\bsocial security\b",
    r"\b\d{9}\b",
    r"\b\d{3}-\d{2}-\d{4}\b",
    r"\b(?:\d[ -]*?){13,16}\b",
    r"\bpassword\b",
    r"\bmedical record\b",
    r"\bdiagnosis\b",
)

# A pragmatic e-mail syntax check. Deliberately rejects control characters
# (including CR/LF) so it doubles as a header-injection guard.
_EMAIL_RE = re.compile(r"^[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+$")

_REDACTION = "[REDACTED-BY-SERVICE-EMAIL-POLICY]"


@dataclass(frozen=True)
class ServiceEmailPolicy:
    """Immutable policy governing the service mailbox.

    Defaults are secure: outbound sending is disabled until explicitly enabled.
    Autonomous sign-ups default to allowed per the agreed FR scope decision.
    """

    allow_outbound: bool = False
    allow_autonomous_signups: bool = True
    raw_retention_days: int = RAW_RETENTION_DAYS
    disabled_actions: frozenset[Action] = frozenset()
    sensitive_patterns: tuple[str, ...] = _DEFAULT_SENSITIVE_PATTERNS

    # -- construction ------------------------------------------------------

    @classmethod
    def default(cls) -> "ServiceEmailPolicy":
        return cls()

    @classmethod
    def from_config(cls, path: Path | str | None = None) -> "ServiceEmailPolicy":
        """Load policy from the JSON config, falling back to secure defaults."""
        cfg_path = Path(path) if path else _CONFIG_PATH
        if not cfg_path.is_file():
            return cls.default()
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        disabled = frozenset(
            Action(a) for a in data.get("disabled_actions", []) if a in Action._value2member_map_
        )
        patterns = tuple(data.get("sensitive_patterns") or _DEFAULT_SENSITIVE_PATTERNS)
        return cls(
            allow_outbound=bool(data.get("allow_outbound", False)),
            allow_autonomous_signups=bool(data.get("allow_autonomous_signups", True)),
            raw_retention_days=int(data.get("raw_retention_days", RAW_RETENTION_DAYS)),
            disabled_actions=disabled,
            sensitive_patterns=patterns,
        )

    # -- immutable builders (handy for tests & scoped overrides) -----------

    def with_outbound(self, allowed: bool) -> "ServiceEmailPolicy":
        return replace(self, allow_outbound=allowed)

    def with_autonomous_signups(self, allowed: bool) -> "ServiceEmailPolicy":
        return replace(self, allow_autonomous_signups=allowed)

    def with_disabled(self, actions) -> "ServiceEmailPolicy":
        return replace(self, disabled_actions=frozenset(actions))

    # -- action-scoped authorization --------------------------------------

    def required_scope(self, action: Action) -> str:
        try:
            return _ACTION_SCOPES[Action(action)]
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Unknown action: {action!r}") from exc

    def authorize(self, action: Action) -> str:
        """Return the OAuth scope for *action*, or raise if the policy
        disables it. Raising here means the client never reaches the API."""
        act = Action(action)
        if act in self.disabled_actions:
            raise PermissionError(f"Action '{act.value}' is disabled by service-email policy")
        return self.required_scope(act)

    # -- outbound guard ----------------------------------------------------

    def guard_outbound(self, recipient: str) -> None:
        """Guard every outbound send. Raises unless outbound is enabled and
        the recipient is a syntactically valid, injection-free address."""
        if not self.allow_outbound:
            raise PermissionError(
                "Outbound sending is disabled by service-email policy (allow_outbound=false)"
            )
        if not recipient or not _EMAIL_RE.match(recipient):
            # Do NOT include the recipient value in the message — avoid leaking
            # runtime-only addresses into logs/tracebacks.
            raise ValueError("Outbound recipient is missing or not a valid e-mail address")

    # -- sign-up guard (policy decision) ----------------------------------

    def guard_signup(self, service: str) -> None:
        if not self.allow_autonomous_signups:
            raise PermissionError(
                "Autonomous sign-ups are disabled by service-email policy"
            )
        if not service:
            raise ValueError("A service identifier is required to authorize a sign-up")

    # -- full-mailbox content filtering -----------------------------------

    def is_sensitive(self, text: str) -> bool:
        if not text:
            return False
        return any(re.search(p, text, re.IGNORECASE) for p in self.sensitive_patterns)

    def apply_content_policy(self, message: dict) -> dict:
        """Return a filtered *copy* of *message*. If the body (or subject)
        matches a sensitive-content heuristic, the body is redacted and a
        ``policy_redacted`` flag is set. The input is never mutated."""
        filtered = dict(message)
        body = filtered.get("body", "") or ""
        subject = filtered.get("subject", "") or ""
        if self.is_sensitive(body) or self.is_sensitive(subject):
            filtered["body"] = _REDACTION
            filtered["policy_redacted"] = True
        else:
            filtered["policy_redacted"] = False
        return filtered

    # -- retention ---------------------------------------------------------

    def retention_cutoff(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        return now - timedelta(days=self.raw_retention_days)

    def is_expired(self, message_ts: datetime, now: datetime | None = None) -> bool:
        return message_ts < self.retention_cutoff(now)
