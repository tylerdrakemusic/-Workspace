# Provider-Neutral AI Health Contract

## Purpose

The AI Health widget exposes a small provider-neutral readiness projection for
the Workspace portal. The projection answers whether a configured provider is
ready for its advertised capabilities. It does not perform generation, deliver
voice, or establish a cross-repository runtime dependency.

## Contract Boundary

The Workspace adapter owns the widget-facing projection. AI-Manifest owns an
equivalent local producer shape in `src/integrations/provider_health.py`. The
two repositories agree by shape only: Workspace does not import AI-Manifest at
runtime, and AI-Manifest does not become a Workspace service dependency.

The current provider adapter is ElevenLabs. It performs an authenticated,
non-generative request to `/v1/user`, bounded to eight seconds per attempt and
at most one retry for transient provider failures.

## Result Shape

Each readiness result contains:

| Field | Meaning |
| --- | --- |
| `provider` | Stable provider identifier, currently `elevenlabs`. |
| `state` | One normalized state: `ready`, `degraded`, `unavailable`, or `unknown`. |
| `latency_ms` | Measured request latency, or `null` when no measurement is available. |
| `quota` | Optional normalized `{used, limit}` character counts; `null` when unavailable or malformed. |
| `capabilities` | Provider capability names, currently `voice_synthesis`, `voice_listing`, and `streaming`. |
| `freshness` | `live` for the bounded check result. |
| `diagnostic_code` | A safe, allowlisted reason code, or `null` for a healthy result. |

Unknown input states normalize to `unknown` rather than escaping the contract.

## Normalized States

- `ready`: the provider responded successfully and returned valid quota data.
- `degraded`: the provider responded with a transient or other provider error,
  or returned malformed quota data after the bounded check.
- `unavailable`: credentials are missing or authentication failed.
- `unknown`: transport, parsing, or unexpected failures prevent a reliable
  readiness conclusion.

## Safe Diagnostics

The widget renders only allowlisted diagnostic codes such as
`missing_credentials`, `authentication_failed`, `provider_unavailable`,
`provider_error`, `quota_malformed`, `transport_error`, and
`unexpected_error`. It never renders API keys, response bodies, exception
details, authorization headers, or provider payloads. Missing values render as
an unavailable quota or an em dash for latency.

## Freshness And Persistence

`freshness: live` means the result came from the current bounded readiness
check. This contract is an in-memory result shape and introduces no persistence,
schema migration, polling loop, or durable readiness state. Existing generic
endpoint history used by the portal's broader health display is separate from
this contract and does not change its fields or ownership.

## Widget Integration

At portal generation time, the Workspace dashboard combines the existing
endpoint display row with the ElevenLabs readiness result. The widget presents
normalized state, latency, quota, capabilities, freshness, and the safe reason
code. A failed readiness check is isolated so portal rendering can still
complete.

## Explicit Exclusions

This contract does not include persistence changes, schema migration, polling,
Executive Audio Brief behavior, repository voice delivery, audio playback,
TTS queue operations, or unrelated portal navigation behavior.