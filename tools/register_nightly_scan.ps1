#Requires -Version 5.1
<#
.SYNOPSIS
    Register (or update) the ⊕Workspace nightly security scan as a Windows
    Scheduled Task. Idempotent — safe to re-run; updates the existing task.

.DESCRIPTION
    Task name : ⊕Workspace-SecurityScan
    Schedule  : Daily at 02:30 local time
    User      : Current logged-in user (needs access to WORKSPACE_DB_KEY)
    Script    : f:\⊕Workspace\src\utils\security_scan_nightly.py
    Python    : C:\G\python.exe

    Run once to install:
        .\register_nightly_scan.ps1

    To verify registration:
        Get-ScheduledTask -TaskName '⊕Workspace-SecurityScan'

    To run immediately for a smoke test:
        Start-ScheduledTask -TaskName '⊕Workspace-SecurityScan'
        Start-Sleep 10
        Get-ScheduledTaskInfo -TaskName '⊕Workspace-SecurityScan'
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName   = [char]0x2295 + 'Workspace-SecurityScan'   # ⊕Workspace-SecurityScan
$Python     = 'C:\G\python.exe'
$Script     = 'f:\⊕Workspace\src\utils\security_scan_nightly.py'
$RunTime    = '02:30'
$WorkingDir = 'f:\⊕Workspace'

# ── Validate prerequisites ─────────────────────────────────────────────────────
if (-not (Test-Path $Python)) {
    Write-Error "Python not found at $Python — update the `$Python variable."
    exit 1
}
if (-not (Test-Path $Script)) {
    Write-Error "Scanner script not found at $Script — check the repo checkout."
    exit 1
}

# ── Build task components ──────────────────────────────────────────────────────
$action  = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument $Script `
    -WorkingDirectory $WorkingDir

$trigger = New-ScheduledTaskTrigger -Daily -At $RunTime

# Pass PYTHONUTF8=1 so sigil paths in log output don't corrupt on cp1252 consoles.
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -WakeToRun:$false

# Principal: run as current user; log on only when user is logged on.
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

# ── Register (or update) the task ─────────────────────────────────────────────
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existing) {
    Write-Host "Updating existing task: $TaskName"
    Set-ScheduledTask `
        -TaskName $TaskName `
        -Action   $action   `
        -Trigger  $trigger  `
        -Settings $settings | Out-Null
} else {
    Write-Host "Registering new task: $TaskName"
    Register-ScheduledTask `
        -TaskName  $TaskName  `
        -Action    $action    `
        -Trigger   $trigger   `
        -Settings  $settings  `
        -Principal $principal `
        -Description 'Nightly bandit+safety scan across all 5 workspace project roots. Writes new vulns to workspace.db vulnerabilities table and logs/security_nightly.log.' |
        Out-Null
}

# ── Confirm ────────────────────────────────────────────────────────────────────
$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host ''
Write-Host "Task registered successfully." -ForegroundColor Green
Write-Host "  Name          : $TaskName"
Write-Host "  Next run time : $($info.NextRunTime)"
Write-Host "  Last run      : $($info.LastRunTime)"
Write-Host "  Last result   : $($info.LastTaskResult)"
Write-Host ''
Write-Host "To test immediately: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Log file: f:\⊕Workspace\logs\security_nightly.log"
