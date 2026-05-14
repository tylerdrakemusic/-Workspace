#!/usr/bin/env pwsh
# install-hooks.ps1 — Set core.hooksPath in all 5 workspace repos
# FR-20260513-hooks-setup
#
# Usage: pwsh f:\⊕Workspace\.github\hooks\install-hooks.ps1
#
# Sets git config core.hooksPath to f:/.github/hooks/scripts in each repo,
# pointing all repos at the shared canonical hook directory.

$ErrorActionPreference = "Stop"

$HOOKS_PATH = "f:/.github/hooks/scripts"

$repos = @(
    [PSCustomObject]@{ Name = "⊕Workspace";   Path = "f:\⊕Workspace" },
    [PSCustomObject]@{ Name = "∞Life";         Path = "f:\∞Life" },
    [PSCustomObject]@{ Name = "❤Music";        Path = "f:\❤Music" },
    [PSCustomObject]@{ Name = "⟨ψ⟩Quantum";   Path = "f:\⟨ψ⟩Quantum" },
    [PSCustomObject]@{ Name = "👁AI-Manifest"; Path = "f:\👁AI-Manifest" }
)

Write-Host ""
Write-Host "=== install-hooks.ps1 — FR-20260513-hooks-setup ===" -ForegroundColor Cyan
Write-Host "    Setting core.hooksPath = $HOOKS_PATH"
Write-Host "    in all 5 workspace repos"
Write-Host ""

$results = @()

foreach ($repo in $repos) {
    $status = "OK"
    $detail = ""
    try {
        if (-not (Test-Path $repo.Path)) {
            $status = "SKIP"
            $detail = "path not found"
        } else {
            git -C $repo.Path config core.hooksPath $HOOKS_PATH 2>&1 | Out-Null
            $verified = (git -C $repo.Path config core.hooksPath 2>&1).Trim()
            if ($verified -eq $HOOKS_PATH) {
                $detail = "set -> $HOOKS_PATH"
            } else {
                $status = "FAIL"
                $detail = "set failed (got: $verified)"
            }
        }
    } catch {
        $status = "FAIL"
        $detail = $_.Exception.Message
    }
    $results += [PSCustomObject]@{ Status = $status; Repo = $repo.Name; Detail = $detail }

    $icon = switch ($status) {
        "OK"   { "[OK]  " }
        "SKIP" { "[SKIP]" }
        "FAIL" { "[FAIL]" }
        default { "[???] " }
    }
    Write-Host "  $icon  $($repo.Name.PadRight(20)) $detail"
}

Write-Host ""

$failed = $results | Where-Object { $_.Status -eq "FAIL" }
if ($failed.Count -gt 0) {
    Write-Host "[WARN]  $($failed.Count) repo(s) failed. Check paths and git installation." -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK]  All repos configured. The unified pre-commit hook is now active." -ForegroundColor Green
Write-Host ""
Write-Host "    Note: pre-commit-worktree-guard.sh is preserved for reference but"
Write-Host "    superseded by the unified pre-commit entry point."
Write-Host ""
Write-Host "    To verify for a repo: git -C f:\<repo> config core.hooksPath"
Write-Host ""
