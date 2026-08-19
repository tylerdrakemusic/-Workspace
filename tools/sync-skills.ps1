#Requires -Version 5.1
# sync-skills.ps1 — git pull each skill repo and copy registered SKILL.md files
# into .github/skills/. Driven by skill-sync-config.json.

param(
    [switch]$ApproveProtectedSync
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $scriptDir "skill-sync-config.json"
$config = Get-Content $configPath -Encoding UTF8 | ConvertFrom-Json

$logFile = $config.log_file
$destination = $config.destination
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log {
    param([string]$msg)
    $line = "[$timestamp] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
New-Item -ItemType Directory -Force -Path $destination | Out-Null

Write-Log "=== skill-sync start ==="

foreach ($repo in $config.repos) {
    Write-Log "--- $($repo.name) ---"

    # Clone if not present, otherwise pull (skip if remote is null — shared path)
    if ($null -ne $repo.remote -and $repo.remote -ne "") {
        if (-not (Test-Path $repo.path)) {
            Write-Log "Cloning $($repo.remote) -> $($repo.path)"
            git clone $repo.remote $repo.path 2>&1 | ForEach-Object { Write-Log $_ }
        } else {
            Push-Location $repo.path
            try {
                Write-Log "git pull origin main"
                git pull origin main 2>&1 | ForEach-Object { Write-Log $_ }
            } finally {
                Pop-Location
            }
        }
    } else {
        Write-Log "Skipping pull (shared repo path, already pulled by sibling entry)"
    }

    # Copy each registered skill's SKILL.md
    foreach ($skill in $repo.skills) {
        $src = Join-Path $repo.path "$($repo.skill_root)\$skill\SKILL.md"
        $destDir = Join-Path $destination $skill
        $destFile = Join-Path $destDir "SKILL.md"

        if (-not (Test-Path $src)) {
            Write-Log "WARN: $src not found — skipping $skill"
            continue
        }

        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        if ((Test-Path $destFile) -and -not $ApproveProtectedSync) {
            Write-Log "DRY-RUN: existing protected skill $destFile — use -ApproveProtectedSync to overwrite"
            continue
        }
        Copy-Item $src $destFile -Force
        Write-Log "Copied $skill from $($repo.name)"
    }
}

Write-Log "=== skill-sync complete ==="
