# Thin compatibility shim. The resident Python supervisor owns restart behavior.
$supervisor = Join-Path $PSScriptRoot "portal_supervisor.py"
& "C:\G\python.exe" $supervisor --restart-all --no-open
exit $LASTEXITCODE
