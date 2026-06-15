$heartSigil = [string][char]0x2764
$musicRoot = "f:\" + $heartSigil + "Music"
$env:PYTHONPATH = Join-Path $musicRoot "src"
$env:PYTHONUTF8 = "1"
$dbKey = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_KEY", "User")
if (-not $dbKey) {
    $dbKey = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_KEY", "Machine")
}
if (-not $dbKey) {
    Write-Host "WARNING: HEARTMUSIC_DB_KEY not found in User or Machine environment; Guitar Trainer may fail to open heartmusic.db" -ForegroundColor Yellow
}
$env:HEARTMUSIC_DB_KEY = $dbKey
$script = Join-Path $musicRoot "src\training\musician_training_ui.py"
& "C:\G\python.exe" $script --port 5055
