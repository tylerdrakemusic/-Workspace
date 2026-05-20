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

## Audit & Sync Scripts

### Audit (presence + scope — no values exposed)
```powershell
$vars = @("HEARTMUSIC_DB_KEY","INFINITELIFE_DB_KEY","WORKSPACE_DB_KEY","QUANTUM_DB_KEY",
  "OPENAPI_TOKEN","GITHUB_TOKEN","GOOGLE_API_KEY","HF_TOKEN","ELEVENLABS_API_KEY",
  "QISKIT_TOKEN","IBM_CLOUD_API_KEY","IBM_QUANTUM_INSTANCE",
  "FACEBOOK_USER_TOKEN","FACEBOOK_APP_TOKEN",
  "INFINITELIFE_VAULT_KEY",
  "GARMIN_EMAIL","GARMIN_PASSWORD","GARMIN_COOKIE","GARMIN_JWT",
  "WITHINGS_CLIENT_ID","WITHINGS_SECRET","WITHINGS_ACCESS_TOKEN","WITHINGS_REFRESH_TOKEN","WITHINGS_USER_ID",
  "MFP_USERNAME","MFP_PASSWORD","MFP_SESSION_TOKEN","MFP_CF_CLEARANCE",
  "TZ_USERNAME","TZ_PASSWORD")
foreach ($v in $vars) {
    $sys  = [System.Environment]::GetEnvironmentVariable($v, "Machine")
    $user = [System.Environment]::GetEnvironmentVariable($v, "User")
    $scope = if ($sys) { "SYSTEM    " } elseif ($user) { "USER-only " } else { "MISSING   " }
    Write-Host "$scope $v"
}
```

### Sync — promote USER-only → SYSTEM (elevated Admin PS required)
**CRITICAL: Verify elevation first or User values will be deleted without being written to SYSTEM.**
```powershell
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrator')
```
```powershell
# Promote a single var
$val = [System.Environment]::GetEnvironmentVariable($varName, "User")
[System.Environment]::SetEnvironmentVariable($varName, $val,  "Machine")
[System.Environment]::SetEnvironmentVariable($varName, $null, "User")
Write-Host "Promoted $varName to SYSTEM."
```
```powershell
# Promote all USER-only vars matching a prefix (e.g. GARMIN)
Get-ChildItem "HKCU:\Environment" | ForEach-Object { $_.GetValueNames() } | Where-Object { $_ -like "PREFIX*" } | ForEach-Object {
    $val = [System.Environment]::GetEnvironmentVariable($_, "User")
    [System.Environment]::SetEnvironmentVariable($_, $val, "Machine")
    [System.Environment]::SetEnvironmentVariable($_, $null, "User")
    Write-Host "Promoted $_ to SYSTEM"
}
```

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
