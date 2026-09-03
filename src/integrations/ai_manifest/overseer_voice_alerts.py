"""Fail-open bridge for concise voice alerts on blocking decisions."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Thread
from typing import Any, Callable, Generic, TypeVar


WorkflowResult = TypeVar("WorkflowResult")
MAX_ALERT_TEXT_LENGTH = 280
DEFAULT_ALERT_TIMEOUT_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class VoiceAlertBridgeResult(Generic[WorkflowResult]):
    """Return the unchanged workflow result and the best-effort alert outcome."""

    decision_id: str
    workflow_result: WorkflowResult
    alert_status: str
    alert_error: str | None = None


def enqueue_blocking_decision_alert(
    decision_id: str,
    text: str,
    workflow_result: WorkflowResult,
    *,
    enqueue_capability: Callable[..., Any],
    blocking_decision: bool,
    voice_alert_authorized: bool,
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",
    timeout_seconds: float = DEFAULT_ALERT_TIMEOUT_SECONDS,
) -> VoiceAlertBridgeResult[WorkflowResult]:
    """Best-effort enqueue one authorized alert without changing workflow state."""
    if not blocking_decision or not voice_alert_authorized:
        return VoiceAlertBridgeResult(decision_id, workflow_result, "skipped")
    if not decision_id.strip() or not text.strip() or len(text) > MAX_ALERT_TEXT_LENGTH:
        return VoiceAlertBridgeResult(decision_id, workflow_result, "failed")

    completed = Event()
    failure: list[BaseException] = []
    submission: list[Any] = []

    def enqueue() -> None:
        try:
            submission.append(enqueue_capability(decision_id, text, voice_id=voice_id))
        except BaseException as exc:
            failure.append(exc)
        finally:
            completed.set()

    Thread(target=enqueue, daemon=True, name="overseer-voice-alert").start()
    completed.wait(timeout=max(0.0, timeout_seconds))
    if not completed.is_set():
        return VoiceAlertBridgeResult(decision_id, workflow_result, "timeout")
    if failure:
        return VoiceAlertBridgeResult(decision_id, workflow_result, "failed")
    if submission and getattr(submission[0], "accepted", True) is False:
        return VoiceAlertBridgeResult(
            decision_id,
            workflow_result,
            "failed",
            getattr(submission[0], "error", None),
        )
    return VoiceAlertBridgeResult(decision_id, workflow_result, "queued")


__all__ = [
    "DEFAULT_ALERT_TIMEOUT_SECONDS",
    "MAX_ALERT_TEXT_LENGTH",
    "VoiceAlertBridgeResult",
    "enqueue_blocking_decision_alert",
]