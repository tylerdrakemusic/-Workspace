<#
.SYNOPSIS
  Register / unregister the `frsignoff:` URL protocol in HKCU.

.DESCRIPTION
  When Tyler clicks a `frsignoff:FR-xxxx` link in the portal, Windows
  launches:

      pythonw.exe F:\⊕Workspace\tools\fr_signoff_handler.py "frsignoff:FR-xxxx"

  The handler calls fr_signoff.signoff(), regenerates dashboards,
  `git push --force-with-lease`, and pops a small tkinter toast.

.USAGE
  .\register_frsignoff_protocol.ps1             # install
  .\register_frsignoff_protocol.ps1 -Uninstall  # remove
  .\register_frsignoff_protocol.ps1 -Check      # show current registration

.NOTES
  Writes to HKCU only — no admin required. Uses pythonw.exe so the console
  window never flashes up.
#>

[CmdletBinding()]
param(
    [switch] $Uninstall,
    [switch] $Check,
    [string] $PythonW = 'C:\G\pythonw.exe',
    [string] $Handler = 'F:\⊕Workspace\tools\fr_signoff_handler.py'
)

$ErrorActionPreference = 'Stop'
$protoRoot   = 'HKCU:\Software\Classes\frsignoff'
$commandPath = "$protoRoot\shell\open\command"

function Show-Registration {
    if (-not (Test-Path $protoRoot)) {
        Write-Host "frsignoff: NOT registered." -ForegroundColor Yellow
        return
    }
    Write-Host "Registered: $protoRoot" -ForegroundColor Green
    Get-Item $protoRoot | Select-Object -ExpandProperty Property | ForEach-Object {
        $v = (Get-ItemProperty -Path $protoRoot -Name $_).$_
        Write-Host ("  {0,-20} {1}" -f $_, $v)
    }
    if (Test-Path $commandPath) {
        $cmd = (Get-ItemProperty -Path $commandPath -Name '(Default)').'(Default)'
        Write-Host "  command:             $cmd"
    }
}

if ($Check) {
    Show-Registration
    exit 0
}

if ($Uninstall) {
    if (Test-Path $protoRoot) {
        Remove-Item -Path $protoRoot -Recurse -Force
        Write-Host "Removed $protoRoot" -ForegroundColor Green
    } else {
        Write-Host "Nothing to remove." -ForegroundColor Yellow
    }
    exit 0
}

# Install
if (-not (Test-Path $PythonW)) {
    throw "pythonw.exe not found at $PythonW"
}
if (-not (Test-Path $Handler)) {
    throw "handler script not found at $Handler"
}

# Create key structure
New-Item -Path $protoRoot -Force | Out-Null
New-ItemProperty -Path $protoRoot -Name '(Default)'    -Value 'URL:frsignoff Protocol' -PropertyType String -Force | Out-Null
New-ItemProperty -Path $protoRoot -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null

New-Item -Path "$protoRoot\DefaultIcon" -Force | Out-Null
New-ItemProperty -Path "$protoRoot\DefaultIcon" -Name '(Default)' -Value "$PythonW,0" -PropertyType String -Force | Out-Null

New-Item -Path $commandPath -Force | Out-Null
# %1 is the full URL (frsignoff:FR-xxxx). Wrapped in quotes to tolerate ? and &.
$command = '"{0}" "{1}" "%1"' -f $PythonW, $Handler
New-ItemProperty -Path $commandPath -Name '(Default)' -Value $command -PropertyType String -Force | Out-Null

Write-Host "Installed frsignoff: protocol handler" -ForegroundColor Green
Show-Registration
Write-Host ""
Write-Host "Test from any browser or Run dialog:" -ForegroundColor Cyan
Write-Host "    frsignoff:FR-TEST-invalid   (should show a 'refused' toast)"
