#Requires -Version 5.1
<#
.SYNOPSIS
    Register (or update) the ⊕Workspace weekly hygiene sweep as a Windows
    Scheduled Task. Idempotent — safe to re-run; updates the existing task.

.DESCRIPTION
    Task name : WorkspaceHygiene
    Schedule  : Weekly on Sunday at 03:00 local time
    User      : Current logged-in user (needs WORKSPACE_DB_KEY in env)
    Script    : f:\⊕Workspace\tools\run_hygiene.py
    Python    : C:\G\python.exe

    Run once (as yourself — admin not required for per-user tasks):
        .\register_hygiene_task.ps1

    To verify registration:
        Get-ScheduledTask -TaskName 'WorkspaceHygiene'

    To run immediately for a smoke test:
        Start-ScheduledTask -TaskName 'WorkspaceHygiene'
        Start-Sleep -Seconds 15
        Get-ScheduledTaskInfo -TaskName 'WorkspaceHygiene'

    To check the last proof artifact written:
        $env:PYTHONUTF8='1'
        C:\G\python.exe f:\⊕Workspace\src\utils\proof_cli.py report --all | Select-Object -Last 30

    To unregister:
        Unregister-ScheduledTask -TaskName 'WorkspaceHygiene' -Confirm:$false
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName   = 'WorkspaceHygiene'
$Python     = 'C:\G\python.exe'
$Script     = 'f:\⊕Workspace\tools\run_hygiene.py'
$RunDay     = 'Sunday'
$RunTime    = '03:00'
$WorkingDir = 'f:\⊕Workspace'

# ── Validate prerequisites ─────────────────────────────────────────────────────
if (-not (Test-Path $Python)) {
    Write-Error "Python not found at $Python — update the `$Python variable."
    exit 1
}
if (-not (Test-Path $Script)) {
    Write-Error "Hygiene runner not found at $Script — ensure the repo is checked out."
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
# ExecutionTimeLimit: 45 min is generous for the full sweep; normally finishes in <2 min.
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit        (New-TimeSpan -Minutes 45) `
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
        -TaskName   $TaskName  `
        -Action     $action    `
        -Trigger    $trigger   `
        -Settings   $settings  `
        -Principal  $principal `
        -Description ('Weekly ⊕Workspace mechanical hygiene sweep: tmp/ purge, log rotation, ' +
                      'git worktree prune, qbackups trim, DB health check. ' +
                      'Writes a proof_artifacts row to workspace.db on completion. ' +
                      'FR: FR-20260524-hygiene-auto-scheduler') | Out-Null
}

# ── Confirm ────────────────────────────────────────────────────────────────────
$info = Get-ScheduledTaskInfo -TaskName $TaskName
$task = Get-ScheduledTask    -TaskName $TaskName

Write-Host ''
Write-Host "Task       : $($task.TaskName)"
Write-Host "State      : $($task.State)"
Write-Host "Next run   : $($info.NextRunTime)"
Write-Host "Last run   : $($info.LastRunTime)"
Write-Host "Last result: $($info.LastTaskResult)"
Write-Host ''
Write-Host "Done. Task '$TaskName' is registered and will run every $RunDay at $RunTime."
Write-Host "Smoke test : Start-ScheduledTask -TaskName '$TaskName'"
