# Thin compatibility shim. The resident Python supervisor owns all behavior.
param([switch]$NoOpen)

$supervisor = Join-Path $PSScriptRoot "portal_supervisor.py"
$arguments = @($supervisor)
if ($NoOpen) { $arguments += "--no-open" }
& "C:\G\python.exe" @arguments
exit $LASTEXITCODE