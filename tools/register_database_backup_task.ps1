#Requires -Version 5.1
param(
    [ValidateSet('❤Music', '⟨ψ⟩Quantum', '👁AI-Manifest', '⊕Workspace')]
    [string]$ApprovedProject = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName = [char]0x2295 + 'Workspace-DatabaseBackup'
$Python = 'C:\G\python.exe'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$workspaceContainer = Split-Path -Parent $WorkspaceRoot
if ((Split-Path -Leaf $workspaceContainer) -eq '.worktrees') {
    $WorkspaceRoot = Split-Path -Parent $workspaceContainer
}
$Launcher = Join-Path $WorkspaceRoot 'tools\run_database_backup.ps1'
$Manifest = Join-Path $WorkspaceRoot 'src\config\database_backup_scope.json'
$ProjectRoots = if ($ApprovedProject) {
    @(
        if ($ApprovedProject -eq '❤Music') {
            ([char]0x2764 + "Music=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) ([char]0x2764 + "Music")))
        } elseif ($ApprovedProject -eq '⟨ψ⟩Quantum') {
            ("⟨ψ⟩Quantum=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) "⟨ψ⟩Quantum"))
        } elseif ($ApprovedProject -eq '👁AI-Manifest') {
            ("👁AI-Manifest=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) "👁AI-Manifest"))
        } else {
            ("⊕Workspace=" + $WorkspaceRoot)
        }
    )
} else {
    @(
        ([char]0x2764 + "Music=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) ([char]0x2764 + "Music"))),
        ("⟨ψ⟩Quantum=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) "⟨ψ⟩Quantum")),
        ("👁AI-Manifest=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) "👁AI-Manifest")),
        ("⊕Workspace=" + $WorkspaceRoot)
    )
}
$ProjectRootArguments = '-ProjectRoot ' + ($ProjectRoots -join ',')

foreach ($name in @('WORKSPACE_BACKUP_VOLUME', 'WORKSPACE_BACKUP_VOLUME_ID', 'WORKSPACE_BACKUP_MANIFEST_KEY')) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($name, 'User')
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Set required environment variable before registration: $name"
    }
}

$action = New-ScheduledTaskAction -Execute 'PowerShell.exe' -Argument (
    "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`" -Python `"$Python`" -Manifest `"$Manifest`" $ProjectRootArguments"
)
$trigger = New-ScheduledTaskTrigger -Daily -At '02:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force `
    -Description 'Daily manifest-driven local database backup to the trusted E:\WorkspaceBackup volume.' | Out-Null
Write-Host "Registered $TaskName for daily 02:00 local execution."