# Start everything for local development: MySQL (3308), API (8000), web (5173).
$root = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'mysql-start.ps1')
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\frontend'; npm.cmd run dev -- --host 127.0.0.1"
Write-Host 'Site:  http://localhost:5173'
Write-Host 'Admin: http://localhost:5173/admin'
Write-Host 'API:   http://localhost:8000/api/docs'
