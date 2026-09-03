---
description: "Shared governed repository-voice contract for workspace agents."
applyTo: ".github/agents/*.agent.md"
---

# Governed Repository Voice

Use the repository voice only as an optional, additional communication channel
when a workflow reaches a blocking decision that genuinely requires Tyler's
input. Keep the normal text request authoritative.

```python
from src.integrations.ai_manifest.governed_repository_voice import (
    enqueue_blocking_decision_repository_voice,
)

workflow_result = run_workflow()
voice_result = enqueue_blocking_decision_repository_voice(
    decision_id=<stable-decision-id>,
    text=<concise-text-request>,
    workflow_result=workflow_result,
    enqueue_capability=<ai_manifest_mcp_repository_voice_callable>,
    blocking_decision=True,
    repository_voice_authorized=True,
)
return voice_result.workflow_result  # unchanged workflow result
```

The `enqueue_capability` value must be the governed AI-Manifest MCP-facing
repository-voice callable that submits to the existing AI-Manifest TTS queue.
It is an injected capability supplied by the integration boundary, not the
bridge function itself. Never call ElevenLabs directly or create ad hoc audio
files.

The decision ID must be stable so retries deduplicate. Voice use is bounded and
fail open: timeout, rejection, synthesis failure, playback failure, or queue
failure must leave the text request, workflow result, and workflow state
unchanged, and must never block the agent indefinitely. Treat the returned
`voice_status` and `voice_error` as diagnostics only.

Blocking decisions are the first authorized repository-voice consumer. Ordinary
status narration is out of scope until separately authorized.