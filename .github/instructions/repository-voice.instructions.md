---
description: "Shared governed repository-voice contract for workspace agents."
applyTo: ".github/agents/*.agent.md"
---

# Governed Repository Voice

Use the repository voice only as an optional, additional communication channel
when a workflow reaches a blocking decision that genuinely requires Tyler's
input. Keep the normal text request authoritative.

For an authorized blocking approval, the integration boundary injects the
governed AI-Manifest MCP capability. Use this exact bounded sequence:

1. Call `start_streaming_tts` with the stable decision ID's concise text
    request and the injected voice/model settings.
2. Poll `streaming_tts_status` with the returned session ID until a terminal
    result or the configured deadline.
3. On timeout, cancellation, provider/audio failure, or any interrupted
    cleanup, call `cancel_streaming_tts` with the session ID when one exists.

The capability is injected and governed by the AI-Manifest integration. Do not
call ElevenLabs directly, create audio artifacts, or make arbitrary MCP/SQL
calls. The durable repository-voice queue is a separate implementation and
must not be used as a fallback for this approval path.

The decision ID must be stable so retries deduplicate. Voice use is bounded and
fail open: timeout, rejection, synthesis failure, playback failure, or queue
failure must leave the text request, workflow result, and workflow state
unchanged, and must never block the agent indefinitely. Treat the returned
voice result and any status/error fields as diagnostics only; normal text is
authoritative.

Blocking decisions are the first authorized repository-voice consumer. Ordinary
status narration is out of scope until separately authorized.