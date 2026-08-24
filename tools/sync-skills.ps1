#Requires -Version 5.1
# sync-skills.ps1 — git pull each skill repo and copy registered SKILL.md files
# into .github/skills/. Driven by skill-sync-config.json.

param(
    [switch]$ApproveProtectedSync,
    [string]$ConfigPath,
    [string]$ManifestPath
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = if ($ConfigPath) { $ConfigPath } else { Join-Path $scriptDir "skill-sync-config.json" }
$config = Get-Content $configPath -Encoding UTF8 | ConvertFrom-Json

function Resolve-ConfiguredPath {
    param(
        [object]$Value,
        [string]$Root
    )

    $configuredValue = $Value
    if ($Value -is [pscustomobject]) {
        $environmentName = $Value.env
        $environmentValue = if ($environmentName) { [Environment]::GetEnvironmentVariable($environmentName) } else { $null }
        $configuredValue = if ($environmentValue) { $environmentValue } else { $Value.relative }
    }

    if ([IO.Path]::IsPathRooted($configuredValue)) {
        return [IO.Path]::GetFullPath($configuredValue)
    }
    return [IO.Path]::GetFullPath((Join-Path $Root $configuredValue))
}

$configDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($configPath))
$defaultRoot = Split-Path -Parent $configDirectory
$configRoot = Resolve-ConfiguredPath $config.workspace_root $defaultRoot
$logFile = Resolve-ConfiguredPath $config.log_file $configRoot
$destination = Resolve-ConfiguredPath $config.destination $configRoot
$manifestPath = if ($ManifestPath) {
    $ManifestPath
} else {
    Join-Path $configRoot ".github\!!☾⛧security\agent-manifest.json"
}
$repoRoot = if ($ManifestPath) {
    Split-Path -Parent (Split-Path -Parent (Split-Path -Parent ([IO.Path]::GetFullPath($ManifestPath))))
} else {
    $configRoot
}
$manifestUpdater = Join-Path (Split-Path $scriptDir -Parent) ".github\!!☾⛧security\update_manifest.py"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$pythonExecutable = if ($env:PYTHON_EXECUTABLE) {
    $env:PYTHON_EXECUTABLE
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    (Get-Command python).Source
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    (Get-Command python3).Source
} else {
    throw "Python executable not found; set PYTHON_EXECUTABLE or install python"
}

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
    $repoPath = Resolve-ConfiguredPath $repo.path $repoRoot
    if ($null -ne $repo.remote -and $repo.remote -ne "") {
        if (-not (Test-Path $repoPath)) {
            Write-Log "Cloning $($repo.remote) -> $repoPath"
            git clone $repo.remote $repoPath 2>&1 | ForEach-Object { Write-Log $_ }
        } else {
            Push-Location $repoPath
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
        $src = Join-Path $repoPath "$($repo.skill_root)\$skill\SKILL.md"
        $destDir = Join-Path $destination $skill
        $destFile = Join-Path $destDir "SKILL.md"

        if (-not (Test-Path $src)) {
            Write-Log "WARN: $src not found — skipping $skill"
            continue
        }

        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        if ((Test-Path $destFile) -and $ApproveProtectedSync -and $repo.provenance -ne "external-source") {
            Write-Log "SKIP: approved overwrite is limited to external-source skill $destFile"
            continue
        }
        if ((Test-Path $destFile) -and -not $ApproveProtectedSync) {
            Write-Log "DRY-RUN: existing protected skill $destFile — use -ApproveProtectedSync to overwrite"
            continue
        }
        Copy-Item $src $destFile -Force
        Write-Log "Copied $skill from $($repo.name)"
        if ($ApproveProtectedSync) {
            & $pythonExecutable $manifestUpdater `
                --update-files $destFile `
                --manifest $manifestPath `
                --repo-root $repoRoot 2>&1 | ForEach-Object { Write-Log $_ }
            if ($LASTEXITCODE -ne 0) {
                throw "Manifest update failed for $destFile"
            }
        }
    }
}

Write-Log "=== skill-sync complete ==="
