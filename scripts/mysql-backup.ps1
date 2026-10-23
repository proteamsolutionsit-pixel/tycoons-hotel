<#
  Consistent logical backup of the application database (default `tycoons`).
  Writes backups\<db>-<UTC timestamp>.sql (git-ignored). Restore with:
      Get-Content backups\tycoons-....sql | .tools\mysql\bin\mysql.exe --host=127.0.0.1 --port=3308 -uroot -p tycoons
  --single-transaction gives a consistent InnoDB snapshot without locking writers.
#>
param([string]$Database = 'tycoons')
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$bin = Join-Path $root '.tools\mysql\bin'
$dir = Join-Path $root 'backups'
New-Item -ItemType Directory -Force $dir | Out-Null
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$out = Join-Path $dir "$Database-$stamp.sql"
$env:MYSQL_PWD = (Get-Content (Join-Path $root '.tools\mysql-root-password.txt') -Raw).Trim()
& "$bin\mysqldump.exe" --host=127.0.0.1 --port=3308 -uroot --single-transaction --routines --triggers --hex-blob `
  --set-gtid-purged=OFF --default-character-set=utf8mb4 --result-file="$out" $Database
$code = $LASTEXITCODE
$env:MYSQL_PWD = $null
if ($code -ne 0) { throw "mysqldump failed ($code)" }
Write-Host "Backup written: $out ($([math]::Round((Get-Item $out).Length / 1KB)) KB)"
