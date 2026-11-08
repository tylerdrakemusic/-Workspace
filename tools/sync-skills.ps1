#Requires -Version 5.1
# sync-skills.ps1 — git pull each skill repo and copy registered SKILL.md files
# into .github/skills/. Driven by skill-sync-config.json.

param(
    [switch]$ApproveProtectedSync,
    [switch]$ApproveReviewedUpdates,
    [switch]$InstallReviewedAdaptations,
    [string[]]$ReviewedSkills,
    [string]$ReviewRationale,
    [string]$RestorePinnedTarget,
    [string]$RestoreRationale,
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

function Restore-StagedWrite {
    param([object]$StagedWrite)

    $targetPath = [string]$StagedWrite.Target
    $backupPath = [string]$StagedWrite.Backup
    if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
        throw "Committed target disappeared before rollback: $targetPath"
    }

    $observedPath = Join-Path (Split-Path -Parent $targetPath) (".skill-sync-rollback-" + [Guid]::NewGuid().ToString("N") + ".tmp")
    [IO.File]::Move($targetPath, $observedPath)
    try {
        $observedHash = (Get-FileHash -LiteralPath $observedPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($observedHash -cne ([string]$StagedWrite.NewHash).ToLowerInvariant()) {
            [IO.File]::Move($observedPath, $targetPath)
            $observedPath = ""
            throw "Preserved target changed by another writer: $targetPath"
        }

        if ($StagedWrite.TargetExisted) {
            if (-not (Test-Path -LiteralPath $backupPath -PathType Leaf)) {
                [IO.File]::Move($observedPath, $targetPath)
                $observedPath = ""
                throw "Original backup disappeared before rollback: $backupPath"
            }
            [IO.File]::Move($backupPath, $targetPath)
        }

        Remove-Item -LiteralPath $observedPath -Force
        $observedPath = ""
    } catch {
        if ($observedPath -and (Test-Path -LiteralPath $observedPath -PathType Leaf)) {
            if ($StagedWrite.TargetExisted -and
                (Test-Path -LiteralPath $backupPath -PathType Leaf)) {
                $StagedWrite.PreserveBackup = $true
            }
            if (-not (Test-Path -LiteralPath $targetPath)) {
                try {
                    [IO.File]::Move($observedPath, $targetPath)
                    $observedPath = ""
                } catch {
                }
            }
            if ($observedPath) {
                throw "Rollback failed; preserved current file at $observedPath and original backup at ${backupPath}: $($_.Exception.Message)"
            }
        }
        throw
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

function Assert-NoReparsePointsInPath {
    param(
        [string]$RootPath,
        [string]$Path,
        [string]$Description
    )

    $directorySeparator = [IO.Path]::DirectorySeparatorChar
    $alternateSeparator = [IO.Path]::AltDirectorySeparatorChar
    $separatorChars = [char[]]@($directorySeparator, $alternateSeparator)
    $rootFullPath = [IO.Path]::GetFullPath($RootPath).TrimEnd($separatorChars)
    $targetFullPath = [IO.Path]::GetFullPath($Path)
    $pathComparison = if ($directorySeparator -eq '\') {
        [StringComparison]::OrdinalIgnoreCase
    } else {
        [StringComparison]::Ordinal
    }
    $rootPrefix = $rootFullPath + $directorySeparator
    if (
        $targetFullPath -ne $rootFullPath -and
        -not $targetFullPath.StartsWith($rootPrefix, $pathComparison)
    ) {
        throw "$Description is outside the configured workspace root"
    }

    $currentRootPath = $rootFullPath
    while ($currentRootPath) {
        $rootItem = Get-Item -LiteralPath $currentRootPath -Force
        if ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Configured workspace root or ancestor is a reparse point: $currentRootPath"
        }
        $parentRootPath = Split-Path -Parent $currentRootPath
        if (-not $parentRootPath -or $parentRootPath -eq $currentRootPath) {
            break
        }
        $currentRootPath = $parentRootPath
    }
    $relativePath = if ($targetFullPath -eq $rootFullPath) {
        ""
    } else {
        $targetFullPath.Substring($rootPrefix.Length)
    }
    $currentPath = $rootFullPath
    foreach ($component in ($relativePath -split '[\\/]')) {
        if (-not $component) { continue }
        $currentPath = Join-Path $currentPath $component
        if (Test-Path -LiteralPath $currentPath) {
            $item = Get-Item -LiteralPath $currentPath -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "$Description path contains a reparse point: $currentPath"
            }
        }
    }
}

function Invoke-PinnedTargetRestore {
    if ([string]::IsNullOrWhiteSpace($RestorePinnedTarget)) {
        throw "Pinned target restoration requires one named skill"
    }
    if ([string]::IsNullOrWhiteSpace($RestoreRationale)) {
        throw "Pinned target restoration requires a non-empty rationale"
    }
    if (
        $ApproveProtectedSync -or $ApproveReviewedUpdates -or
        $null -ne $ReviewedSkills -or -not [string]::IsNullOrWhiteSpace($ReviewRationale)
    ) {
        throw "Pinned target restoration cannot be combined with another sync mode"
    }
    if (
        $RestorePinnedTarget -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$' -or
        $RestorePinnedTarget.Contains("\") -or
        @($RestorePinnedTarget.Split('/')).Where({ $_ -in @("", ".", "..") }).Count -gt 0
    ) {
        throw "Pinned target restoration requires a configured skill name, not a path"
    }

    $canonicalConfigPath = Join-Path $configRoot "tools\skill-sync-config.json"
    $canonicalManifestPath = Join-Path $configRoot ".github\!!☾⛧security\agent-manifest.json"
    $canonicalDestination = Join-Path $configRoot ".github\skills"
    $canonicalScriptDir = Join-Path $configRoot "tools"
    if (
        [IO.Path]::GetFullPath($configPath) -ne [IO.Path]::GetFullPath($canonicalConfigPath) -or
        [IO.Path]::GetFullPath($manifestPath) -ne [IO.Path]::GetFullPath($canonicalManifestPath) -or
        [IO.Path]::GetFullPath($repoRoot) -ne [IO.Path]::GetFullPath($configRoot) -or
        [IO.Path]::GetFullPath($destination) -ne [IO.Path]::GetFullPath($canonicalDestination) -or
        [IO.Path]::GetFullPath($scriptDir) -ne [IO.Path]::GetFullPath($canonicalScriptDir)
    ) {
        throw "Pinned target restoration requires the canonical workspace paths"
    }

    Assert-NoReparsePointsInPath $configRoot $configPath "Sync config"
    Assert-NoReparsePointsInPath $configRoot $manifestPath "Agent manifest"

    $rawConfig = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($null -eq $manifest.files) {
        throw "Pinned target restoration requires an existing manifest files map"
    }

    $mappingMatches = [System.Collections.Generic.List[object]]::new()
    foreach ($candidateRepo in $config.repos) {
        if ($candidateRepo.provenance -cne "external-source") { continue }
        foreach ($candidateMapping in $candidateRepo.mappings) {
            if ($candidateMapping.skill -ceq $RestorePinnedTarget) {
                $null = $mappingMatches.Add([pscustomobject]@{
                    Repo = $candidateRepo
                    Mapping = $candidateMapping
                })
            }
        }
    }
    if ($mappingMatches.Count -ne 1) {
        throw "Pinned target '$RestorePinnedTarget' must name exactly one external-source mapping"
    }

    $repo = $mappingMatches[0].Repo
    $mapping = $mappingMatches[0].Mapping
    $rawRepos = @($rawConfig.repos | Where-Object { $_.name -ceq $repo.name })
    if ($rawRepos.Count -ne 1) {
        throw "Pinned source repository '$($repo.name)' is ambiguous in the sync config"
    }
    $rawRepo = $rawRepos[0]
    if (
        $rawRepo.provenance -cne "external-source" -or
        @($rawRepo.skills).Count -ne 1 -or
        $rawRepo.skills[0] -cne $RestorePinnedTarget -or
        @($repo.mappings).Count -ne 1
    ) {
        throw "Pinned target '$RestorePinnedTarget' must have one exact external mapping"
    }

    $hasCommit = $rawRepo.PSObject.Properties.Name -contains "pinned_commit"
    $hasSha = $rawRepo.PSObject.Properties.Name -contains "sha256"
    $pinnedCommit = [string]$rawRepo.pinned_commit
    $pinnedSha = [string]$rawRepo.sha256
    if (
        -not $hasCommit -or -not $hasSha -or
        $pinnedCommit -notmatch '^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$' -or
        $pinnedSha -notmatch '^[0-9a-fA-F]{64}$' -or
        [string]$repo.pinned_commit -cne $pinnedCommit -or
        ([string]$repo.sha256).ToLowerInvariant() -cne $pinnedSha.ToLowerInvariant()
    ) {
        throw "Pinned source '$($repo.name)' must have a complete, matching existing pin pair"
    }

    $sourceRelativePath = [string]$mapping.source_relative_path
    if (
        [IO.Path]::IsPathRooted($sourceRelativePath) -or
        $sourceRelativePath.Contains("\") -or
        @($sourceRelativePath.Split('/')).Where({ $_ -in @("", ".", "..") }).Count -gt 0
    ) {
        throw "Pinned source path must be a normalized repository-relative path"
    }

    $expectedTarget = Join-Path $canonicalDestination ($RestorePinnedTarget.Replace('/', '\') + "\SKILL.md")
    $targetPath = [IO.Path]::GetFullPath($mapping.target)
    if ($targetPath -ne [IO.Path]::GetFullPath($expectedTarget)) {
        throw "Pinned target mapping does not resolve to the canonical skill target"
    }
    if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
        throw "Pinned target '$RestorePinnedTarget' must already exist"
    }
    Assert-NoReparsePointsInPath $configRoot $targetPath "Pinned target"

    $manifestKey = $targetPath.Substring(
        [IO.Path]::GetFullPath($configRoot).TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1
    ).Replace('\', '/')
    $manifestEntries = @($manifest.files.PSObject.Properties | Where-Object { $_.Name -ceq $manifestKey })
    if ($manifestEntries.Count -ne 1) {
        throw "Pinned target '$manifestKey' must have exactly one existing manifest entry"
    }
    $manifestHash = [string]$manifestEntries[0].Value
    if (
        $manifestHash -notmatch '^[0-9a-fA-F]{64}$' -or
        $manifestHash.ToLowerInvariant() -cne $pinnedSha.ToLowerInvariant()
    ) {
        throw "Existing manifest hash does not match the configured pinned SHA-256 for '$manifestKey'"
    }
    $installedHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($installedHash -ceq $manifestHash.ToLowerInvariant()) {
        throw "Pinned target '$manifestKey' already matches its existing manifest hash"
    }

    $repositoryPath = [string]$repo.path
    $commitReference = "$pinnedCommit^{commit}"
    & git -C $repositoryPath cat-file -e $commitReference 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Pinned commit $pinnedCommit is unavailable in $repositoryPath"
    }
    $blobReference = "$pinnedCommit`:$sourceRelativePath"
    & git -C $repositoryPath cat-file -e $blobReference 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Pinned source $sourceRelativePath is unavailable at commit $pinnedCommit"
    }
    $treeOutput = @(& git -C $repositoryPath ls-tree -r $pinnedCommit -- $sourceRelativePath 2>&1)
    if ($LASTEXITCODE -ne 0 -or @($treeOutput).Count -ne 1 -or $treeOutput[0] -notmatch '^(100644|100755) blob [0-9a-f]{40,64}\t') {
        throw "Pinned source must be one regular Git blob at the configured path"
    }

    $blobHashScript = "import hashlib,subprocess,sys; result=subprocess.run(['git','-C',sys.argv[1],'cat-file','blob',sys.argv[2]+':'+sys.argv[3]],check=True,capture_output=True); print(hashlib.sha256(result.stdout).hexdigest())"
    $blobHashOutput = & $pythonExecutable -c $blobHashScript $repositoryPath $pinnedCommit $sourceRelativePath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to hash configured pinned Git blob: $($blobHashOutput -join ' ')"
    }
    $blobHash = ($blobHashOutput -join [Environment]::NewLine).Trim().ToLowerInvariant()
    if ($blobHash -cne $pinnedSha.ToLowerInvariant()) {
        throw "Configured SHA-256 does not match the existing pinned Git blob SHA-256"
    }

    $temporaryPath = Join-Path (Split-Path -Parent $targetPath) (".restore-" + [Guid]::NewGuid().ToString("N") + ".tmp")
    $backupPath = Join-Path (Split-Path -Parent $targetPath) (".restore-backup-" + [Guid]::NewGuid().ToString("N") + ".tmp")
    try {
        $blobArgs = @(
            "--write-pinned-git-blob",
            $repositoryPath,
            $pinnedCommit,
            $sourceRelativePath,
            "--output",
            $temporaryPath,
            "--root",
            $configRoot
        )
        $blobOutput = & $pythonExecutable $manifestUpdater @blobArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Pinned Git blob materialization failed: $($blobOutput -join ' ')"
        }
        $temporaryHash = (Get-FileHash -LiteralPath $temporaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($temporaryHash -cne $pinnedSha.ToLowerInvariant()) {
            throw "Materialized pinned Git blob does not match the configured SHA-256"
        }
        [IO.File]::Replace($temporaryPath, $targetPath, $backupPath)
        $restoredHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($restoredHash -cne $pinnedSha.ToLowerInvariant()) {
            [IO.File]::Replace($backupPath, $targetPath, $temporaryPath)
            throw "Restored pinned target failed post-replacement SHA-256 verification"
        }
    } finally {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
        if (Test-Path -LiteralPath $backupPath) {
            Remove-Item -LiteralPath $backupPath -Force
        }
    }

    Write-Host "Restored pinned skill '$RestorePinnedTarget' to $pinnedSha. Rationale: $($RestoreRationale.Trim())"
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

    $rawConfig = Get-Content -Raw -Path $configPath | ConvertFrom-Json
    $manifest = Get-Content -Raw -Path $manifestPath | ConvertFrom-Json
    if ($null -eq $manifest.files) {
        throw "Reviewed updates require an existing manifest files map"
    }

    $syncPlan = [System.Collections.Generic.List[object]]::new()
    $pinnedSources = [System.Collections.Generic.List[object]]::new()
    $stagedWrites = [System.Collections.Generic.List[object]]::new()
    $createdDirectories = [System.Collections.Generic.List[string]]::new()
    $hasReviewedSkillAdaptation = $false
    $configChanged = $false
    $syncSucceeded = $false
    $configWriteAttempted = $false
    $manifestWriteAttempted = $false
    $configWrittenHash = ""
    $manifestWrittenHash = ""
    $originalConfigBytes = [IO.File]::ReadAllBytes($configPath)
    $originalManifestBytes = [IO.File]::ReadAllBytes($manifestPath)
    $originalConfigHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $originalManifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $configBackupPath = ""
    $configClaimPath = ""
    $manifestBackupPath = ""
    $configBackupCandidate = ""
    $manifestBackupCandidate = ""
    $configStageCandidate = ""
    try {
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

            if ($mapping.reviewed_adaptation_source) {
                $hasReviewedSkillAdaptation = $true
                if (-not $InstallReviewedAdaptations) {
                    throw "Reviewed skill adaptation installation requires -InstallReviewedAdaptations and an explicit reviewed skill selection: $skill"
                }
                if ($hasCommit -or $hasSha) {
                    throw "Reviewed skill adaptations cannot override pinned sources: $skill"
                }
                $adaptationSource = [string]$mapping.reviewed_adaptation_source
                $adaptationHash = ([string]$mapping.reviewed_adaptation_sha256).ToLowerInvariant()
                if (-not $adaptationSource -or $adaptationHash -notmatch '^[0-9a-f]{64}$') {
                    throw "Reviewed skill adaptation requires a verified source and SHA-256 baseline: $skill"
                }
                Assert-NoReparsePointsInPath `
                    $configRoot `
                    $adaptationSource `
                    "Reviewed skill adaptation '$skill'"
                if (-not (Test-Path -LiteralPath $adaptationSource -PathType Leaf)) {
                    throw "Reviewed skill adaptation source is missing: $skill"
                }
                $actualAdaptationHash = (Get-FileHash -LiteralPath $adaptationSource -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actualAdaptationHash -cne $adaptationHash) {
                    throw "Reviewed skill adaptation source hash mismatch: $skill"
                }
                $source = $adaptationSource
                $newHash = $adaptationHash
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
                IsCompanion = $false
            })

            foreach ($companionRepo in $config.repos) {
                if ($companionRepo.provenance -cne "external-source") { continue }
                foreach ($companion in $companionRepo.companions) {
                    $consumerIndex = [Array]::IndexOf(
                        [string[]]@($companion.consumers),
                        [string]$skill
                    )
                    if ($consumerIndex -lt 0) { continue }

                    $companionSource = [IO.Path]::GetFullPath([string]$companion.source)
                    $targetRelative = [string]$companion.target_relative_paths[$consumerIndex]
                    $companionTarget = [IO.Path]::GetFullPath([string]$companion.targets[$consumerIndex])
                    $expectedTarget = [IO.Path]::GetFullPath(
                        (Join-Path $configRoot ($targetRelative.Replace('/', '\')))
                    )
                    $expectedPrefix = [IO.Path]::GetFullPath(
                        (Join-Path $destination ($skill + '\'))
                    )
                    $pathComparison = if ([IO.Path]::DirectorySeparatorChar -eq '\') {
                        [StringComparison]::OrdinalIgnoreCase
                    } else {
                        [StringComparison]::Ordinal
                    }
                    if (
                        $companionTarget -ne $expectedTarget -or
                        -not $companionTarget.StartsWith($expectedPrefix, $pathComparison)
                    ) {
                        throw "Reviewed companion target for '$skill' is outside its exact consumer mapping"
                    }

                    $sourcePolicy = [string]$companionRepo.source_policy
                    if (-not (Test-Path -LiteralPath $companionSource -PathType Leaf)) {
                        if ($sourcePolicy -eq "optional" -and $companion.required -eq $false) { continue }
                        throw "Reviewed required companion source is missing: $($companion.identity)"
                    }
                    Assert-NoReparsePointsInPath `
                        $companionRepo.path `
                        $companionSource `
                        "Reviewed companion source '$($companion.identity)'"
                    Assert-NoReparsePointsInPath `
                        $configRoot `
                        $companionTarget `
                        "Reviewed companion target '$targetRelative'"

                    $companionHash = (Get-FileHash -LiteralPath $companionSource -Algorithm SHA256).Hash.ToLowerInvariant()
                    $syncCompanionSource = $companionSource
                    $companionManifestEntry = $manifest.files.PSObject.Properties[$targetRelative]
                    $acceptedBaselines = @($companion.hash_contract.accepted_baselines)
                    $targetExists = Test-Path -LiteralPath $companionTarget -PathType Leaf
                    if ((Test-Path -LiteralPath $companionTarget) -and -not $targetExists) {
                        throw "Reviewed companion target is not a regular file: $targetRelative"
                    }
                    if ($targetExists) {
                        if ($null -eq $companionManifestEntry) {
                            throw "Reviewed companion target is unexpected without a manifest baseline: $targetRelative"
                        }
                        $installedHash = (Get-FileHash -LiteralPath $companionTarget -Algorithm SHA256).Hash.ToLowerInvariant()
                        $baselineHash = ([string]$companionManifestEntry.Value).ToLowerInvariant()
                        if ($installedHash -ne $baselineHash) {
                            throw "Reviewed companion target no longer matches its manifest baseline: $targetRelative"
                        }
                        $approvedSourceBaseline = (
                            $acceptedBaselines -contains "approved-source" -and
                            $baselineHash -eq $companionHash
                        )
                        $reviewedAdaptationHash = ([string]$companion.hash_contract.reviewed_adaptation_sha256).ToLowerInvariant()
                        $reviewedAdaptationBaseline = (
                            $acceptedBaselines -contains "reviewed-project-owned-adaptation" -and
                            $reviewedAdaptationHash -match '^[0-9a-f]{64}$' -and
                            $baselineHash -eq $reviewedAdaptationHash -and
                            $baselineHash -ne $companionHash
                        )
                        if (-not ($approvedSourceBaseline -or $reviewedAdaptationBaseline)) {
                            throw "Reviewed companion target does not match an allowed prior baseline: $targetRelative"
                        }
                        if ($reviewedAdaptationBaseline -and -not $approvedSourceBaseline) {
                            Write-Log "Preserving reviewed companion adaptation: $targetRelative"
                            continue
                        }
                    } elseif ($null -ne $companionManifestEntry) {
                        throw "Reviewed companion target is missing but remains in the manifest: $targetRelative"
                    } elseif ($acceptedBaselines -notcontains "approved-source") {
                        if (-not $InstallReviewedAdaptations) {
                            throw "Reviewed adaptation installation requires -InstallReviewedAdaptations and an explicit reviewed skill selection: $targetRelative"
                        }
                        $adaptationSource = [string]$companion.reviewed_adaptation_source
                        $adaptationHash = ([string]$companion.hash_contract.reviewed_adaptation_sha256).ToLowerInvariant()
                        if (-not $adaptationSource -or $adaptationHash -notmatch '^[0-9a-f]{64}$') {
                            throw "New reviewed companion target requires a verified reviewed-adaptation source: $targetRelative"
                        }
                        Assert-NoReparsePointsInPath `
                            $configRoot `
                            $adaptationSource `
                            "Reviewed adaptation source '$targetRelative'"
                        if (-not (Test-Path -LiteralPath $adaptationSource -PathType Leaf)) {
                            throw "Reviewed adaptation source is missing: $targetRelative"
                        }
                        $actualAdaptationHash = (Get-FileHash -LiteralPath $adaptationSource -Algorithm SHA256).Hash.ToLowerInvariant()
                        if ($actualAdaptationHash -cne $adaptationHash) {
                            throw "Reviewed adaptation source hash mismatch: $targetRelative"
                        }
                        $syncCompanionSource = $adaptationSource
                        $companionHash = $adaptationHash
                    }

                    $null = $syncPlan.Add([pscustomobject]@{
                        Skill = $skill
                        RepositoryName = $companionRepo.name
                        Source = $syncCompanionSource
                        Target = $companionTarget
                        ManifestKey = $targetRelative
                        OldCommit = ""
                        NewCommit = ""
                        OldHash = if ($null -ne $companionManifestEntry) { [string]$companionManifestEntry.Value } else { "" }
                        NewHash = $companionHash
                        IsCompanion = $true
                    })
                }
            }
        }

        if ($configChanged -and $hasReviewedSkillAdaptation) {
            throw "Reviewed adaptations and pinned source config updates require a separate reviewed sync"
        }

        $plannedTargets = @($syncPlan | ForEach-Object { $_.Target })
        if ($plannedTargets.Count -ne @($plannedTargets | Select-Object -Unique).Count) {
            throw "Reviewed sync plan contains duplicate target mappings"
        }

        foreach ($item in $syncPlan) {
            $targetParent = Split-Path -Parent $item.Target
            $missingDirectories = [System.Collections.Generic.List[string]]::new()
            $directoryCursor = $targetParent
            while (-not (Test-Path -LiteralPath $directoryCursor -PathType Container)) {
                $null = $missingDirectories.Add($directoryCursor)
                $nextDirectory = Split-Path -Parent $directoryCursor
                if (-not $nextDirectory -or $nextDirectory -eq $directoryCursor) {
                    throw "Reviewed target parent could not be created: $targetParent"
                }
                $directoryCursor = $nextDirectory
            }
            $missingDirectories.Reverse()
            foreach ($directory in $missingDirectories) {
                New-Item -ItemType Directory -Path $directory | Out-Null
                $null = $createdDirectories.Add($directory)
            }

            Assert-NoReparsePointsInPath $configRoot $item.Target "Reviewed target '$($item.ManifestKey)'"
            $stagePath = Join-Path $targetParent (".skill-sync-stage-" + [Guid]::NewGuid().ToString("N") + ".tmp")
            $backupPath = Join-Path $targetParent (".skill-sync-backup-" + [Guid]::NewGuid().ToString("N") + ".tmp")
            $targetExists = Test-Path -LiteralPath $item.Target -PathType Leaf
            $stagedWrite = [pscustomobject]@{
                Target = $item.Target
                Stage = $stagePath
                Backup = $backupPath
                TargetExisted = $targetExists
                OldHash = $item.OldHash
                NewHash = $item.NewHash
                Committed = $false
                PreserveBackup = $false
            }
            $null = $stagedWrites.Add($stagedWrite)
            Copy-Item -LiteralPath $item.Source -Destination $stagePath
            $stagedHash = (Get-FileHash -LiteralPath $stagePath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($stagedHash -cne ([string]$item.NewHash).ToLowerInvariant()) {
                throw "Staged reviewed source failed SHA-256 verification: $($item.ManifestKey)"
            }
        }

        New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
        foreach ($line in $script:logBuffer) {
            Add-Content -Path $logFile -Value $line -Encoding UTF8
        }
        $script:logBuffer.Clear()
        $script:logReady = $true

        Write-Log "Reviewed skill update rationale: $($ReviewRationale.Trim())"
        $manifestBackupCandidate = Join-Path (Split-Path -Parent $manifestPath) (".skill-sync-manifest-backup-" + [Guid]::NewGuid().ToString("N") + ".tmp")
        [IO.File]::WriteAllBytes($manifestBackupCandidate, $originalManifestBytes)
        $manifestBackupHash = (Get-FileHash -LiteralPath $manifestBackupCandidate -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($manifestBackupHash -cne $originalManifestHash) {
            throw "Manifest backup failed byte-for-byte verification"
        }
        $manifestBackupPath = $manifestBackupCandidate
        if ($configChanged) {
            $configBackupCandidate = Join-Path (Split-Path -Parent $configPath) (".skill-sync-config-backup-" + [Guid]::NewGuid().ToString("N") + ".tmp")
            [IO.File]::WriteAllBytes($configBackupCandidate, $originalConfigBytes)
            $configBackupHash = (Get-FileHash -LiteralPath $configBackupCandidate -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($configBackupHash -cne $originalConfigHash) {
                throw "Sync config backup failed byte-for-byte verification"
            }
            $configBackupPath = $configBackupCandidate
            $currentConfigHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($currentConfigHash -cne $originalConfigHash) {
                throw "Sync config changed after reviewed preflight"
            }
            $configJson = ConvertTo-Json -InputObject $rawConfig -Depth 100
            $configStageCandidate = Join-Path (Split-Path -Parent $configPath) (".skill-sync-config-stage-" + [Guid]::NewGuid().ToString("N") + ".tmp")
            [IO.File]::WriteAllText(
                $configStageCandidate,
                $configJson + [Environment]::NewLine,
                [Text.UTF8Encoding]::new($false)
            )
            $stagedConfigHash = (Get-FileHash -LiteralPath $configStageCandidate -Algorithm SHA256).Hash.ToLowerInvariant()
            if (-not $stagedConfigHash) {
                throw "Staged sync config failed SHA-256 verification"
            }
            $currentConfigHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($currentConfigHash -cne $originalConfigHash) {
                throw "Sync config changed after reviewed preflight"
            }
            $configClaimPath = Join-Path (Split-Path -Parent $configPath) (".skill-sync-config-claim-" + [Guid]::NewGuid().ToString("N") + ".tmp")
            try {
                [IO.File]::Move($configPath, $configClaimPath)
                $claimedConfigHash = (Get-FileHash -LiteralPath $configClaimPath -Algorithm SHA256).Hash.ToLowerInvariant()
            } catch {
                $claimError = $_.Exception.Message
                if ($configClaimPath -and (Test-Path -LiteralPath $configClaimPath -PathType Leaf)) {
                    if (Test-Path -LiteralPath $configPath) {
                        $configBackupPath = $configClaimPath
                        $configBackupCandidate = $configClaimPath
                        throw "Unable to validate claimed sync config; canonical path is occupied and original bytes are preserved at ${configClaimPath}: $claimError"
                    }
                    try {
                        [IO.File]::Move($configClaimPath, $configPath)
                        $configClaimPath = ""
                        $configBackupPath = ""
                    } catch {
                        $restoreError = $_.Exception.Message
                        $configBackupPath = $configClaimPath
                        $configBackupCandidate = $configClaimPath
                        throw "Unable to restore claimed sync config; original bytes are preserved at ${configClaimPath}: $restoreError"
                    }
                }
                throw "Unable to validate claimed sync config; original bytes were restored: $claimError"
            }
            if ($claimedConfigHash -cne $originalConfigHash) {
                if (Test-Path -LiteralPath $configPath) {
                    $configBackupPath = $configClaimPath
                    $configBackupCandidate = $configClaimPath
                    throw "Sync config changed after reviewed preflight; concurrent bytes remain at $configPath and the original config is preserved at $configClaimPath"
                }
                try {
                    [IO.File]::Move($configClaimPath, $configPath)
                    $configClaimPath = ""
                    $configBackupPath = ""
                } catch {
                    $restoreError = $_.Exception.Message
                    $configBackupPath = $configClaimPath
                    $configBackupCandidate = $configClaimPath
                    throw "Sync config hash mismatch; original config restore failed and bytes are preserved at ${configClaimPath}: $restoreError"
                }
                throw "Sync config hash mismatch; original config restored at $configPath"
            }
            try {
                [IO.File]::Move($configStageCandidate, $configPath)
            } catch {
                if (-not (Test-Path -LiteralPath $configPath)) {
                    try {
                        [IO.File]::Move($configClaimPath, $configPath)
                        $configClaimPath = ""
                        $configBackupPath = ""
                    } catch {
                        $restoreError = $_.Exception.Message
                        $configBackupPath = $configClaimPath
                        $configBackupCandidate = $configClaimPath
                        throw "Concurrent config writer blocked restoration; original config is preserved at ${configClaimPath}: $restoreError"
                    }
                    throw "Concurrent sync config writer appeared; original config restored at $configPath"
                } else {
                    $configBackupPath = $configClaimPath
                    $configBackupCandidate = $configClaimPath
                    throw "Concurrent sync config writer appeared; competing bytes remain at $configPath and the original config is preserved at $configClaimPath"
                }
            }
            $configStageCandidate = ""
            $configWrittenHash = $stagedConfigHash
            $configWriteAttempted = $true
            Remove-Item -LiteralPath $configClaimPath -Force
            $configClaimPath = ""
            $observedConfigHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($observedConfigHash -cne $stagedConfigHash) {
                throw "Sync config changed during reviewed write; concurrent edit preserved"
            }
        }
        for ($index = 0; $index -lt $syncPlan.Count; $index++) {
            $item = $syncPlan[$index]
            $stagedWrite = $stagedWrites[$index]
            Assert-NoReparsePointsInPath $configRoot $item.Target "Reviewed target '$($item.ManifestKey)'"
            if ($stagedWrite.TargetExisted) {
                if (-not (Test-Path -LiteralPath $item.Target -PathType Leaf)) {
                    throw "Reviewed target disappeared after preflight: $($item.ManifestKey)"
                }
                $currentHash = (Get-FileHash -LiteralPath $item.Target -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($currentHash -cne ([string]$item.OldHash).ToLowerInvariant()) {
                    throw "Reviewed target changed after preflight: $($item.ManifestKey)"
                }
                [IO.File]::Replace($stagedWrite.Stage, $item.Target, $stagedWrite.Backup)
            } else {
                if (Test-Path -LiteralPath $item.Target) {
                    throw "Reviewed target appeared after preflight: $($item.ManifestKey)"
                }
                [IO.File]::Move($stagedWrite.Stage, $item.Target)
            }
            $stagedWrite.Committed = $true
            if ($item.IsCompanion) {
                Write-Log "Reviewed companion update: $($item.ManifestKey); hash $($item.OldHash) -> $($item.NewHash)"
            } else {
                Write-Log "Reviewed update: $($item.Skill); commit $($item.OldCommit) -> $($item.NewCommit); hash $($item.OldHash) -> $($item.NewHash)"
            }
        }

        foreach ($item in $syncPlan) {
            Assert-NoReparsePointsInPath $configRoot $item.Target "Reviewed target '$($item.ManifestKey)'"
            if (-not (Test-Path -LiteralPath $item.Target -PathType Leaf)) {
                throw "Reviewed target disappeared before manifest update: $($item.ManifestKey)"
            }
            $finalTargetHash = (Get-FileHash -LiteralPath $item.Target -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($finalTargetHash -cne ([string]$item.NewHash).ToLowerInvariant()) {
                throw "Reviewed target changed before manifest update: $($item.ManifestKey)"
            }
        }

        $currentManifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($currentManifestHash -cne $originalManifestHash) {
            throw "Agent manifest changed after reviewed preflight"
        }
        $manifestArgs = @("--update-files") + @($syncPlan | ForEach-Object { $_.Target }) + @("--manifest", $manifestPath, "--repo-root", $repoRoot, "--expected-manifest-hash", $originalManifestHash)
        foreach ($item in $syncPlan) {
            $manifestArgs += @("--expected-file-hash", $item.Target, ([string]$item.NewHash).ToLowerInvariant())
        }
        $manifestWriteAttempted = $true
        $manifestOutput = & $pythonExecutable $manifestUpdater @manifestArgs 2>&1
        $manifestExitCode = $LASTEXITCODE
        $manifestOutput | ForEach-Object { Write-Log $_ }
        if ($manifestExitCode -ne 0) {
            throw "Reviewed skill manifest update failed"
        }
        $manifestHashLines = @(
            $manifestOutput | ForEach-Object {
                if ([string]$_ -match '^MANIFEST_SHA256=([0-9a-f]{64})$') {
                    $Matches[1]
                }
            } | Where-Object { $_ }
        )
        if ($manifestHashLines.Count -ne 1) {
            throw "Reviewed manifest updater did not return one transaction hash"
        }
        $manifestWrittenHash = ([string]$manifestHashLines[0]).ToLowerInvariant()

        $prewriteGate = Join-Path (Split-Path $scriptDir -Parent) "src\utils\prewrite_security_gate.py"
        $gateOutput = & $pythonExecutable $prewriteGate --repo-root $repoRoot --strict 2>&1
        $gateExitCode = $LASTEXITCODE
        $gateOutput | ForEach-Object { Write-Log $_ }
        if ($gateExitCode -ne 0) {
            throw "Reviewed skill update did not pass the prewrite security gate"
        }
        $syncSucceeded = $true
    } finally {
        $rollbackErrors = [System.Collections.Generic.List[string]]::new()
        if (-not $syncSucceeded) {
            for ($index = $stagedWrites.Count - 1; $index -ge 0; $index--) {
                $stagedWrite = $stagedWrites[$index]
                try {
                    if ($stagedWrite.Committed) {
                        Restore-StagedWrite $stagedWrite
                    }
                } catch {
                    if ($stagedWrite.TargetExisted -and
                        (Test-Path -LiteralPath $stagedWrite.Backup -PathType Leaf)) {
                        $stagedWrite.PreserveBackup = $true
                        $null = $rollbackErrors.Add(
                            "Rollback failed; original backup preserved at $($stagedWrite.Backup): $($_.Exception.Message)"
                        )
                    } else {
                        $null = $rollbackErrors.Add($_.Exception.Message)
                    }
                }
            }

            foreach ($backup in @(
                [pscustomobject]@{
                    Path = $manifestBackupPath
                    Target = $manifestPath
                    WriteAttempted = $manifestWriteAttempted
                    OriginalHash = $originalManifestHash
                    WrittenHash = $manifestWrittenHash
                },
                [pscustomobject]@{
                    Path = $configBackupPath
                    Target = $configPath
                    WriteAttempted = $configWriteAttempted
                    OriginalHash = $originalConfigHash
                    WrittenHash = $configWrittenHash
                }
            )) {
                if (-not $backup.WriteAttempted -or -not $backup.Path -or -not (Test-Path -LiteralPath $backup.Path -PathType Leaf)) { continue }
                try {
                    if (Test-Path -LiteralPath $backup.Target -PathType Leaf) {
                        $currentHash = (Get-FileHash -LiteralPath $backup.Target -Algorithm SHA256).Hash.ToLowerInvariant()
                        if ($backup.Target -ceq $manifestPath) {
                            $restoreArgs = @(
                                "--restore-manifest-backup", $backup.Path,
                                "--expected-original-hash", $backup.OriginalHash,
                                "--expected-current-hash", $backup.WrittenHash,
                                "--manifest", $backup.Target,
                                "--repo-root", $repoRoot
                            )
                            $restoreOutput = & $pythonExecutable $manifestUpdater @restoreArgs 2>&1
                            $restoreExitCode = $LASTEXITCODE
                            $restoreOutput | ForEach-Object { Write-Log $_ }
                            if ($restoreExitCode -ne 0) {
                                $null = $rollbackErrors.Add(
                                    "Locked manifest rollback failed; backup preserved at $($backup.Path)"
                                )
                            }
                            continue
                        }
                        if ($currentHash -ceq $backup.OriginalHash) { continue }
                        if ($backup.WrittenHash -and $currentHash -cne $backup.WrittenHash) {
                            $null = $rollbackErrors.Add(
                                "Preserved concurrently changed file and backup at $($backup.Path)"
                            )
                            continue
                        }
                        $discardPath = Join-Path (Split-Path -Parent $backup.Target) (".skill-sync-discard-" + [Guid]::NewGuid().ToString("N") + ".tmp")
                        [IO.File]::Replace($backup.Path, $backup.Target, $discardPath)
                        Remove-Item -LiteralPath $discardPath -Force -ErrorAction SilentlyContinue
                    } else {
                        if ($backup.Target -ceq $manifestPath) {
                            $null = $rollbackErrors.Add(
                                "Manifest was removed by another writer; preserved backup at $($backup.Path)"
                            )
                            continue
                        }
                        [IO.File]::Move($backup.Path, $backup.Target)
                    }
                } catch {
                    $null = $rollbackErrors.Add($_.Exception.Message)
                }
            }
        }

        foreach ($stagedWrite in $stagedWrites) {
            foreach ($temporaryPath in @($stagedWrite.Stage, $stagedWrite.Backup)) {
                if ($temporaryPath -eq $stagedWrite.Backup -and $stagedWrite.PreserveBackup) {
                    continue
                }
                if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
                    Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
                }
            }
        }
        if ($syncSucceeded) {
            foreach ($temporaryPath in @($manifestBackupPath, $configBackupPath, $manifestBackupCandidate, $configBackupCandidate, $configStageCandidate)) {
                if ($temporaryPath -and (Test-Path -LiteralPath $temporaryPath -PathType Leaf)) {
                    Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
                }
            }
        } else {
            foreach ($candidatePath in @($manifestBackupCandidate, $configBackupCandidate, $configStageCandidate)) {
                if (
                    $candidatePath -and
                    $candidatePath -ne $manifestBackupPath -and
                    $candidatePath -ne $configBackupPath -and
                    (Test-Path -LiteralPath $candidatePath -PathType Leaf)
                ) {
                    Remove-Item -LiteralPath $candidatePath -Force -ErrorAction SilentlyContinue
                }
            }
        }
        if (-not $syncSucceeded) {
            for ($index = $createdDirectories.Count - 1; $index -ge 0; $index--) {
                $directory = $createdDirectories[$index]
                if ((Test-Path -LiteralPath $directory -PathType Container) -and
                    @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction SilentlyContinue).Count -eq 0) {
                    Remove-Item -LiteralPath $directory -Force -ErrorAction SilentlyContinue
                }
            }
        }
        foreach ($pinnedSource in $pinnedSources) {
            Remove-PinnedSource $pinnedSource.RepositoryPath $pinnedSource.Worktree
        }
        if ($rollbackErrors.Count -gt 0) {
            throw "Reviewed sync rollback was incomplete: $($rollbackErrors -join '; ')"
        }
    }
}

if (
    $PSBoundParameters.ContainsKey("RestorePinnedTarget") -or
    $PSBoundParameters.ContainsKey("RestoreRationale")
) {
    Invoke-PinnedTargetRestore
    exit 0
}

if ($ApproveReviewedUpdates) {
    Invoke-ReviewedSkillSync
    exit 0
}

if ($InstallReviewedAdaptations) {
    throw "Reviewed adaptation installation requires -ApproveReviewedUpdates, -ReviewedSkills, and -ReviewRationale"
}
$reviewedAdaptationMappings = @(
    $config.repos | ForEach-Object { $_.mappings } |
        Where-Object { $_.reviewed_adaptation_source }
)
$unapprovedAdaptationWrites = @(
    $reviewedAdaptationMappings | Where-Object {
        $ApproveProtectedSync -or
        -not (Test-Path -LiteralPath $_.target -PathType Leaf)
    }
)
if ($unapprovedAdaptationWrites.Count -gt 0) {
    $adaptedNames = ($unapprovedAdaptationWrites | ForEach-Object { $_.skill }) -join ", "
    throw "Reviewed skill adaptations cannot be written through ordinary sync; use approved C7 reviewed sync for: $adaptedNames"
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
