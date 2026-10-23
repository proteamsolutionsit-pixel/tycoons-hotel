# Stop the portable MySQL server cleanly.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$bin = Join-Path $root '.tools\mysql\bin'
$env:MYSQL_PWD = (Get-Content (Join-Path $root '.tools\mysql-root-password.txt') -Raw).Trim()
& "$bin\mysqladmin.exe" --host=127.0.0.1 --port=3308 -uroot shutdown
$env:MYSQL_PWD = $null
if ($LASTEXITCODE -eq 0) { Write-Host 'MySQL stopped.' }
