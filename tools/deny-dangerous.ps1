<#
.SYNOPSIS
    Global agent command guard — blocks dangerous shell commands before agents run them.
    PowerShell port of https://github.com/davidondrej/skills/blob/main/hooks/deny-dangerous.sh

.DESCRIPTION
    Reads dangerous-patterns.txt (one .NET regex per line).
    Returns $true (blocked) with a reason message, or $false (allowed) silently.
    Called from $PROFILE via Invoke-GuardCheck before running agent-suggested commands,
    or integrated as a pre-execution wrapper in agent workflows.

.PARAMETER Command
    The command string to check.

.PARAMETER PatternsFile
    Path to the patterns file. Defaults to dangerous-patterns.txt in the same directory.

.OUTPUTS
    [bool] $true = blocked, $false = allowed.
    On block, writes reason to $env:GUARD_BLOCK_REASON and prints to stderr.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory, ValueFromPipeline)]
    [string]$Command,

    [string]$PatternsFile = "$PSScriptRoot\dangerous-patterns.txt"
)

function Test-DangerousCommand {
    param([string]$Cmd, [string]$Patterns)

    if (-not (Test-Path $Patterns)) { return $false }  # fail open if patterns missing

    Get-Content $Patterns | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) { return }
        try {
            if ($Cmd -match $line) {
                $reason = "Command guard blocked a dangerous command. Matched pattern: $line`nDo not retry or work around the guard; explain the block to the user instead."
                $env:GUARD_BLOCK_REASON = $reason
                [Console]::Error.WriteLine($reason)
                # signal block to caller via exit code when used as script
                return $true
            }
        } catch {
            # malformed regex — skip and fail open
        }
    }
    return $false
}

$blocked = Test-DangerousCommand -Cmd $Command -Patterns $PatternsFile
if ($blocked) { exit 2 } else { exit 0 }
