"""Inject the governed AI-Manifest repository-voice callable into workflows."""

from __future__ import annotations

from threading import Lock
from typing import Any, Callable, Generic, TypeVar

from .governed_repository_voice import (
    GovernedRepositoryVoiceResult,
    enqueue_blocking_decision_repository_voice,
)


WorkflowResult = TypeVar("WorkflowResult")
RepositoryVoiceCallable = Callable[..., Any]


class RepositoryVoiceInjection(Generic[WorkflowResult]):
    """Provide deduplicated repository voice at authorized blocking gates."""

    def __init__(
        self,
        enqueue_capability: RepositoryVoiceCallable,
        *,
        timeout_seconds: float,
    ) -> None:
        self._enqueue_capability = enqueue_capability
        self._timeout_seconds = timeout_seconds
        self._decision_ids: set[str] = set()
        self._lock = Lock()

    def overseer_blocking_decision(
        self,
        decision_id: str,
        text: str,
        workflow_result: WorkflowResult,
        *,
        repository_voice_authorized: bool,
        voice_alert_authorized: bool,
    ) -> GovernedRepositoryVoiceResult[WorkflowResult]:
        """Notify through the injected capability for an Overseer gate."""
        return self._blocking_decision(
            decision_id,
            text,
            workflow_result,
            repository_voice_authorized=repository_voice_authorized,
            voice_alert_authorized=voice_alert_authorized,
        )

    def ci_blocking_decision(
        self,
        decision_id: str,
        text: str,
        workflow_result: WorkflowResult,
        *,
        repository_voice_authorized: bool,
        voice_alert_authorized: bool,
    ) -> GovernedRepositoryVoiceResult[WorkflowResult]:
        """Notify through the injected capability for a CI gate."""
        return self._blocking_decision(
            decision_id,
            text,
            workflow_result,
            repository_voice_authorized=repository_voice_authorized,
            voice_alert_authorized=voice_alert_authorized,
        )

    def _blocking_decision(
        self,
        decision_id: str,
        text: str,
        workflow_result: WorkflowResult,
        *,
        repository_voice_authorized: bool,
        voice_alert_authorized: bool,
    ) -> GovernedRepositoryVoiceResult[WorkflowResult]:
        if not repository_voice_authorized or not voice_alert_authorized:
            return enqueue_blocking_decision_repository_voice(
                decision_id,
                text,
                workflow_result,
                enqueue_capability=self._enqueue_capability,
                blocking_decision=False,
                repository_voice_authorized=False,
                voice_alert_authorized=False,
                timeout_seconds=self._timeout_seconds,
            )

        with self._lock:
            if decision_id in self._decision_ids:
                return enqueue_blocking_decision_repository_voice(
                    decision_id,
                    text,
                    workflow_result,
                    enqueue_capability=self._enqueue_capability,
                    blocking_decision=False,
                    repository_voice_authorized=False,
                    voice_alert_authorized=False,
                    timeout_seconds=self._timeout_seconds,
                )
            self._decision_ids.add(decision_id)

        return enqueue_blocking_decision_repository_voice(
            decision_id,
            text,
            workflow_result,
            enqueue_capability=self._enqueue_capability,
            blocking_decision=True,
            repository_voice_authorized=True,
            voice_alert_authorized=True,
            timeout_seconds=self._timeout_seconds,
        )


def create_repository_voice_injection(
    enqueue_capability: RepositoryVoiceCallable,
    *,
    timeout_seconds: float = 0.25,
) -> RepositoryVoiceInjection[Any]:
    """Create a workflow-scoped injection for the registered MCP callable."""
    return RepositoryVoiceInjection(
        enqueue_capability,
        timeout_seconds=timeout_seconds,
    )


__all__ = ["RepositoryVoiceInjection", "create_repository_voice_injection"]