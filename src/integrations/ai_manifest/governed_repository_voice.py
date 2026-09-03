"""Fail-open bridge for governed repository voice on blocking decisions."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Thread
from typing import Any, Callable, Generic, TypeVar


WorkflowResult = TypeVar("WorkflowResult")
MAX_REPOSITORY_VOICE_TEXT_LENGTH = 280
DEFAULT_REPOSITORY_VOICE_TIMEOUT_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class GovernedRepositoryVoiceResult(Generic[WorkflowResult]):
    """Return the unchanged workflow result and best-effort voice outcome."""

    decision_id: str
    workflow_result: WorkflowResult
    voice_status: str
    voice_error: str | None = None

    @property
    def alert_status(self) -> str:
        """Expose the former result field for existing consumers."""
        return self.voice_status

    @property
    def alert_error(self) -> str | None:
        """Expose the former result field for existing consumers."""
        return self.voice_error


def enqueue_blocking_decision_repository_voice(
    decision_id: str,
    text: str,
    workflow_result: WorkflowResult,
    *,
    enqueue_capability: Callable[..., Any],
    blocking_decision: bool,
    repository_voice_authorized: bool | None = None,
    voice_alert_authorized: bool | None = None,
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",
    timeout_seconds: float = DEFAULT_REPOSITORY_VOICE_TIMEOUT_SECONDS,
) -> GovernedRepositoryVoiceResult[WorkflowResult]:
    """Best-effort enqueue one authorized repository-voice message."""
    authorized = (
        repository_voice_authorized
        if repository_voice_authorized is not None
        else voice_alert_authorized
    )
    if not blocking_decision or not authorized:
        return GovernedRepositoryVoiceResult(decision_id, workflow_result, "skipped")
    if not decision_id.strip() or not text.strip() or len(text) > MAX_REPOSITORY_VOICE_TEXT_LENGTH:
        return GovernedRepositoryVoiceResult(decision_id, workflow_result, "failed")

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

    Thread(target=enqueue, daemon=True, name="overseer-repository-voice").start()
    completed.wait(timeout=max(0.0, timeout_seconds))
    if not completed.is_set():
        return GovernedRepositoryVoiceResult(decision_id, workflow_result, "timeout")
    if failure:
        return GovernedRepositoryVoiceResult(decision_id, workflow_result, "failed")
    if submission and getattr(submission[0], "accepted", True) is False:
        return GovernedRepositoryVoiceResult(
            decision_id,
            workflow_result,
            "failed",
            getattr(submission[0], "error", None),
        )
    return GovernedRepositoryVoiceResult(decision_id, workflow_result, "queued")


MAX_ALERT_TEXT_LENGTH = MAX_REPOSITORY_VOICE_TEXT_LENGTH
DEFAULT_ALERT_TIMEOUT_SECONDS = DEFAULT_REPOSITORY_VOICE_TIMEOUT_SECONDS
VoiceAlertBridgeResult = GovernedRepositoryVoiceResult
enqueue_blocking_decision_alert = enqueue_blocking_decision_repository_voice


__all__ = [
    "DEFAULT_REPOSITORY_VOICE_TIMEOUT_SECONDS",
    "MAX_REPOSITORY_VOICE_TEXT_LENGTH",
    "GovernedRepositoryVoiceResult",
    "enqueue_blocking_decision_repository_voice",
    "DEFAULT_ALERT_TIMEOUT_SECONDS",
    "MAX_ALERT_TEXT_LENGTH",
    "VoiceAlertBridgeResult",
    "enqueue_blocking_decision_alert",
]