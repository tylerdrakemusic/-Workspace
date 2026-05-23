$project = Get-ChildItem -Path "f:\" -Directory | Where-Object { $_.Name -like "*AI-Manifest" } | Select-Object -First 1
if (-not $project) {
Write-Error "Could not locate AI-Manifest project directory under f:\"
exit 1
}

$projectRoot = $project.FullName
$env:PYTHONUTF8 = "1"

# PYTHONPATH cannot carry the emoji path reliably (PowerShell 5.1 cp1252
# mojibake). Instead: cd to the project root and use relative paths +
# sys.path.insert('.') so that src.* and tools.* imports resolve from CWD.
Set-Location $projectRoot

# Prevent the brief server from auto-opening a separate browser tab.
$briefNoOpenCmd = "import sys,runpy,webbrowser;sys.path.insert(0,'.');webbrowser.open=lambda *a,**k:False;sys.argv=['tools/executive_audio_brief.py','--serve','--port','8200'];runpy.run_path('tools/executive_audio_brief.py',run_name='__main__')"
& "C:\G\python.exe" -c $briefNoOpenCmd
