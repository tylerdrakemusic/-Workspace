#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Python = 'C:\G\python.exe',
    [Parameter(Mandatory = $true)][string]$Manifest,
    [Parameter(Mandatory = $true)][string]$SourceRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

foreach ($name in @('WORKSPACE_BACKUP_VOLUME', 'WORKSPACE_BACKUP_VOLUME_ID', 'WORKSPACE_BACKUP_MANIFEST_KEY')) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
        throw "Missing required environment variable: $name"
    }
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

& $Python (Join-Path $PSScriptRoot 'run_database_backup.py') `
    --manifest $Manifest `
    --source-root $SourceRoot `
    --volume-root $volume `
    --volume-identity $env:WORKSPACE_BACKUP_VOLUME_ID
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }