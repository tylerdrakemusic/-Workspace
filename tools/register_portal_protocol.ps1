# Registers the portal:// custom URL protocol so portal.html can invoke launch_portal.ps1.
# Run once. Works without admin (registers in HKCU).

$scriptPath = "f:\⊕Workspace\tools\launch_portal.ps1"
$cmd = "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$scriptPath"" -NoOpen"
$regBase = "HKCU:\Software\Classes\portal"

New-Item -Path $regBase -Force | Out-Null
Set-ItemProperty -Path $regBase -Name "(Default)" -Value "URL:Portal Launch Protocol"
Set-ItemProperty -Path $regBase -Name "URL Protocol" -Value ""
New-Item -Path "$regBase\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "$regBase\DefaultIcon" -Name "(Default)" -Value "powershell.exe,0"
New-Item -Path "$regBase\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$regBase\shell\open\command" -Name "(Default)" -Value $cmd

Write-Host "portal:// protocol registered" -ForegroundColor Green
Write-Host "Handler: $cmd"