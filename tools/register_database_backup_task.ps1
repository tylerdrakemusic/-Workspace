#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName = [char]0x2295 + 'Workspace-DatabaseBackup'
$Python = 'C:\G\python.exe'
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot 'run_database_backup.ps1'
$Manifest = Join-Path $WorkspaceRoot 'src\config\database_backup_scope.json'
$SourceRoot = Split-Path -Parent $WorkspaceRoot

foreach ($name in @('WORKSPACE_BACKUP_VOLUME', 'WORKSPACE_BACKUP_VOLUME_ID', 'WORKSPACE_BACKUP_MANIFEST_KEY')) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Set required environment variable before registration: $name"
    }
}

$action = New-ScheduledTaskAction -Execute 'PowerShell.exe' -Argument (
    "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`" -Python `"$Python`" -Manifest `"$Manifest`" -SourceRoot `"$SourceRoot`""
)
$trigger = New-ScheduledTaskTrigger -Daily -At '02:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force `
    -Description 'Daily manifest-driven local database backup to the trusted E:\WorkspaceBackup volume.' | Out-Null
Write-Host "Registered $TaskName for daily 02:00 local execution."