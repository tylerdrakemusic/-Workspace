# Registers the portal:// custom URL protocol so portal.html can invoke launch_portal.ps1.
# Run once. Works without admin (registers in HKCU).

$scriptPath = "f:\⊕Workspace\tools\launch_portal.ps1"
$stagingDir = Join-Path $env:LOCALAPPDATA "WorkspacePortal"
$stagedPs1 = Join-Path $stagingDir "portal_protocol_launch.ps1"
$stagedVbs = Join-Path $stagingDir "portal_protocol_launch.vbs"
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

# Keep launch indirection in ASCII-safe path for shell/protocol stability.
[System.IO.File]::WriteAllText(
	$stagedPs1,
	"& `"$scriptPath`" -NoOpen`r`n",
	[System.Text.UTF8Encoding]::new($true)
)
$vbsText = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""$stagedPs1""", 0, False
"@
[System.IO.File]::WriteAllText($stagedVbs, $vbsText, [System.Text.Encoding]::ASCII)

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