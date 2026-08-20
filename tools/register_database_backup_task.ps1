#Requires -Version 5.1
param(
    [string]$ApprovedProject = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName = [char]0x2295 + 'Workspace-DatabaseBackup'
$LifeLabel = [char]0x221E + 'Life'
$MusicLabel = [char]0x2764 + 'Music'
$QuantumLabel = [char]0x27E8 + [char]0x03C8 + [char]0x27E9 + 'Quantum'
$ManifestLabel = [char]0xD83D + [char]0xDC41 + 'AI-Manifest'
$WorkspaceLabel = [char]0x2295 + 'Workspace'
$ApprovedProjectLabels = @($LifeLabel, $MusicLabel, $QuantumLabel, $ManifestLabel, $WorkspaceLabel)
if ($ApprovedProject -and $ApprovedProjectLabels -notcontains $ApprovedProject) {
    throw "Unknown approved project: $ApprovedProject"
}
$Python = [Environment]::GetEnvironmentVariable('WORKSPACE_BACKUP_PYTHON', 'Process')
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = [Environment]::GetEnvironmentVariable('WORKSPACE_BACKUP_PYTHON', 'Machine')
}
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = [Environment]::GetEnvironmentVariable('WORKSPACE_BACKUP_PYTHON', 'User')
}
if ([string]::IsNullOrWhiteSpace($Python) -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'WORKSPACE_BACKUP_PYTHON must reference an existing supported interpreter.'
}
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$workspaceContainer = Split-Path -Parent $WorkspaceRoot
if ((Split-Path -Leaf $workspaceContainer) -eq '.worktrees') {
    $WorkspaceRoot = Split-Path -Parent $workspaceContainer
}
$Launcher = Join-Path $WorkspaceRoot 'tools\run_database_backup.ps1'
$Manifest = Join-Path $WorkspaceRoot 'src\config\database_backup_scope.json'
$ProjectRoots = if ($ApprovedProject) {
    @(
        if ($ApprovedProject -eq $MusicLabel) {
            ($MusicLabel + "=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $MusicLabel))
        } elseif ($ApprovedProject -eq $LifeLabel) {
            ($LifeLabel + "=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $LifeLabel))
        } elseif ($ApprovedProject -eq $QuantumLabel) {
            ($QuantumLabel + "=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $QuantumLabel))
        } elseif ($ApprovedProject -eq $ManifestLabel) {
            ($ManifestLabel + "=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $ManifestLabel))
        } else {
            ($WorkspaceLabel + "=" + $WorkspaceRoot)
        }
    )
} else {
    @(
        ($LifeLabel + "=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $LifeLabel)),
        ($MusicLabel + "=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $MusicLabel)),
        ($QuantumLabel + "=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $QuantumLabel)),
        ($ManifestLabel + "=" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $ManifestLabel)),
        ($WorkspaceLabel + "=" + $WorkspaceRoot)
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
    Set-Item -Path "Env:$name" -Value $value
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