# Agent Handoff Protocol

The workspace handoff protocol has three durable layers:

1. `HandoffStore.create_envelope` records a versioned envelope containing
   routing metadata, an allowlisted context object, and a SHA-256 digest.
2. `HandoffStore.publish_result` records inbound or outbound result metadata
   and a digest. Raw result payloads are never stored.
3. `OperationalRuntime.takeover_resume` can resume only a lifecycle record that
   has already been recovered as `stale`. It requires both
   `takeover_enabled: true` in the operational policy and explicit approval.

The SQLite tables are `agent_handoff_envelopes` and `agent_handoff_results`.
Envelope rows are immutable: repeating an identical handoff is idempotent,
while a changed handoff with the same ID is rejected. Result rows are
append-only and preserve direction and insertion order.

Health, medical, genomic, financial, account, credential, password, secret,
token, and API-key values are rejected recursively in envelope contexts and
result objects. The durable schema intentionally has no raw `payload` or
`result` column. Existing FR approval, QA, review, merge, soak, and signoff
gates remain outside this execution mechanism.