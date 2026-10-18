#Requires -Version 5.1
# sync-skills.ps1 — git pull each skill repo and copy registered SKILL.md files
# into .github/skills/. Driven by skill-sync-config.json.

param(
    [switch]$ApproveProtectedSync,
    [switch]$ApproveReviewedUpdates,
    [string[]]$ReviewedSkills,
    [string]$ReviewRationale,
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

function Assert-NoReparseComponents {
    param(
        [string]$Path,
        [string]$Root,
        [string]$Description
    )

    $normalizedInputPath = $Path.Replace('\', '/')
    if (@($normalizedInputPath -split '/') | Where-Object { $_ -in @('.', '..') }) {
        throw "$Description path must not contain dot segments: $Path"
    }
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ))
    $pathFull = [IO.Path]::GetFullPath($Path)
    $rootPrefix = $rootFull + [IO.Path]::DirectorySeparatorChar
    if (-not $pathFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Description path is outside the configured workspace: $pathFull"
    }

    $cursor = $rootFull
    $relative = $pathFull.Substring($rootPrefix.Length)
    foreach ($component in ($relative -split '[\\/]')) {
        if ([string]::IsNullOrWhiteSpace($component)) { continue }
        $cursor = Join-Path $cursor $component
        try {
            $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        } catch {
            $item = $null
        }
        if ($null -ne $item -and
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "$Description path contains a reparse point: $cursor"
        }
    }
}

function Assert-SyncWorkspaceIdentity {
    param([object]$ResolvedConfig)

    $resolvedRoot = [IO.Path]::GetFullPath([string]$ResolvedConfig.workspace_root)
    if ($resolvedRoot -ne $repoRoot) {
        throw "Skill sync workspace root changed after lock acquisition: $resolvedRoot"
    }
    $expectedConfigPath = [IO.Path]::GetFullPath(
        (Join-Path $resolvedRoot "tools\skill-sync-config.json")
    )
    $expectedManifestPath = [IO.Path]::GetFullPath(
        (Join-Path $resolvedRoot ".github\!!☾⛧security\agent-manifest.json")
    )
    if ([IO.Path]::GetFullPath($configPath) -ne $expectedConfigPath) {
        throw "Skill sync config path changed from the canonical workspace config"
    }
    if ([IO.Path]::GetFullPath($manifestPath) -ne $expectedManifestPath) {
        throw "Skill sync manifest path changed from the canonical workspace manifest"
    }
}

$configWorkspaceRoot = [IO.Path]::GetFullPath(
    (Join-Path (Split-Path -Parent $configPath) "..")
)
$canonicalConfigPath = [IO.Path]::GetFullPath(
    (Join-Path $configWorkspaceRoot "tools\skill-sync-config.json")
)
if ([IO.Path]::GetFullPath($configPath) -ne $canonicalConfigPath) {
    throw "Sync requires the canonical skill sync config path: $canonicalConfigPath"
}
Assert-NoReparseComponents $configPath $configWorkspaceRoot "Skill sync config"

$config = Get-SyncPreflight
$configRoot = $config.workspace_root
if ([IO.Path]::GetFullPath($configRoot) -ne $configWorkspaceRoot) {
    throw "Configured workspace root does not match the canonical config location"
}
$logFile = $config.log_file
$destination = $config.destination
$manifestPath = if ($ManifestPath) {
    [IO.Path]::GetFullPath($ManifestPath)
} else {
    Join-Path $configRoot ".github\!!☾⛧security\agent-manifest.json"
}
$repoRoot = [IO.Path]::GetFullPath($configRoot)
$expectedManifestPath = [IO.Path]::GetFullPath(
    (Join-Path $configRoot ".github\!!☾⛧security\agent-manifest.json")
)
if ([IO.Path]::GetFullPath($manifestPath) -ne $expectedManifestPath) {
    throw "Sync requires the canonical agent manifest path: $expectedManifestPath"
}
Assert-NoReparseComponents $manifestPath $repoRoot "Agent manifest"
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
    $blobArgs = @(
        "--write-pinned-git-blob",
        $RepositoryPath,
        $PinnedCommit,
        $gitPath,
        "--output",
        $sourcePath,
        "--root",
        $worktreePath
    )
    $blobOutput = & $pythonExecutable $manifestUpdater @blobArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Pinned Git blob materialization failed: $($blobOutput -join ' ')"
    }
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

function Enter-WorkspaceSkillSyncLock {
    param([string]$WorkspaceRoot)

    $separators = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $canonicalRoot = [IO.Path]::GetFullPath($WorkspaceRoot).TrimEnd($separators).ToLowerInvariant()
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = $hashAlgorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonicalRoot))
    } finally {
        $hashAlgorithm.Dispose()
    }
    $mutexName = "Local\WorkspaceSkillSync-" + [BitConverter]::ToString($digest).Replace("-", "")
    $mutex = [System.Threading.Mutex]::new($false, $mutexName)
    try {
        if (-not $mutex.WaitOne(0)) {
            $mutex.Dispose()
            throw "Another skill sync is active for $canonicalRoot"
        }
    } catch [System.Threading.AbandonedMutexException] {
    }
    return $mutex
}

function Exit-WorkspaceSkillSyncLock {
    param([System.Threading.Mutex]$Mutex)
    if ($null -ne $Mutex) {
        try {
            $Mutex.ReleaseMutex()
        } finally {
            $Mutex.Dispose()
        }
    }
}

function Invoke-ReviewedSkillSync {
    if ([string]::IsNullOrWhiteSpace($ReviewRationale)) {
        throw "Reviewed updates require a non-empty review rationale"
    }
    $selectedSkills = @($ReviewedSkills | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($selectedSkills.Count -eq 0 -or $selectedSkills.Count -ne @($selectedSkills | Select-Object -Unique).Count) {
        throw "Reviewed updates require unique named skills"
    }
    $expectedManifestPath = Join-Path $configRoot ".github\!!☾⛧security\agent-manifest.json"
    $expectedConfigPath = Join-Path $configRoot "tools\skill-sync-config.json"
    if (
        [IO.Path]::GetFullPath($configPath) -ne [IO.Path]::GetFullPath($expectedConfigPath) -or
        [IO.Path]::GetFullPath($manifestPath) -ne [IO.Path]::GetFullPath($expectedManifestPath) -or
        [IO.Path]::GetFullPath($repoRoot) -ne [IO.Path]::GetFullPath($configRoot)
    ) {
        throw "Reviewed updates require the canonical sync config and agent manifest under the configured workspace"
    }
    $protectedConfigPath = $configRoot
    foreach ($component in @("tools", "skill-sync-config.json")) {
        $protectedConfigPath = Join-Path $protectedConfigPath $component
        if (Test-Path -LiteralPath $protectedConfigPath) {
            $configItem = Get-Item -LiteralPath $protectedConfigPath -Force
            if ($configItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Reviewed sync config path contains a reparse point: $protectedConfigPath"
            }
        }
    }
    $protectedOutputPath = $configRoot
    foreach ($component in @(".github", "!!☾⛧security", "agent-manifest.json")) {
        $protectedOutputPath = Join-Path $protectedOutputPath $component
        if (Test-Path -LiteralPath $protectedOutputPath) {
            $outputItem = Get-Item -LiteralPath $protectedOutputPath -Force
            if ($outputItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Reviewed manifest path contains a reparse point: $protectedOutputPath"
            }
        }
    }

    $syncPlan = [System.Collections.Generic.List[object]]::new()
    $pinnedSources = [System.Collections.Generic.List[object]]::new()
    $configChanged = $false
    $syncMutex = $null
    try {
        $syncMutex = Enter-WorkspaceSkillSyncLock $repoRoot
        $config = Get-SyncPreflight
        Assert-SyncWorkspaceIdentity $config
        Assert-NoReparseComponents $configPath $repoRoot "Skill sync config"
        Assert-NoReparseComponents $manifestPath $repoRoot "Agent manifest"
        $rawConfig = Get-Content -Raw -Path $configPath | ConvertFrom-Json
        $manifest = Get-Content -Raw -Path $manifestPath | ConvertFrom-Json
        if ($null -eq $manifest.files) {
            throw "Reviewed updates require an existing manifest files map"
        }
        foreach ($skill in $selectedSkills) {
            $reviewedMappings = [System.Collections.Generic.List[object]]::new()
            foreach ($repo in $config.repos) {
                if ($repo.provenance -ne "external-source") { continue }
                foreach ($mapping in $repo.mappings) {
                    if ($mapping.skill -ceq $skill) {
                        $null = $reviewedMappings.Add([pscustomobject]@{ Repo = $repo; Mapping = $mapping })
                    }
                }
            }
            if ($reviewedMappings.Count -ne 1) {
                throw "Reviewed skill '$skill' must name exactly one configured external-source mapping"
            }

            $repo = $reviewedMappings[0].Repo
            $mapping = $reviewedMappings[0].Mapping
            $rawRepos = @($rawConfig.repos | Where-Object { $_.name -ceq $repo.name })
            if ($rawRepos.Count -ne 1) {
                throw "Reviewed source repository '$($repo.name)' is ambiguous in the sync config"
            }
            $rawRepo = $rawRepos[0]
            $hasCommit = $rawRepo.PSObject.Properties.Name -contains "pinned_commit"
            $hasSha = $rawRepo.PSObject.Properties.Name -contains "sha256"
            $source = $mapping.source
            $newCommit = ""
            $newHash = ""

            if ($hasCommit -or $hasSha) {
                if (-not $hasCommit -or -not $hasSha -or
                    [string]::IsNullOrWhiteSpace($rawRepo.pinned_commit) -or
                    [string]::IsNullOrWhiteSpace($rawRepo.sha256)) {
                    throw "Reviewed pinned source '$($repo.name)' must have a complete existing pin pair"
                }
                if ($repo.mappings.Count -ne 1) {
                    throw "Reviewed pinned repository '$($repo.name)' must map exactly one skill"
                }

                $commitOutput = & git -C $repo.path rev-parse --verify 'HEAD^{commit}' 2>&1
                if ($LASTEXITCODE -ne 0) {
                    throw "Unable to resolve reviewed candidate commit for $($repo.name): $($commitOutput -join ' ')"
                }
                $newCommit = ($commitOutput -join [Environment]::NewLine).Trim()
                & git -C $repo.path merge-base --is-ancestor $rawRepo.pinned_commit $newCommit 2>$null
                if ($LASTEXITCODE -ne 0) {
                    throw "Reviewed candidate commit $newCommit does not advance existing pin $($rawRepo.pinned_commit)"
                }
                $existingPinnedSource = Resolve-PinnedSource `
                    $repo.path `
                    $rawRepo.pinned_commit `
                    $mapping.source_relative_path `
                    $pinnedSources
                $existingPinnedHash = (Get-FileHash -Path $existingPinnedSource.Path -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($existingPinnedHash -ne ([string]$rawRepo.sha256).ToLowerInvariant()) {
                    throw "Configured SHA-256 does not match the existing pinned Git blob SHA-256 for '$($repo.name)'"
                }
                $pinnedSource = Resolve-PinnedSource `
                    $repo.path `
                    $newCommit `
                    $mapping.source_relative_path `
                    $pinnedSources
                $source = $pinnedSource.Path
                $newHash = (Get-FileHash -Path $source -Algorithm SHA256).Hash.ToLowerInvariant()
                $rawRepo.pinned_commit = $newCommit
                $rawRepo.sha256 = $newHash
                $configChanged = $true
            }

            if (-not (Test-Path $source -PathType Leaf)) {
                throw "Reviewed source for '$skill' is missing: $source"
            }
            $directorySeparator = [IO.Path]::DirectorySeparatorChar
            $alternateSeparator = [IO.Path]::AltDirectorySeparatorChar
            $separatorChars = [char[]]@($directorySeparator, $alternateSeparator)
            $rootPrefix = [IO.Path]::GetFullPath($repoRoot).TrimEnd($separatorChars) + $directorySeparator
            $targetPath = [IO.Path]::GetFullPath($mapping.target)
            $pathComparison = if ($directorySeparator -eq '\') {
                [StringComparison]::OrdinalIgnoreCase
            } else {
                [StringComparison]::Ordinal
            }
            if (-not $targetPath.StartsWith($rootPrefix, $pathComparison)) {
                throw "Reviewed target for '$skill' is outside the repository root"
            }
            $manifestKey = $targetPath.Substring($rootPrefix.Length).Replace('\', '/')
            $manifestEntry = $manifest.files.PSObject.Properties[$manifestKey]
            if ($null -eq $manifestEntry -or -not (Test-Path $targetPath -PathType Leaf)) {
                throw "Reviewed target '$manifestKey' must already exist in both the manifest and workspace"
            }
            $installedHash = (Get-FileHash -Path $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($installedHash -ne ([string]$manifestEntry.Value).ToLowerInvariant()) {
                throw "Reviewed target '$manifestKey' no longer matches its trusted manifest hash"
            }

            $null = $syncPlan.Add([pscustomobject]@{
                Skill = $skill
                RepositoryName = $repo.name
                Source = $source
                Target = $targetPath
                ManifestKey = $manifestKey
                OldCommit = [string]$repo.pinned_commit
                NewCommit = $newCommit
                OldHash = [string]$manifestEntry.Value
                NewHash = if ($newHash) { $newHash } else { (Get-FileHash -Path $source -Algorithm SHA256).Hash.ToLowerInvariant() }
            })

            foreach ($resource in @($repo.resources | Where-Object { $_.skill -ceq $skill })) {
                $pinnedResource = Resolve-PinnedSource `
                    $repo.path `
                    $resource.pinned_commit `
                    $resource.source_relative_path `
                    $pinnedSources
                $resourceHash = (Get-FileHash -Path $pinnedResource.Path -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($resourceHash -ne ([string]$resource.sha256).ToLowerInvariant()) {
                    throw "Pinned resource hash mismatch for $($repo.name): $($resource.source_relative_path)"
                }

                $resourceTarget = [IO.Path]::GetFullPath($resource.target)
                if (-not $resourceTarget.StartsWith($rootPrefix, $pathComparison)) {
                    throw "Reviewed resource target is outside the repository root: $resourceTarget"
                }
                $resourceKey = $resourceTarget.Substring($rootPrefix.Length).Replace('\', '/')
                $resourceManifestEntry = $manifest.files.PSObject.Properties[$resourceKey]
                $resourceTargetExists = Test-Path -LiteralPath $resourceTarget
                if ($resourceTargetExists -and -not (Test-Path -LiteralPath $resourceTarget -PathType Leaf)) {
                    throw "Reviewed resource target is not a file: $resourceTarget"
                }
                if ($null -eq $resourceManifestEntry) {
                    if ($resourceTargetExists) {
                        throw "Unmanifested resource target already exists: $resourceKey"
                    }
                    $oldResourceHash = "absent"
                    $skipResourceWrite = $false
                } else {
                    if (-not $resourceTargetExists) {
                        throw "Manifested resource target is missing: $resourceKey"
                    }
                    $installedResourceHash = (Get-FileHash -Path $resourceTarget -Algorithm SHA256).Hash.ToLowerInvariant()
                    if ($installedResourceHash -ne ([string]$resourceManifestEntry.Value).ToLowerInvariant()) {
                        throw "Reviewed resource target '$resourceKey' no longer matches its trusted manifest hash"
                    }
                    if ($installedResourceHash -ne $resourceHash) {
                        throw "Refusing to replace manifest-matched resource '$resourceKey' whose bytes differ from the configured pin"
                    }
                    $oldResourceHash = [string]$resourceManifestEntry.Value
                    $skipResourceWrite = $true
                }

                $null = $syncPlan.Add([pscustomobject]@{
                    Skill = $skill
                    RepositoryName = $repo.name
                    Source = $pinnedResource.Path
                    Target = $resourceTarget
                    ManifestKey = $resourceKey
                    OldCommit = [string]$resource.pinned_commit
                    NewCommit = [string]$resource.pinned_commit
                    OldHash = $oldResourceHash
                    NewHash = $resourceHash
                    Resource = $true
                    SkipWrite = $skipResourceWrite
                })
            }
        }

        $targetBackups = [System.Collections.Generic.List[object]]::new()
        foreach ($item in $syncPlan) {
            if ($item.Resource -and $item.SkipWrite) { continue }
            $targetExists = Test-Path -LiteralPath $item.Target
            if ($targetExists -and -not (Test-Path -LiteralPath $item.Target -PathType Leaf)) {
                throw "Reviewed target is not a file: $($item.Target)"
            }
            $targetBackups.Add([pscustomobject]@{
                Path = $item.Target
                Exists = $targetExists
                Bytes = if ($targetExists) { [IO.File]::ReadAllBytes($item.Target) } else { $null }
            })
        }
        $manifestBackup = [IO.File]::ReadAllBytes($manifestPath)
        $configBackup = if ($configChanged) { [IO.File]::ReadAllBytes($configPath) } else { $null }

        New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
        foreach ($line in $script:logBuffer) {
            Add-Content -Path $logFile -Value $line -Encoding UTF8
        }
        $script:logBuffer.Clear()
        $script:logReady = $true

        Write-Log "Reviewed skill update rationale: $($ReviewRationale.Trim())"
        try {
            if ($configChanged) {
                $configJson = ConvertTo-Json -InputObject $rawConfig -Depth 100
                [IO.File]::WriteAllText(
                    $configPath,
                    $configJson + [Environment]::NewLine,
                    [Text.UTF8Encoding]::new($false)
                )
            }
            foreach ($item in $syncPlan) {
                if ($item.Resource -and $item.SkipWrite) {
                    Write-Log "Preserved already-installed pinned resource: $($item.ManifestKey)"
                    continue
                }
                New-Item -ItemType Directory -Force -Path (Split-Path $item.Target -Parent) | Out-Null
                if ($item.Resource) {
                    [IO.File]::Copy($item.Source, $item.Target, $false)
                } else {
                    Copy-Item $item.Source $item.Target -Force
                }
                if ($item.Resource) {
                    Write-Log "Reviewed pinned resource: $($item.Skill) / $($item.ManifestKey); commit $($item.OldCommit); hash $($item.OldHash) -> $($item.NewHash)"
                } else {
                    Write-Log "Reviewed update: $($item.Skill); commit $($item.OldCommit) -> $($item.NewCommit); hash $($item.OldHash) -> $($item.NewHash)"
                }
            }

            $manifestArgs = @("--update-files") + @($syncPlan | ForEach-Object { $_.Target }) + @("--manifest", $manifestPath, "--repo-root", $repoRoot)
            $manifestOutput = & $pythonExecutable $manifestUpdater @manifestArgs 2>&1
            $manifestExitCode = $LASTEXITCODE
            $manifestOutput | ForEach-Object { Write-Log $_ }
            if ($manifestExitCode -ne 0) {
                throw "Reviewed skill manifest update failed"
            }

            $prewriteGate = Join-Path (Split-Path $scriptDir -Parent) "src\utils\prewrite_security_gate.py"
            $gateOutput = & $pythonExecutable $prewriteGate --repo-root $repoRoot 2>&1
            $gateExitCode = $LASTEXITCODE
            $gateOutput | ForEach-Object { Write-Log $_ }
            if ($gateExitCode -ne 0) {
                throw "Reviewed skill update did not pass the prewrite security gate"
            }
        } catch {
            $syncFailure = $_
            $rollbackFailures = [System.Collections.Generic.List[string]]::new()
            for ($index = $targetBackups.Count - 1; $index -ge 0; $index--) {
                $backup = $targetBackups[$index]
                try {
                    if ($backup.Exists) {
                        [IO.File]::WriteAllBytes($backup.Path, $backup.Bytes)
                    } elseif (Test-Path -LiteralPath $backup.Path -PathType Leaf) {
                        [IO.File]::Delete($backup.Path)
                    }
                } catch {
                    $rollbackFailures.Add("$($backup.Path): $($_.Exception.Message)")
                }
            }
            try {
                [IO.File]::WriteAllBytes($manifestPath, $manifestBackup)
            } catch {
                $rollbackFailures.Add("${manifestPath}: $($_.Exception.Message)")
            }
            if ($configChanged) {
                try {
                    [IO.File]::WriteAllBytes($configPath, $configBackup)
                } catch {
                    $rollbackFailures.Add("${configPath}: $($_.Exception.Message)")
                }
            }
            if ($rollbackFailures.Count -gt 0) {
                throw "Reviewed sync failed and rollback was incomplete: $($rollbackFailures -join '; '). Original failure: $($syncFailure.Exception.Message)"
            }
            throw $syncFailure
        }
    } finally {
        foreach ($pinnedSource in $pinnedSources) {
            Remove-PinnedSource $pinnedSource.RepositoryPath $pinnedSource.Worktree
        }
        Exit-WorkspaceSkillSyncLock $syncMutex
    }
}

if ($ApproveReviewedUpdates) {
    Invoke-ReviewedSkillSync
    exit 0
}

$syncMutex = Enter-WorkspaceSkillSyncLock $repoRoot
try {
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
$manifest = Get-Content -Raw -Path $manifestPath | ConvertFrom-Json
$manifestFiles = $manifest.files
$pathSeparators = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$rootPrefix = [IO.Path]::GetFullPath($repoRoot).TrimEnd($pathSeparators) + [IO.Path]::DirectorySeparatorChar
$pathComparison = if ([IO.Path]::DirectorySeparatorChar -eq '\') {
    [StringComparison]::OrdinalIgnoreCase
} else {
    [StringComparison]::Ordinal
}

$syncPlan = [System.Collections.Generic.List[object]]::new()
$pinnedSources = [System.Collections.Generic.List[object]]::new()

try {
    $config = Get-SyncPreflight
    Assert-SyncWorkspaceIdentity $config
    $destination = $config.destination
    Assert-NoReparseComponents $configPath $repoRoot "Skill sync config"
    Assert-NoReparseComponents $manifestPath $repoRoot "Agent manifest"
    $manifest = Get-Content -Raw -Path $manifestPath | ConvertFrom-Json
    $manifestFiles = $manifest.files
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
        foreach ($resource in $repo.resources) {
            $pinnedResource = Resolve-PinnedSource `
                $repoPath `
                $resource.pinned_commit `
                $resource.source_relative_path `
                $pinnedSources
            $resourceHash = (Get-FileHash -Path $pinnedResource.Path -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($resourceHash -ne ([string]$resource.sha256).ToLowerInvariant()) {
                throw "Pinned resource hash mismatch for $($repo.name): $($resource.source_relative_path)"
            }
            $null = $syncPlan.Add([pscustomobject]@{
                RepositoryName = $repo.name
                Provenance = $repo.provenance
                Skill = $resource.skill
                Source = $pinnedResource.Path
                Target = $resource.target
                Resource = $true
                PinnedHash = $resourceHash
                ManifestKey = ([IO.Path]::GetFullPath($resource.target).Substring($rootPrefix.Length).Replace('\', '/'))
                SkipInstall = $false
            })
        }
    }

    if ($ApproveProtectedSync) {
        foreach ($resourceMapping in @($syncPlan | Where-Object { $_.Resource })) {
            $resourceTargetExists = Test-Path -LiteralPath $resourceMapping.Target
            $resourceManifestEntry = $manifestFiles.PSObject.Properties[$resourceMapping.ManifestKey]
            if ($resourceTargetExists -and -not (Test-Path -LiteralPath $resourceMapping.Target -PathType Leaf)) {
                throw "Pinned resource target is not a file: $($resourceMapping.Target)"
            }
            if ($null -eq $resourceManifestEntry) {
                if ($resourceTargetExists) {
                    throw "Unmanifested pinned resource target already exists: $($resourceMapping.ManifestKey)"
                }
            } else {
                if (-not $resourceTargetExists) {
                    throw "Manifested pinned resource target is missing: $($resourceMapping.ManifestKey)"
                }
                $installedResourceHash = (Get-FileHash -Path $resourceMapping.Target -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($installedResourceHash -ne ([string]$resourceManifestEntry.Value).ToLowerInvariant()) {
                    throw "Pinned resource target no longer matches its trusted manifest hash: $($resourceMapping.ManifestKey)"
                }
                if ($installedResourceHash -ne $resourceMapping.PinnedHash) {
                    throw "Refusing to replace manifest-matched resource whose bytes differ from the configured pin: $($resourceMapping.ManifestKey)"
                }
                $resourceMapping.SkipInstall = $true
            }
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

        if ($mapping.Resource -and $mapping.SkipInstall) {
            Write-Log "Preserved already-installed pinned resource: $($mapping.ManifestKey)"
            continue
        }

        if ($mapping.Resource -and -not $ApproveProtectedSync) {
            Write-Log "DRY-RUN: pinned resource $destFile — use -ApproveProtectedSync to install"
            continue
        }

        if ($mapping.Resource) {
            $resourceTargetExists = Test-Path -LiteralPath $destFile
            $resourceManifestEntry = $manifestFiles.PSObject.Properties[$mapping.ManifestKey]
            if ($resourceTargetExists -and -not (Test-Path -LiteralPath $destFile -PathType Leaf)) {
                throw "Pinned resource target is not a file: $destFile"
            }
            if ($null -eq $resourceManifestEntry) {
                if ($resourceTargetExists) {
                    throw "Unmanifested pinned resource target already exists: $($mapping.ManifestKey)"
                }
            } else {
                if (-not $resourceTargetExists) {
                    throw "Manifested pinned resource target is missing: $($mapping.ManifestKey)"
                }
                $installedResourceHash = (Get-FileHash -Path $destFile -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($installedResourceHash -ne ([string]$resourceManifestEntry.Value).ToLowerInvariant()) {
                    throw "Pinned resource target no longer matches its trusted manifest hash: $($mapping.ManifestKey)"
                }
                if ($installedResourceHash -ne $mapping.PinnedHash) {
                    throw "Refusing to replace manifest-matched resource whose bytes differ from the configured pin: $($mapping.ManifestKey)"
                }
                Write-Log "Preserved already-installed pinned resource: $($mapping.ManifestKey)"
                continue
            }
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
        if ($mapping.Resource) {
            [IO.File]::Copy($src, $destFile, $false)
        } else {
            Copy-Item $src $destFile -Force
        }
        if ($mapping.Resource) {
            Write-Log "Copied pinned resource for $skill from $($mapping.RepositoryName)"
        } else {
            Write-Log "Copied $skill from $($mapping.RepositoryName)"
        }
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
} finally {
    Exit-WorkspaceSkillSyncLock $syncMutex
}
