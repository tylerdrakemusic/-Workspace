#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Python = $null,
    [Parameter(Mandatory = $true)][string]$Manifest,
    [string]$SourceRoot = $null,
    [string[]]$ProjectRoot = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

foreach ($name in @('WORKSPACE_BACKUP_VOLUME', 'WORKSPACE_BACKUP_VOLUME_ID', 'WORKSPACE_BACKUP_MANIFEST_KEY')) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($name, 'User')
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Set-Item -Path ('Env:' + $name) -Value $value
        }
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required environment variable: $name"
    }
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = [Environment]::GetEnvironmentVariable('WORKSPACE_BACKUP_PYTHON', 'Process')
    if ([string]::IsNullOrWhiteSpace($Python)) {
        $Python = [Environment]::GetEnvironmentVariable('WORKSPACE_BACKUP_PYTHON', 'User')
    }
}
if ([string]::IsNullOrWhiteSpace($Python) -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Configured Python interpreter is unavailable to the scheduled task identity.'
}

$volume = [IO.Path]::GetFullPath($env:WORKSPACE_BACKUP_VOLUME)
$canonical = [IO.Path]::GetFullPath('E:\WorkspaceBackup')
if ($volume.TrimEnd('\') -ine $canonical.TrimEnd('\')) {
    throw "Backup volume must be E:\WorkspaceBackup; refusing fallback destination."
}
if (-not (Test-Path -LiteralPath $volume -PathType Container)) {
    throw "Backup volume is unavailable: $volume"
}
$marker = Join-Path $volume '.backup-volume-identity'
if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
    throw "Trusted backup volume marker is absent: $marker"
}
if ((Get-Content -LiteralPath $marker -Raw).Trim() -cne $env:WORKSPACE_BACKUP_VOLUME_ID) {
    throw 'Trusted backup volume marker does not match WORKSPACE_BACKUP_VOLUME_ID.'
}

$runnerArguments = @(
    '--manifest', $Manifest,
    '--volume-root', $volume
)
if ($ProjectRoot.Count -gt 0) {
    if (-not [string]::IsNullOrWhiteSpace($SourceRoot)) {
        throw 'SourceRoot and ProjectRoot cannot be combined.'
    }
    foreach ($root in $ProjectRoot) {
        $runnerArguments += @('--project-root', $root)
    }
} elseif ($null -ne $SourceRoot) {
    $runnerArguments += @('--source-root', $SourceRoot)
} else {
    throw 'SourceRoot or ProjectRoot is required.'
}

& $Python (Join-Path $PSScriptRoot 'run_database_backup.py') @runnerArguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }