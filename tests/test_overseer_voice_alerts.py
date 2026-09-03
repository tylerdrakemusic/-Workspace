from __future__ import annotations

from dataclasses import dataclass
from threading import Event

from src.integrations.ai_manifest.overseer_voice_alerts import enqueue_blocking_decision_alert


@dataclass(frozen=True)
class StructuredRejection:
    accepted: bool
    error: str


def test_voice_enqueue_failure_preserves_blocking_decision_result() -> None:
    def failing_enqueue(**_: object) -> None:
        raise RuntimeError("manifest capability unavailable")

    workflow_result = {"state": "WAITING_FOR_TYLER", "text_approval": "Approve deploy"}

    result = enqueue_blocking_decision_alert(
        "decision-42",
        "Approve deploy",
        workflow_result,
        enqueue_capability=failing_enqueue,
        blocking_decision=True,
        voice_alert_authorized=True,
    )

    assert result.workflow_result is workflow_result
    assert result.decision_id == "decision-42"
    assert result.alert_status == "failed"


def test_structured_enqueue_rejection_preserves_workflow_and_reports_error() -> None:
    workflow_result = {"state": "WAITING_FOR_TYLER", "text_approval": "Approve deploy"}

    def rejecting_enqueue(*_: object, **__: object) -> StructuredRejection:
        return StructuredRejection(accepted=False, error="queue unavailable")

    result = enqueue_blocking_decision_alert(
        "decision-structured-rejection",
        "Approve deploy",
        workflow_result,
        enqueue_capability=rejecting_enqueue,
        blocking_decision=True,
        voice_alert_authorized=True,
    )

    assert result.workflow_result is workflow_result
    assert result.alert_status == "failed"
    assert result.alert_error == "queue unavailable"


def test_authorized_blocking_decision_forwards_stable_id_and_concise_text() -> None:
    calls: list[tuple[object, ...]] = []

    def enqueue(*args: object, **kwargs: object) -> None:
        calls.append((*args, kwargs))

    workflow_result = "WAITING_FOR_TYLER"
    result = enqueue_blocking_decision_alert(
        "decision-7",
        "Approve the release",
        workflow_result,
        enqueue_capability=enqueue,
        blocking_decision=True,
        voice_alert_authorized=True,
        voice_id="voice-1",
    )

    assert result.alert_status == "queued"
    assert result.workflow_result == workflow_result
    assert calls == [("decision-7", "Approve the release", {"voice_id": "voice-1"})]


def test_unauthorized_blocking_decision_is_not_enqueued() -> None:
    calls: list[object] = []

    def enqueue(*args: object, **kwargs: object) -> None:
        calls.extend((args, kwargs))

    result = enqueue_blocking_decision_alert(
        "decision-9",
        "Approve the release",
        "WAITING_FOR_TYLER",
        enqueue_capability=enqueue,
        blocking_decision=True,
        voice_alert_authorized=False,
    )

    assert result.alert_status == "skipped"
    assert calls == []


def test_invalid_or_oversized_alert_is_not_enqueued() -> None:
    calls: list[object] = []

    def enqueue(*args: object, **kwargs: object) -> None:
        calls.extend((args, kwargs))

    for text in ("   ", "x" * 281):
        result = enqueue_blocking_decision_alert(
            "decision-10",
            text,
            "WAITING_FOR_TYLER",
            enqueue_capability=enqueue,
            blocking_decision=True,
            voice_alert_authorized=True,
        )

        assert result.alert_status == "failed"

    assert calls == []


def test_unscoped_status_event_is_not_enqueued() -> None:
    calls: list[object] = []

    def enqueue(*args: object, **kwargs: object) -> None:
        calls.extend((args, kwargs))

    result = enqueue_blocking_decision_alert(
        "status-7",
        "Routine status update",
        "RUNNING",
        enqueue_capability=enqueue,
        blocking_decision=False,
        voice_alert_authorized=True,
    )

    assert result.alert_status == "skipped"
    assert calls == []


def test_voice_capability_timeout_does_not_block_workflow() -> None:
    started = Event()

    def hanging_enqueue(*args: object, **kwargs: object) -> None:
        started.set()
        Event().wait(10)

    result = enqueue_blocking_decision_alert(
        "decision-8",
        "Approve the release",
        {"state": "WAITING_FOR_TYLER"},
        enqueue_capability=hanging_enqueue,
        blocking_decision=True,
        voice_alert_authorized=True,
        timeout_seconds=0.01,
    )

    assert started.wait(0.1)
    assert result.alert_status == "timeout"