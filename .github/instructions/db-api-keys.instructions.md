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

## API Keys & Tokens

| Key | Scope |
|-----|-------|
| `OPENAPI_TOKEN` | All projects — OpenAI |
| `GITHUB_TOKEN` | All projects — GitHub API |
| `GOOGLE_API_KEY` | All projects — Google APIs |
| `HF_TOKEN` | 👁AI-Manifest, ⟨ψ⟩Quantum — Hugging Face |
| `ELEVENLABS_API_KEY` | 👁AI-Manifest — voice synthesis |
| `QISKIT_TOKEN` | ⟨ψ⟩Quantum — IBM Quantum |
| `IBM_CLOUD_API_KEY` | ⟨ψ⟩Quantum — IBM Cloud |
| `IBM_QUANTUM_INSTANCE` | ⟨ψ⟩Quantum — IBM Quantum instance CRN |
| `FACEBOOK_USER_TOKEN` | ❤Music — social/promo |
| `FACEBOOK_APP_TOKEN` | ❤Music — social/promo |
| `INFINITELIFE_VAULT_KEY` | ∞Life — QEC credential vault master key |
| `GARMIN_EMAIL` / `GARMIN_PASSWORD` | ∞Life — Garmin Connect credentials |
| `GARMIN_COOKIE` / `GARMIN_JWT` | ∞Life — Garmin session tokens |
| `WITHINGS_CLIENT_ID` / `WITHINGS_SECRET` | ∞Life — Withings OAuth app credentials |
| `WITHINGS_ACCESS_TOKEN` / `WITHINGS_REFRESH_TOKEN` | ∞Life — Withings OAuth tokens |
| `WITHINGS_USER_ID` | ∞Life — Withings user identifier |
| `MFP_USERNAME` / `MFP_PASSWORD` | ∞Life — MyFitnessPal credentials |
| `MFP_SESSION_TOKEN` / `MFP_CF_CLEARANCE` | ∞Life — MyFitnessPal session tokens |
| `TZ_USERNAME` / `TZ_PASSWORD` | ∞Life — TrainingZones credentials |
