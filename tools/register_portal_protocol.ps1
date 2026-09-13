# Registers the portal:// custom URL protocol as a thin supervisor shim.
# Run once. Works without admin (registers in HKCU).

$supervisorPath = "f:\⊕Workspace\tools\portal_supervisor.py"
$stagingDir = Join-Path $env:LOCALAPPDATA "WorkspacePortal"
$stagedPs1 = Join-Path $stagingDir "portal_protocol_launch.ps1"
$stagedVbs = Join-Path $stagingDir "portal_protocol_launch.vbs"
$desktopPs1 = Join-Path $stagingDir "open_portal.ps1"
$desktopVbs = Join-Path $stagingDir "open_portal.vbs"
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
foreach ($path in @($stagedPs1, $stagedVbs, $desktopPs1, $desktopVbs)) {
	if (Test-Path -LiteralPath $path) {
		Copy-Item -LiteralPath $path -Destination "$path.backup-$timestamp" -Force
	}
}

function Write-PortalShim {
	param([string]$PowerShellPath, [string]$VbsPath, [switch]$NoOpen)
	$noOpenArg = if ($NoOpen) { " --no-open" } else { "" }
	[System.IO.File]::WriteAllText(
		$PowerShellPath,
		"& `"C:\G\python.exe`" `"$supervisorPath`"$noOpenArg`r`nexit `$LASTEXITCODE`r`n",
		[System.Text.UTF8Encoding]::new($true)
	)
	$vbsText = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""$PowerShellPath""", 0, False
"@
	[System.IO.File]::WriteAllText($VbsPath, $vbsText, [System.Text.Encoding]::ASCII)
}

# Keep launch indirection in ASCII-safe paths for shell/protocol stability.
Write-PortalShim -PowerShellPath $stagedPs1 -VbsPath $stagedVbs -NoOpen
Write-PortalShim -PowerShellPath $desktopPs1 -VbsPath $desktopVbs

$cmd = "wscript.exe `"$stagedVbs`""
$regBase = "HKCU:\Software\Classes\portal"

New-Item -Path $regBase -Force | Out-Null
Set-ItemProperty -Path $regBase -Name "(Default)" -Value "URL:Portal Launch Protocol"
Set-ItemProperty -Path $regBase -Name "URL Protocol" -Value ""
New-Item -Path "$regBase\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "$regBase\DefaultIcon" -Name "(Default)" -Value "wscript.exe,0"
New-Item -Path "$regBase\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$regBase\shell\open\command" -Name "(Default)" -Value $cmd

Write-Host "portal:// protocol registered" -ForegroundColor Green
Write-Host "Handler: $cmd"
Write-Host "Desktop launcher staged: $desktopVbs"
Write-Host "Rollback backups use suffix: .backup-$timestamp"

# Operator proof plan (run only after reviewing this reversible staging script):
# 1. Run this script to stage backups plus the thin launcher files.
# 2. Invoke C:\Users\tyler\AppData\Local\WorkspacePortal\open_portal.vbs.
# 3. Verify http://127.0.0.1:8080/api/state returns no-store, one generation,
#    and service PID/command/start/readiness/attempt/error state.
# 4. Invoke open_portal.vbs again and verify the generation and service PIDs do
#    not change while the existing portal is focused.
# 5. Use Restart All and verify a new generation and configured-port reclamation.
# 6. Roll back by copying each .backup-<timestamp> file over its staged original.