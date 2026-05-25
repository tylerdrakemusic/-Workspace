#Requires -Version 5.1
<#
.SYNOPSIS
    Register (or update) the Proof Artifact Staleness Verifier as a Windows
    Scheduled Task. Idempotent — safe to re-run; updates the existing task.

.DESCRIPTION
    Task name : ProofHealthVerifier
    Schedule  : Weekly on Sunday at 04:00 local time (after WorkspaceHygiene @ 03:00)
    User      : Current logged-in user (needs WORKSPACE_DB_KEY in env)
    Script    : f:\⊕Workspace\src\utils\proof_health_verifier.py
    Python    : C:\G\python.exe
    Output    : f:\⊕Workspace\reports\proof_health.json
               f:\⊕Workspace\logs\proof_health.log

    Run once (as yourself — admin not required for per-user tasks):
        .\register_proof_health_task.ps1

    To verify registration:
        Get-ScheduledTask -TaskName 'ProofHealthVerifier'

    To run immediately for a smoke test:
        Start-ScheduledTask -TaskName 'ProofHealthVerifier'
        Start-Sleep -Seconds 30
        Get-ScheduledTaskInfo -TaskName 'ProofHealthVerifier'

    To inspect the last report:
        Get-Content 'f:\⊕Workspace\reports\proof_health.json' | ConvertFrom-Json

    To inspect the log:
        Get-Content 'f:\⊕Workspace\logs\proof_health.log' -Tail 20

    To unregister:
        Unregister-ScheduledTask -TaskName 'ProofHealthVerifier' -Confirm:$false

FR: FR-20260524-proof-artifact-staleness-verifier
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName   = 'ProofHealthVerifier'
$Python     = 'C:\G\python.exe'
$Script     = 'f:\⊕Workspace\src\utils\proof_health_verifier.py'
$RunDay     = 'Sunday'
$RunTime    = '04:00'
$WorkingDir = 'f:\⊕Workspace'

# ── Validate prerequisites ─────────────────────────────────────────────────────
if (-not (Test-Path $Python)) {
    Write-Error "Python not found at $Python — update the `$Python variable."
    exit 1
}
if (-not (Test-Path $Script)) {
    Write-Error "Verifier script not found at $Script — ensure the repo is checked out."
    exit 1
}
if (-not $env:WORKSPACE_DB_KEY) {
    Write-Warning "WORKSPACE_DB_KEY is not set in the current environment."
    Write-Warning "The scheduled task runs as the current user and will inherit their environment."
    Write-Warning "Ensure WORKSPACE_DB_KEY is set as a User or System environment variable."
}

# ── Build task components ──────────────────────────────────────────────────────
$action = New-ScheduledTaskAction `
    -Execute          $Python `
    -Argument         $Script `
    -WorkingDirectory $WorkingDir

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $RunDay -At $RunTime

# PYTHONUTF8=1 ensures sigil paths in stdout don't corrupt on cp1252 consoles.
# ExecutionTimeLimit: 10 min is generous; normally finishes in a few seconds.
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit        (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -WakeToRun:$false `
    -MultipleInstances         IgnoreNew

# Run as current user, interactive logon only (inherits env vars incl. DB keys).
$principal = New-ScheduledTaskPrincipal `
    -UserId   ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

# ── Register (or update) the task ─────────────────────────────────────────────
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existing) {
    Write-Host "Updating existing task: $TaskName"
    Set-ScheduledTask `
        -TaskName  $TaskName `
        -Action    $action   `
        -Trigger   $trigger  `
        -Settings  $settings | Out-Null
} else {
    Write-Host "Registering new task: $TaskName"
    Register-ScheduledTask `
        -TaskName    $TaskName   `
        -Action      $action     `
        -Trigger     $trigger    `
        -Settings    $settings   `
        -Principal   $principal  `
        -Description ('Weekly proof_artifacts staleness sweep. Checks every ' +
                      'artifact_path for existence and SHA-256 hash match. ' +
                      'Writes reports/proof_health.json and exits 1 if ' +
                      'failure rate exceeds 10%. ' +
                      'FR: FR-20260524-proof-artifact-staleness-verifier') | Out-Null
}

# ── Confirm ────────────────────────────────────────────────────────────────────
$info = Get-ScheduledTaskInfo -TaskName $TaskName
$task = Get-ScheduledTask    -TaskName $TaskName

Write-Host ''
Write-Host "Task         : $($task.TaskName)"
Write-Host "State        : $($task.State)"
Write-Host "Schedule     : $RunDay $RunTime"
Write-Host "Script       : $Script"
Write-Host "Last Run     : $($info.LastRunTime)"
Write-Host "Last Result  : $($info.LastTaskResult)"
Write-Host "Next Run     : $($info.NextRunTime)"
Write-Host ''
Write-Host "Registration complete. Run a smoke test with:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
