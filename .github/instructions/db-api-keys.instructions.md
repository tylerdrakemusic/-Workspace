---
description: "DB encryption keys and API token reference for all workspace agents. All values are Windows System Environment Variables — never in code or .env values."
applyTo: ".github/agents/*.agent.md"
---

# Workspace DB Keys & API Tokens

## Database Keys

| DB | Env Var | Path |
|----|---------|------|
| ❤Music | `HEARTMUSIC_DB_KEY` | `f:\❤Music\src\data\heartmusic.db` |
| ∞Life | `INFINITELIFE_DB_KEY` | `f:\∞Life\src\data\infinitelife.db` |
| ⊕Workspace | `WORKSPACE_DB_KEY` | `f:\⊕Workspace\src\data\workspace.db` |
| ⟨ψ⟩Quantum | `QUANTUM_DB_KEY` | `f:\⟨ψ⟩Quantum\src\data\quantumpsi.db` |

Keys live in Windows System Environment Variables — never in code or `.env` values. Reference stubs at `f:\.env`. Set via:
```powershell
[System.Environment]::SetEnvironmentVariable("KEY_NAME", "value", "Machine")
```
Generate new keys: `⊕workspace-gen-qee`.

### Scope Status (audited 2026-05-19)
| Scope | Var |
|-------|-----|
| ✅ SYSTEM | `WORKSPACE_DB_KEY` |
| ⚠️ USER-only — needs sync | `HEARTMUSIC_DB_KEY` |
| ⚠️ USER-only — needs sync | `INFINITELIFE_DB_KEY` |
| ⚠️ USER-only — needs sync | `QUANTUM_DB_KEY` |

## API Keys & Tokens

| Key | Scope | Env scope |
|-----|-------|-----------|
| `OPENAPI_TOKEN` | All projects — OpenAI | ⚠️ USER-only |
| `QISKIT_TOKEN` | ⟨ψ⟩Quantum — IBM Quantum | ⚠️ USER-only |
| `GOOGLE_API_KEY` | All projects — Google APIs | ⚠️ USER-only |
| `HF_TOKEN` | 👁AI-Manifest, ⟨ψ⟩Quantum — Hugging Face | ⚠️ USER-only |
| `FACEBOOK_USER_TOKEN` | ❤Music — social/promo | ⚠️ USER-only |
| `FACEBOOK_APP_TOKEN` | ❤Music — social/promo | ⚠️ USER-only |
| `MFP_USERNAME` / `MFP_PASSWORD` | ∞Life — MyFitnessPal nutrition sync | ⚠️ USER-only |
| `TZ_USERNAME` / `TZ_PASSWORD` | ∞Life — TrainingZones | ⚠️ USER-only |
| `ELEVENLABS_API_KEY` | 👁AI-Manifest — voice synthesis | ✅ SYSTEM |

> **Sync needed:** 13 vars are USER-only scope. Run the `⊕workspace-gen-qee` env var sync in an elevated terminal to promote them all to SYSTEM.
