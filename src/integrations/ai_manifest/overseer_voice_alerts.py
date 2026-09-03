"""Compatibility imports for the former overseer voice-alert bridge."""

from .governed_repository_voice import (
    DEFAULT_ALERT_TIMEOUT_SECONDS,
    DEFAULT_REPOSITORY_VOICE_TIMEOUT_SECONDS,
    MAX_ALERT_TEXT_LENGTH,
    MAX_REPOSITORY_VOICE_TEXT_LENGTH,
    GovernedRepositoryVoiceResult,
    VoiceAlertBridgeResult,
    enqueue_blocking_decision_alert,
    enqueue_blocking_decision_repository_voice,
)


__all__ = [
    "DEFAULT_ALERT_TIMEOUT_SECONDS",
    "DEFAULT_REPOSITORY_VOICE_TIMEOUT_SECONDS",
    "MAX_ALERT_TEXT_LENGTH",
    "MAX_REPOSITORY_VOICE_TEXT_LENGTH",
    "GovernedRepositoryVoiceResult",
    "VoiceAlertBridgeResult",
    "enqueue_blocking_decision_alert",
    "enqueue_blocking_decision_repository_voice",
]