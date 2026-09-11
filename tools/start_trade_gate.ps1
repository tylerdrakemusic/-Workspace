param(
	[int]$Port = 7475,
	[string]$ProjectRoot = "f:\ΣCapital"
)

$ErrorActionPreference = "Stop"
$sourceEntrypoint = Join-Path $ProjectRoot "src\utils\trade_gate.py"
if (-not (Test-Path -LiteralPath $sourceEntrypoint -PathType Leaf)) {
	throw "Trade Gate source entrypoint was not found: $sourceEntrypoint"
}
$normalizedSourceEntrypoint = [IO.Path]::GetFullPath($sourceEntrypoint).Replace('/', '\').TrimEnd('\').ToLowerInvariant()

function Get-TradeGateListeners {
	try {
		return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
	}
	catch {
		if ($_.Exception.Message -like '*No matching MSFT_NetTCPConnection objects found*') {
			return @()
		}
		throw "Unable to inspect Trade Gate port ${Port}: $($_.Exception.Message)"
	}
}

function Test-TradeGateProcessOwner {
	param([string]$CommandLine)

	foreach ($match in [regex]::Matches($CommandLine, '(?:"([^"]+)"|([^\s]+))')) {
		$candidate = if ($match.Groups[1].Success) { $match.Groups[1].Value } else { $match.Groups[2].Value }
		try {
			$normalizedCandidate = [IO.Path]::GetFullPath($candidate).Replace('/', '\').TrimEnd('\').ToLowerInvariant()
		}
		catch {
			continue
		}
		if ($normalizedCandidate -eq $normalizedSourceEntrypoint) {
			return $true
		}
	}
	return $false
}

# Only stop listeners that are demonstrably owned by this Trade Gate source.
$listeners = Get-TradeGateListeners
foreach ($listener in $listeners) {
	$owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
	$commandLine = [string]$owner.CommandLine
	if (-not (Test-TradeGateProcessOwner -CommandLine $commandLine)) {
		throw "Port $Port is occupied by a process outside the Trade Gate ownership contract (PID $($listener.OwningProcess))."
	}
	Stop-Process -Id $listener.OwningProcess -Force
	Write-Host "Stopped stale Trade Gate PID $($listener.OwningProcess) on port $Port."
}

$remaining = @()
for ($attempt = 0; $attempt -lt 5; $attempt++) {
	$remaining = Get-TradeGateListeners
	if (-not $remaining) {
		break
	}
	Start-Sleep -Milliseconds 200
}
if ($remaining) {
	throw "Port $Port is still occupied after stale Trade Gate cleanup."
}

$projectRoot = $ProjectRoot
$projectRoot = [IO.Path]::GetFullPath($projectRoot).TrimEnd('\')
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8        = "1"
$env:PYTHONIOENCODING  = "utf-8"
$env:PYTHONPATH        = Join-Path $projectRoot "src"
$env:TRADE_GATE_PORT = [string]$Port
$env:TRADE_GATE_PROCESS_OWNER = "trade-gate-launcher"
$env:TRADE_GATE_SOURCE_ENTRYPOINT = "src/utils/trade_gate.py"
& "C:\G\python.exe" $sourceEntrypoint
