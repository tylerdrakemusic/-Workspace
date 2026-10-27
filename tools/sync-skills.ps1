#Requires -Version 5.1
# sync-skills.ps1 — git pull each skill repo and copy registered SKILL.md files
# into .github/skills/. Driven by skill-sync-config.json.

param(
    [switch]$ApproveProtectedSync,
    [switch]$ApproveReviewedUpdates,
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

    $rootItem = Get-Item -LiteralPath $rootFullPath -Force
    if ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Configured workspace root is a reparse point: $rootFullPath"
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
    $configChanged = $false
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
        }

        New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null
        foreach ($line in $script:logBuffer) {
            Add-Content -Path $logFile -Value $line -Encoding UTF8
        }
        $script:logBuffer.Clear()
        $script:logReady = $true

        Write-Log "Reviewed skill update rationale: $($ReviewRationale.Trim())"
        if ($configChanged) {
            $configJson = ConvertTo-Json -InputObject $rawConfig -Depth 100
            [IO.File]::WriteAllText(
                $configPath,
                $configJson + [Environment]::NewLine,
                [Text.UTF8Encoding]::new($false)
            )
        }
        foreach ($item in $syncPlan) {
            Copy-Item $item.Source $item.Target -Force
            Write-Log "Reviewed update: $($item.Skill); commit $($item.OldCommit) -> $($item.NewCommit); hash $($item.OldHash) -> $($item.NewHash)"
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
    } finally {
        foreach ($pinnedSource in $pinnedSources) {
            Remove-PinnedSource $pinnedSource.RepositoryPath $pinnedSource.Worktree
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
