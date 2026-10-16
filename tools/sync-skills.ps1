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
$configPath = if ($ConfigPath) { [IO.Path]::GetFullPath($ConfigPath) } else { Join-Path $scriptDir "skill-sync-config.json" }
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

function Get-SyncPreflight {
    $output = & $pythonExecutable $manifestUpdater --preflight-sync-config $configPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Skill sync path preflight failed: $($output -join ' ')"
    }
    try {
        return (($output -join [Environment]::NewLine) | ConvertFrom-Json)
    } catch {
        throw "Skill sync path preflight returned invalid output: $_"
    }
}

$config = Get-SyncPreflight
$configRoot = $config.workspace_root
$logFile = $config.log_file
$destination = $config.destination
$manifestPath = if ($ManifestPath) {
    [IO.Path]::GetFullPath($ManifestPath)
} else {
    Join-Path $configRoot ".github\!!☾⛧security\agent-manifest.json"
}
$repoRoot = if ($ManifestPath) {
    Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $manifestPath))
} else {
    $configRoot
}
$script:logReady = $false
$script:logBuffer = [System.Collections.Generic.List[string]]::new()

function Write-Log {
    param([string]$msg)
    $line = "[$timestamp] $msg"
    Write-Host $line
    if ($script:logReady) {
        Add-Content -Path $logFile -Value $line -Encoding UTF8
    } else {
        $null = $script:logBuffer.Add($line)
    }
}

function Resolve-PinnedSource {
    param(
        [string]$RepositoryPath,
        [string]$PinnedCommit,
        [string]$SourceRelativePath,
        [object]$PinnedSources
    )

    if ([string]::IsNullOrWhiteSpace($PinnedCommit)) {
        throw "Pinned source is missing pinned_commit for $RepositoryPath"
    }

    $gitPath = $SourceRelativePath.Replace("\", "/")
    & git -C $RepositoryPath cat-file -e "$PinnedCommit^{commit}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Pinned commit $PinnedCommit is unavailable in $RepositoryPath"
    }
    & git -C $RepositoryPath cat-file -e "$PinnedCommit`:$gitPath" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Pinned source $gitPath is unavailable at commit $PinnedCommit"
    }

    $worktreePath = Join-Path ([IO.Path]::GetTempPath()) ("skill-sync-" + [Guid]::NewGuid().ToString("N"))
    $null = $PinnedSources.Add([pscustomobject]@{
        RepositoryPath = $RepositoryPath
        Worktree = $worktreePath
    })
    New-Item -ItemType Directory -Force -Path $worktreePath | Out-Null
    & git -c core.autocrlf=false -C $RepositoryPath worktree add --detach --quiet $worktreePath $PinnedCommit 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to materialize pinned commit $PinnedCommit in $RepositoryPath"
    }

    $sourcePath = Join-Path $worktreePath $gitPath
    $resolvedSource = & $pythonExecutable $manifestUpdater `
        --confine-path $sourcePath `
        --root $worktreePath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Pinned source path preflight failed: $($resolvedSource -join ' ')"
    }
    $sourcePath = ($resolvedSource -join [Environment]::NewLine).Trim()
    if (-not (Test-Path $sourcePath -PathType Leaf)) {
        throw "Pinned source $gitPath was not materialized at commit $PinnedCommit"
    }
    return [pscustomobject]@{ Path = $sourcePath; Worktree = $worktreePath }
}

function Remove-PinnedSource {
    param(
        [string]$RepositoryPath,
        [string]$WorktreePath
    )

    if ($WorktreePath) {
        & git -C $RepositoryPath worktree remove --force $WorktreePath 2>$null | Out-Null
        Remove-Item -Recurse -Force $WorktreePath -ErrorAction SilentlyContinue
    }
}

Write-Log "=== skill-sync start ==="

foreach ($repo in $config.repos) {
    Write-Log "--- $($repo.name) ---"

    # Clone if not present, otherwise pull (skip if remote is null — shared path)
    $repoPath = $repo.path
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
}

<# Re-resolve after repository updates, then write only from the validated plan. #>
$config = Get-SyncPreflight
$destination = $config.destination

$syncPlan = [System.Collections.Generic.List[object]]::new()
$pinnedSources = [System.Collections.Generic.List[object]]::new()

try {
    foreach ($repo in $config.repos) {
        $repoPath = $repo.path
        foreach ($mapping in $repo.mappings) {
            $src = $mapping.source
            if ($repo.pinned_commit -or $repo.sha256) {
                if (-not $repo.pinned_commit -or -not $repo.sha256) {
                    throw "Pinned source $($repo.name) must declare both pinned_commit and sha256"
                }
                $pinnedSource = Resolve-PinnedSource `
                    $repoPath `
                    $repo.pinned_commit `
                    $mapping.source_relative_path `
                    $pinnedSources
                $src = $pinnedSource.Path
                $actualHash = (Get-FileHash -Path $src -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actualHash -ne $repo.sha256.ToLowerInvariant()) {
                    throw "Pinned source hash mismatch for $($repo.name): expected $($repo.sha256), got $actualHash"
                }
            }
            $null = $syncPlan.Add([pscustomobject]@{
                RepositoryName = $repo.name
                Provenance = $repo.provenance
                Skill = $mapping.skill
                Source = $src
                Target = $mapping.target
            })
        }
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
    foreach ($line in $script:logBuffer) {
        Add-Content -Path $logFile -Value $line -Encoding UTF8
    }
    $script:logBuffer.Clear()
    $script:logReady = $true

    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    foreach ($mapping in $syncPlan) {
        $skill = $mapping.Skill
        $src = $mapping.Source
        $destFile = $mapping.Target
        $destDir = Split-Path -Parent $destFile

        if (-not (Test-Path $src)) {
            Write-Log "WARN: $src not found — skipping $skill"
            continue
        }

        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        if ((Test-Path $destFile) -and $ApproveProtectedSync -and $mapping.Provenance -ne "external-source") {
            Write-Log "SKIP: approved overwrite is limited to external-source skill $destFile"
            continue
        }
        if ((Test-Path $destFile) -and -not $ApproveProtectedSync) {
            Write-Log "DRY-RUN: existing protected skill $destFile — use -ApproveProtectedSync to overwrite"
            continue
        }
        Copy-Item $src $destFile -Force
        Write-Log "Copied $skill from $($mapping.RepositoryName)"
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
} finally {
    foreach ($pinnedSource in $pinnedSources) {
        Remove-PinnedSource $pinnedSource.RepositoryPath $pinnedSource.Worktree
    }
}

Write-Log "=== skill-sync complete ==="
