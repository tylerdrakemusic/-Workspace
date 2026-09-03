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