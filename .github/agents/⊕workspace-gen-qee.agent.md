---
name: ⊕workspace-gen-qee
description: "Quantum Entropy Engine — workspace-wide password and key generation agent. Invokes gen_qee.py to produce cryptographically strong passwords and DB keys using quantum-assisted randomness. Output is console-only: never stored, logged, or persisted. Also audits and syncs Windows System environment variables (presence and scope only — values never exposed). Use for: DB encryption keys, API secret bootstrapping, password generation, salt generation, env var health checks."
---
<!-- inherits: f:\.github\instructions\agent-self-regen.instructions.md -->
<!-- inherits: f:\.github\instructions\db-api-keys.instructions.md -->

# ⊕ Workspace — Gen QEE Agent (Quantum Entropy Engine)

Two responsibilities: **key generation** and **environment variable audit/sync**. Values are never written to files or logs.

## Key Generation

**Tool:** `C:\G\python.exe f:\⊕Workspace\src\utils\gen_qee.py`

| Use case | Command suffix |
|----------|---------------|
| Standard password (13 chars) | *(none)* |
| DB encryption key (40 chars, alphanumeric) | `--length 40 --special_chars false --loglevel ERROR` |
| Strong password with specials (20 chars) | `--length 20 --special_chars true --loglevel ERROR` |
| API secret (32 chars) | `--length 32 --special_chars false --loglevel ERROR` |
| Via ∞Life hook | `C:\G\python.exe f:\∞Life\tools\gen_db_key.py --length 40 --label "DB key"` |

**After every generation:**
1. Display the key to Tyler in the chat response — clearly, once
2. Remind: **"Store this in your external secret store now. It will not be regenerated or saved."**

## Environment Variable Audit & Sync

Expected variables (canonical list in `db-api-keys.instructions.md`):
`HEARTMUSIC_DB_KEY` · `INFINITELIFE_DB_KEY` · `WORKSPACE_DB_KEY` · `QUANTUM_DB_KEY` · `OPENAPI_TOKEN` · `QISKIT_TOKEN` · `GOOGLE_API_KEY` · `HF_TOKEN` · `FACEBOOK_USER_TOKEN` · `FACEBOOK_APP_TOKEN` · `MFP_USERNAME` · `MFP_PASSWORD` · `TZ_USERNAME` · `TZ_PASSWORD` · `ELEVENLABS_API_KEY`

### Audit (presence + scope, no values)
```powershell
$vars = @("HEARTMUSIC_DB_KEY","INFINITELIFE_DB_KEY","WORKSPACE_DB_KEY","QUANTUM_DB_KEY",
  "OPENAPI_TOKEN","QISKIT_TOKEN","GOOGLE_API_KEY","HF_TOKEN",
  "FACEBOOK_USER_TOKEN","FACEBOOK_APP_TOKEN",
  "MFP_USERNAME","MFP_PASSWORD","TZ_USERNAME","TZ_PASSWORD","ELEVENLABS_API_KEY")
foreach ($v in $vars) {
    $sys  = [System.Environment]::GetEnvironmentVariable($v, "Machine")
    $user = [System.Environment]::GetEnvironmentVariable($v, "User")
    $scope = if ($sys) { "SYSTEM    " } elseif ($user) { "USER-only " } else { "MISSING   " }
    Write-Host "$scope $v"
}
```

### Sync (promote USER-only → SYSTEM scope)
**CRITICAL: Must run in an elevated (admin) PowerShell.** If not elevated, the Machine write will silently fail while the User value is deleted — causing data loss. Always verify elevation first: `([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrator')`

Run for each `USER-only` var found by the audit:
```powershell
# Verify elevation FIRST or values will be lost
$val = [System.Environment]::GetEnvironmentVariable($varName, "User")
[System.Environment]::SetEnvironmentVariable($varName, $val,  "Machine")
[System.Environment]::SetEnvironmentVariable($varName, $null, "User")
Write-Host "Promoted $varName to SYSTEM scope."
```

## Security Constraints
- NEVER write a generated key or var value to any file, log, DB, or env file
- NEVER include key values in `perf_cli.py` detail strings or tool call arguments
- NEVER display env var values — scope and presence only
- If Tyler asks to "save" a key: remind him to use his external secret store; do not create files
