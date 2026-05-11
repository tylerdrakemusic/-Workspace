$env:PYTHONPATH = "f:\❤Music\src"

# Ensure only one radio process owns port 8100 so stale local-mode launches cannot override Icecast mode.
$staleRadio = Get-CimInstance Win32_Process | Where-Object {
	$_.CommandLine -like "*tjd_radio.py*" -and $_.CommandLine -like "*--port 8100*"
}
foreach ($proc in $staleRadio) {
	Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

$bridgeScript = "f:\❤Music\tools\icecast_wsl_bridge.py"
$bridgeProc = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*icecast_wsl_bridge.py*" }
if (-not $bridgeProc) {
	Start-Process -FilePath "C:\G\python.exe" -ArgumentList @($bridgeScript, "--port", "18000") -WindowStyle Hidden
}

& "C:\G\python.exe" "f:\❤Music\src\radio\tjd_radio.py" --backend icecast --port 8100 --icecast-stream-url "http://127.0.0.1:18000/stream" --icecast-status-url "http://127.0.0.1:18000/status-json.xsl"