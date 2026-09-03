from __future__ import annotations

from dataclasses import dataclass
from threading import Event

from src.integrations.ai_manifest.governed_repository_voice import (
    enqueue_blocking_decision_repository_voice,
)


@dataclass(frozen=True)
class StructuredRejection:
    accepted: bool
    error: str


def test_repository_voice_api_preserves_stable_decision_and_text_request() -> None:
    calls: list[tuple[object, ...]] = []

    def enqueue(*args: object, **kwargs: object) -> None:
        calls.append((*args, kwargs))

    workflow_result = {"state": "WAITING_FOR_TYLER", "text_approval": "Approve deploy"}
    result = enqueue_blocking_decision_repository_voice(
        "decision-repository-1",
        workflow_result["text_approval"],
        workflow_result,
        enqueue_capability=enqueue,
        blocking_decision=True,
        repository_voice_authorized=True,
    )

    assert result.workflow_result is workflow_result
    assert result.decision_id == "decision-repository-1"
    assert result.voice_status == "queued"
    assert calls == [("decision-repository-1", "Approve deploy", {"voice_id": "21m00Tcm4TlvDq8ikWAM"})]


def test_enqueue_failure_preserves_blocking_decision_result() -> None:
    def failing_enqueue(**_: object) -> None:
        raise RuntimeError("manifest capability unavailable")

    workflow_result = {"state": "WAITING_FOR_TYLER", "text_approval": "Approve deploy"}
    result = enqueue_blocking_decision_repository_voice(
        "decision-42",
        "Approve deploy",
        workflow_result,
        enqueue_capability=failing_enqueue,
        blocking_decision=True,
        repository_voice_authorized=True,
    )

    assert result.workflow_result is workflow_result
    assert result.decision_id == "decision-42"
    assert result.voice_status == "failed"


def test_structured_enqueue_rejection_preserves_workflow_and_reports_error() -> None:
    workflow_result = {"state": "WAITING_FOR_TYLER", "text_approval": "Approve deploy"}

    def rejecting_enqueue(*_: object, **__: object) -> StructuredRejection:
        return StructuredRejection(accepted=False, error="queue unavailable")

    result = enqueue_blocking_decision_repository_voice(
        "decision-structured-rejection",
        "Approve deploy",
        workflow_result,
        enqueue_capability=rejecting_enqueue,
        blocking_decision=True,
        repository_voice_authorized=True,
    )

    assert result.workflow_result is workflow_result
    assert result.voice_status == "failed"
    assert result.voice_error == "queue unavailable"


def test_unauthorized_blocking_decision_is_not_enqueued() -> None:
    calls: list[object] = []

    def enqueue(*args: object, **kwargs: object) -> None:
        calls.extend((args, kwargs))

    result = enqueue_blocking_decision_repository_voice(
        "decision-9",
        "Approve the release",
        "WAITING_FOR_TYLER",
        enqueue_capability=enqueue,
        blocking_decision=True,
        repository_voice_authorized=False,
    )

    assert result.voice_status == "skipped"
    assert calls == []


def test_invalid_or_oversized_repository_voice_is_not_enqueued() -> None:
    calls: list[object] = []

    def enqueue(*args: object, **kwargs: object) -> None:
        calls.extend((args, kwargs))

    for text in ("   ", "x" * 281):
        result = enqueue_blocking_decision_repository_voice(
            "decision-10",
            text,
            "WAITING_FOR_TYLER",
            enqueue_capability=enqueue,
            blocking_decision=True,
            repository_voice_authorized=True,
        )

        assert result.voice_status == "failed"

    assert calls == []


def test_unscoped_status_event_is_not_enqueued() -> None:
    calls: list[object] = []

    def enqueue(*args: object, **kwargs: object) -> None:
        calls.extend((args, kwargs))

    result = enqueue_blocking_decision_repository_voice(
        "status-7",
        "Routine status update",
        "RUNNING",
        enqueue_capability=enqueue,
        blocking_decision=False,
        repository_voice_authorized=True,
    )

    assert result.voice_status == "skipped"
    assert calls == []


def test_repository_voice_capability_timeout_does_not_block_workflow() -> None:
    started = Event()

    def hanging_enqueue(*args: object, **kwargs: object) -> None:
        started.set()
        Event().wait(10)

    result = enqueue_blocking_decision_repository_voice(
        "decision-8",
        "Approve the release",
        {"state": "WAITING_FOR_TYLER"},
        enqueue_capability=hanging_enqueue,
        blocking_decision=True,
        repository_voice_authorized=True,
        timeout_seconds=0.01,
    )

    assert started.wait(0.1)
    assert result.voice_status == "timeout"


def test_legacy_voice_alert_api_remains_compatible() -> None:
    from src.integrations.ai_manifest.overseer_voice_alerts import enqueue_blocking_decision_alert

    result = enqueue_blocking_decision_alert(
        "legacy-1",
        "Approve the release",
        "WAITING_FOR_TYLER",
        enqueue_capability=lambda *args, **kwargs: None,
        blocking_decision=True,
        voice_alert_authorized=True,
    )

    assert result.alert_status == "queued"
