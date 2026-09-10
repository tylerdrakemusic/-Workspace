"""Provider-neutral bounded structured events and local JSONL sink."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import threading
from time import monotonic
from typing import Any, Callable, Iterator
import uuid


_REDACTED = "[REDACTED]"
_SENSITIVE_NAMES = {
    "account", "account_hash", "account_id", "account_number", "access_token",
    "api_key", "authorization", "broker_order_id", "client_secret", "password",
    "payload", "raw_payload", "refresh_token", "secret", "token",
}
_ALLOWED_FIELD_NAMES = {
    "attempt", "eligible_pair_count", "exception_type", "execution_mode",
    "intent_type", "outcome", "queued_count", "reason", "sequence", "status",
}
_SEVERITIES = {"debug", "info", "warning", "error", "critical"}
_OUTCOMES = {"started", "succeeded", "failed", "blocked", "retried", "shed", "healthy", "unhealthy"}


@contextmanager
def observed_boundary(
    emit: Callable[..., str | None],
    event_name: str,
    *,
    stage: str,
    fields: dict[str, Any] | None = None,
    severity: str = "info",
    retry_count: int = 0,
    retry_limit: int = 0,
) -> Iterator[str | None]:
    """Emit causal start and terminal events around one boundary."""
    started_at = monotonic()
    started_event_id = emit(
        f"{event_name}.started", stage=stage, outcome="started", fields=fields or {},
        severity=severity, retry_count=retry_count, retry_limit=retry_limit,
    )
    try:
        yield started_event_id
    except Exception as exc:
        emit(
            f"{event_name}.failed", causation_id=started_event_id, stage=stage,
            outcome="failed", fields=fields or {}, severity="error",
            duration_ms=max(0, int((monotonic() - started_at) * 1000)),
            exception_class=type(exc).__name__, retry_count=retry_count,
            retry_limit=retry_limit,
        )
        raise
    else:
        emit(
            f"{event_name}.completed", causation_id=started_event_id, stage=stage,
            outcome="succeeded", fields=fields or {}, severity=severity,
            duration_ms=max(0, int((monotonic() - started_at) * 1000)),
            retry_count=retry_count, retry_limit=retry_limit,
        )


def make_event_emitter(
    sink: Any,
    *,
    component: str,
    correlation_id: str,
    actor: str,
    source: str,
) -> Callable[..., str]:
    """Create an adapter that builds events and writes them to ``sink``."""
    def emit(event_name: str, **kwargs: Any) -> str:
        event = StructuredEvent.create(
            event_name=event_name, component=component, correlation_id=correlation_id,
            actor=actor, source=source, **kwargs,
        )
        sink.write(event)
        return event.event_id

    return emit


def _is_sensitive_name(name: str) -> bool:
    normalized = name.lower().replace("-", "_")
    return normalized in _SENSITIVE_NAMES or any(
        marker in normalized for marker in ("token", "secret", "password", "account_hash")
    )


def _redact(name: str, value: Any) -> Any:
    normalized = name.lower().replace("-", "_")
    if _is_sensitive_name(name) or normalized not in _ALLOWED_FIELD_NAMES:
        return _REDACTED
    if isinstance(value, dict):
        return {str(key): _redact(str(key), item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(name, item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return _REDACTED


@dataclass(frozen=True)
class StructuredEvent:
    """A versioned event with explicit correlation and causation identity."""

    event_name: str
    component: str
    event_id: str
    correlation_id: str
    causation_id: str | None
    occurred_at: str
    schema_version: int
    severity: str
    stage: str
    outcome: str
    duration_ms: int
    exception_class: str | None
    retry: dict[str, int]
    actor: str
    source: str
    fields: dict[str, Any]

    @classmethod
    def create(
        cls, *, event_name: str, component: str, correlation_id: str,
        fields: dict[str, Any], causation_id: str | None = None,
        event_id: str | None = None, occurred_at: datetime | None = None,
        severity: str = "info", stage: str = "operation", outcome: str = "started",
        duration_ms: int = 0, exception_class: str | None = None,
        retry_count: int = 0, retry_limit: int = 0, actor: str = "system",
        source: str = "workspace",
    ) -> "StructuredEvent":
        if not event_name.strip():
            raise ValueError("event_name is required")
        if not component.strip():
            raise ValueError("component is required")
        if not correlation_id.strip():
            raise ValueError("correlation_id is required")
        severity = severity.strip().lower()
        if severity not in _SEVERITIES:
            raise ValueError("severity is invalid")
        stage = stage.strip()
        if not stage:
            raise ValueError("stage is required")
        outcome = outcome.strip().lower()
        if outcome not in _OUTCOMES:
            raise ValueError("outcome is invalid")
        if not isinstance(duration_ms, int) or duration_ms < 0:
            raise ValueError("duration_ms must be a non-negative integer")
        if exception_class is not None and not str(exception_class).strip():
            raise ValueError("exception_class must be non-empty when provided")
        if not isinstance(retry_count, int) or retry_count < 0:
            raise ValueError("retry_count must be a non-negative integer")
        if not isinstance(retry_limit, int) or retry_limit < 0:
            raise ValueError("retry_limit must be a non-negative integer")
        if retry_count > retry_limit and retry_limit != 0:
            raise ValueError("retry_count cannot exceed retry_limit")
        actor = actor.strip()
        source = source.strip()
        if not actor or not source:
            raise ValueError("actor and source are required")
        timestamp = occurred_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return cls(
            event_name=event_name.strip(), component=component.strip(),
            event_id=event_id or str(uuid.uuid4()), correlation_id=correlation_id.strip(),
            causation_id=causation_id.strip() if causation_id else None,
            occurred_at=timestamp.astimezone(timezone.utc).isoformat(), schema_version=2,
            severity=severity, stage=stage, outcome=outcome, duration_ms=duration_ms,
            exception_class=str(exception_class) if exception_class else None,
            retry={"count": retry_count, "limit": retry_limit}, actor=actor, source=source,
            fields={str(key): _redact(str(key), value) for key, value in fields.items()},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "event_name": self.event_name,
            "component": self.component, "event_id": self.event_id,
            "correlation_id": self.correlation_id, "causation_id": self.causation_id,
            "occurred_at": self.occurred_at, "severity": self.severity, "stage": self.stage,
            "outcome": self.outcome, "duration_ms": self.duration_ms,
            "exception_class": self.exception_class, "retry": self.retry,
            "actor": self.actor, "source": self.source, "fields": self.fields,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class SinkStats:
    written_events: int
    dropped_events: int
    dropped_bytes: int
    malformed_events: int = 0
    shed_oldest_events: int = 0


class BoundedLocalSink:
    """Write JSONL events to a bounded rotating local file set."""

    def __init__(
        self, path: str | os.PathLike[str], *, max_bytes: int = 1_048_576,
        max_files: int = 5, min_free_bytes: int = 0,
        disk_usage: Callable[[str | os.PathLike[str]], Any] | None = None,
    ) -> None:
        if max_bytes < 128 or max_files < 1 or min_free_bytes < 0:
            raise ValueError("invalid bounded sink limits")
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.min_free_bytes = min_free_bytes
        self._disk_usage = disk_usage or shutil.disk_usage
        self._lock = threading.Lock()
        self._written_events = 0
        self._dropped_events = 0
        self._dropped_bytes = 0
        self._malformed_events = 0
        self._shed_oldest_events = 0

    def _files(self) -> list[Path]:
        candidates = [self.path]
        candidates.extend(self.path.with_name(f"{self.path.name}.{index}") for index in range(1, self.max_files))
        return [candidate for candidate in candidates if candidate.exists()]

    def _discard_oldest_file(self, candidate: Path) -> None:
        try:
            with candidate.open("rb") as handle:
                self._shed_oldest_events += sum(1 for _ in handle)
        except OSError:
            pass
        candidate.unlink(missing_ok=True)

    def _prune(self) -> None:
        files = sorted(self._files(), key=lambda candidate: candidate.stat().st_mtime, reverse=True)
        for candidate in files[self.max_files:]:
            self._discard_oldest_file(candidate)
        total = 0
        for candidate in sorted(self._files(), key=lambda item: item.stat().st_mtime, reverse=True):
            total += candidate.stat().st_size
            if total > self.max_bytes * self.max_files:
                self._discard_oldest_file(candidate)

    def _rotate(self) -> None:
        for index in range(self.max_files - 1, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            target = self.path.with_name(f"{self.path.name}.{index + 1}")
            if source.exists():
                if index + 1 >= self.max_files:
                    self._discard_oldest_file(source)
                else:
                    source.replace(target)
        if self.path.exists():
            self.path.replace(self.path.with_name(f"{self.path.name}.1"))

    def write(self, event: StructuredEvent) -> bool:
        try:
            if not isinstance(event, StructuredEvent):
                raise TypeError("event must be StructuredEvent")
            encoded = event.to_dict()
            required = {"schema_version", "severity", "stage", "outcome", "duration_ms", "exception_class", "retry", "actor", "source"}
            if not required.issubset(encoded):
                raise ValueError("event schema is incomplete")
            data = (event.to_json() + "\n").encode("utf-8")
        except (TypeError, ValueError):
            with self._lock:
                self._malformed_events += 1
            return False
        with self._lock:
            try:
                free_bytes = int(self._disk_usage(self.path.parent).free)
            except (OSError, AttributeError, TypeError, ValueError):
                free_bytes = self.min_free_bytes
            if free_bytes < self.min_free_bytes or len(data) > self.max_bytes:
                self._dropped_events += 1
                self._dropped_bytes += len(data)
                return False
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size + len(data) > self.max_bytes:
                    self._rotate()
                with self.path.open("ab") as handle:
                    handle.write(data)
                self._prune()
            except OSError:
                self._dropped_events += 1
                self._dropped_bytes += len(data)
                return False
            self._written_events += 1
            return True

    def stats(self) -> SinkStats:
        with self._lock:
            return SinkStats(self._written_events, self._dropped_events, self._dropped_bytes, self._malformed_events, self._shed_oldest_events)

    def health(self) -> dict[str, Any]:
        stats = self.stats()
        return {
            "healthy": stats.dropped_events == 0 and stats.malformed_events == 0,
            "writable": self.path.parent.exists() or not self.path.parent,
            "written_events": stats.written_events, "dropped_events": stats.dropped_events,
            "malformed_events": stats.malformed_events, "shed_oldest_events": stats.shed_oldest_events,
        }


def build_sink(default_path: str | os.PathLike[str]) -> BoundedLocalSink:
    """Build a bounded sink from Workspace-neutral environment settings."""
    def positive_int(name: str, default: int, minimum: int) -> int:
        try:
            value = int(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default
        return value if value >= minimum else default

    return BoundedLocalSink(
        os.environ.get("WORKSPACE_STRUCTURED_LOG_PATH", str(default_path)),
        max_bytes=positive_int("WORKSPACE_STRUCTURED_LOG_MAX_BYTES", 1_048_576, 128),
        max_files=positive_int("WORKSPACE_STRUCTURED_LOG_MAX_FILES", 5, 1),
        min_free_bytes=positive_int("WORKSPACE_STRUCTURED_LOG_MIN_FREE_BYTES", 0, 0),
    )


build_pilot_sink = build_sink

__all__ = [
    "BoundedLocalSink", "SinkStats", "StructuredEvent", "build_pilot_sink",
    "build_sink", "make_event_emitter", "observed_boundary",
]