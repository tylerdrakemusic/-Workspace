$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Start-Process -FilePath "C:\G\python.exe" `
    -ArgumentList @("f:\⊕Workspace\src\utils\fr_server.py", "--port", "7474") `
    -WindowStyle Hidden
