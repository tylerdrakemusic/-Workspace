# Governed Overseer Repository Voice Contract

This contract defines the Workspace-side boundary for governed repository voice.

- A message is eligible only when the workflow has reached a blocking decision
  that requires Tyler's input. Ordinary status events never enqueue repository
  voice messages.
- The workflow supplies a stable decision identifier. The bridge forwards that
  identifier unchanged so the governed capability can preserve deduplication
  and audit identity.
- Enqueue requires explicit repository-voice authorization in addition to the
  blocking-decision gate. Authorization is not inferred from workflow state.
- The text approval or request is preserved immediately in the workflow result
  and remains authoritative. Repository voice is an additional notification
  channel, not the source of truth.
- Repository-voice enqueue is best effort and fail open. A capability error,
  invalid payload, or timeout reports a voice outcome while returning the
  unchanged workflow result.
- Repository-voice failure and timeout must never mutate workflow state or block
  the workflow indefinitely. The bridge uses a bounded wait for the injected
  governed capability.

## Runtime Injection

Workspace runtime setup creates one injection from the MCP-facing
`submit_repository_voice` callable:

```python
from src.integrations.ai_manifest.repository_voice_capability import (
  create_repository_voice_injection,
)

repository_voice = create_repository_voice_injection(submit_repository_voice)
result = repository_voice.overseer_blocking_decision(
  decision_id,
  text_request,
  workflow_result,
  repository_voice_authorized=True,
  voice_alert_authorized=True,
)
```

CI uses `ci_blocking_decision` with the same contract. Each injection
deduplicates a stable decision ID and requires both authorization flags. No
ordinary-status method is exposed, and the injected callable remains the only
delivery capability; Workspace never calls ElevenLabs directly.