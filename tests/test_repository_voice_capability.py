from __future__ import annotations

from src.integrations.ai_manifest.repository_voice_capability import (
    create_repository_voice_injection,
)


def test_overseer_blocking_gate_injects_registered_capability_once() -> None:
    calls: list[tuple[object, ...]] = []

    def submit_repository_voice(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append((*args, kwargs))
        return {"accepted": True}

    injection = create_repository_voice_injection(submit_repository_voice)
    workflow_result = {"state": "WAITING_FOR_TYLER", "text": "Approve deploy"}

    first = injection.overseer_blocking_decision(
        "overseer-decision-1",
        workflow_result["text"],
        workflow_result,
        repository_voice_authorized=True,
        voice_alert_authorized=True,
    )
    second = injection.overseer_blocking_decision(
        "overseer-decision-1",
        workflow_result["text"],
        workflow_result,
        repository_voice_authorized=True,
        voice_alert_authorized=True,
    )

    assert first.workflow_result is workflow_result
    assert second.workflow_result is workflow_result
    assert first.voice_status == "queued"
    assert second.voice_status == "skipped"
    assert calls == [
        (
            "overseer-decision-1",
            "Approve deploy",
            {"voice_id": "21m00Tcm4TlvDq8ikWAM"},
        )
    ]


def test_ci_blocking_gate_requires_both_authorization_flags() -> None:
    calls: list[tuple[object, ...]] = []

    def submit_repository_voice(*args: object, **kwargs: object) -> None:
        calls.append((*args, kwargs))

    injection = create_repository_voice_injection(submit_repository_voice)
    workflow_result = {"state": "BLOCKED", "text": "Approve remediation"}

    result = injection.ci_blocking_decision(
        "ci-decision-1",
        workflow_result["text"],
        workflow_result,
        repository_voice_authorized=True,
        voice_alert_authorized=False,
    )

    assert result.workflow_result is workflow_result
    assert result.voice_status == "skipped"
    assert calls == []


def test_injected_timeout_preserves_ci_workflow_result() -> None:
    from threading import Event

    def hanging_submit(*args: object, **kwargs: object) -> None:
        Event().wait(10)

    workflow_result = {"state": "BLOCKED", "text": "Approve remediation"}
    injection = create_repository_voice_injection(
        hanging_submit,
        timeout_seconds=0.01,
    )

    result = injection.ci_blocking_decision(
        "ci-decision-timeout",
        workflow_result["text"],
        workflow_result,
        repository_voice_authorized=True,
        voice_alert_authorized=True,
    )

    assert result.workflow_result is workflow_result
    assert result.voice_status == "timeout"


def test_structured_mcp_rejection_is_fail_open() -> None:
    def reject_repository_voice(*args: object, **kwargs: object) -> dict[str, object]:
        return {"accepted": False, "error": "queue unavailable"}

    workflow_result = {"state": "WAITING_FOR_TYLER"}
    injection = create_repository_voice_injection(reject_repository_voice)

    result = injection.overseer_blocking_decision(
        "overseer-decision-rejected",
        "Approve deploy",
        workflow_result,
        repository_voice_authorized=True,
        voice_alert_authorized=True,
    )

    assert result.workflow_result is workflow_result
    assert result.voice_status == "failed"
    assert result.voice_error == "queue unavailable"