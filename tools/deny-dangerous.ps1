<#
.SYNOPSIS
    Global agent command guard — blocks dangerous shell commands before agents run them.
    PowerShell port of https://github.com/davidondrej/skills/blob/main/hooks/deny-dangerous.sh

.DESCRIPTION
    Reads CurrentUser DPAPI-protected .NET regex rules, one per line. Rules are decrypted
    in memory only. DPAPI CurrentUser discourages casual inspection
    on this account and machine; it does not isolate same-user agents or prevent bypass.
    Returns $true (blocked) with a reason message, or $false (allowed) silently.
    Called from $PROFILE via Invoke-GuardCheck before running agent-suggested commands,
    or integrated as a pre-execution wrapper in agent workflows.

.PARAMETER Command
    The command string to check.

.PARAMETER PatternsFile
    Path to the protected rules file. Defaults to dangerous-patterns.dpapi beside this script.

.PARAMETER Maintenance
    Encrypt a supplied plaintext rules file instead of checking a command.

.PARAMETER PlaintextPatternsFile
    Caller-supplied plaintext rules file used only with -Maintenance. It is not removed.

.PARAMETER Overwrite
    Explicitly allow maintenance mode to replace an existing protected rules file.

.EXAMPLE
    .\deny-dangerous.ps1 -Maintenance -PlaintextPatternsFile .\my-rules.txt

.OUTPUTS
    [bool] $true = blocked, $false = allowed.
    On block, writes reason to $env:GUARD_BLOCK_REASON and prints to stderr.
#>
[CmdletBinding(DefaultParameterSetName = 'Runtime')]
param(
    [Parameter(Mandatory, ValueFromPipeline, ParameterSetName = 'Runtime')]
    [string]$Command,

    [string]$PatternsFile = "$PSScriptRoot\dangerous-patterns.dpapi",

    [Parameter(Mandatory, ParameterSetName = 'Maintenance')]
    [switch]$Maintenance,

    [Parameter(Mandatory, ParameterSetName = 'Maintenance')]
    [string]$PlaintextPatternsFile,

    [Parameter(ParameterSetName = 'Maintenance')]
    [switch]$Overwrite
)

function Test-DangerousCommand {
    param([string]$Cmd, [string[]]$Patterns)

    foreach ($pattern in $Patterns) {
        $line = $pattern.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) { continue }
        try {
            if ($Cmd -match $line) {
                $reason = "Command guard blocked a dangerous command. Do not retry or work around the guard; explain the block to the user instead."
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

if ($Maintenance) {
    if ((Test-Path -LiteralPath $PatternsFile) -and -not $Overwrite) {
        [Console]::Error.WriteLine('Protected rules file already exists; specify -Overwrite to replace it.')
        exit 1
    }
    if (-not (Test-Path -LiteralPath $PlaintextPatternsFile -PathType Leaf)) {
        [Console]::Error.WriteLine('Plaintext rules file was not found.')
        exit 1
    }

    try {
        $plaintextBytes = [System.IO.File]::ReadAllBytes($PlaintextPatternsFile)
        $protectedBytes = [System.Security.Cryptography.ProtectedData]::Protect(
            $plaintextBytes,
            $null,
            [System.Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        [System.IO.File]::WriteAllBytes($PatternsFile, $protectedBytes)
        exit 0
    } catch {
        [Console]::Error.WriteLine('Could not protect the supplied rules file.')
        exit 1
    }
}

try {
    if (-not (Test-Path -LiteralPath $PatternsFile -PathType Leaf)) {
        throw 'Protected rules file unavailable.'
    }
    $protectedBytes = [System.IO.File]::ReadAllBytes($PatternsFile)
    $plaintextBytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
        $protectedBytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    $plaintextRules = [System.Text.Encoding]::UTF8.GetString($plaintextBytes).TrimStart([char]0xFEFF)
    $patterns = $plaintextRules -split "`r?`n"
} catch {
    [Console]::Error.WriteLine('Command guard rules unavailable; allowing command.')
    exit 0
}

$blocked = Test-DangerousCommand -Cmd $Command -Patterns $patterns
if ($blocked) { exit 2 } else { exit 0 }
