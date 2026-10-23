# Start the portable MySQL server (127.0.0.1:3308) in the background.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$bin = Join-Path $root '.tools\mysql\bin'
$ini = Join-Path $root 'scripts\mysql\my.ini'
$base = Join-Path $root '.tools\mysql'
$data = Join-Path $root '.tools\mysql-data'

function Test-Port { $c = New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', 3308); $c.Close(); $true } catch { $false } }

if (Test-Port) { Write-Host 'MySQL is already running on 127.0.0.1:3308.'; exit 0 }
if (-not (Test-Path $data)) { throw "No data directory at $data. Run scripts\mysql-init.ps1 first." }

$mysqldArgs = @("--defaults-file=`"$ini`"", "--basedir=`"$base`"", "--datadir=`"$data`"", "--log-error=`"$data\mysqld.err`"")
$p = Start-Process -FilePath "$bin\mysqld.exe" -ArgumentList $mysqldArgs -WindowStyle Hidden -PassThru
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Milliseconds 500
  if (Test-Port) { Write-Host "MySQL started on 127.0.0.1:3308 (pid $($p.Id))."; exit 0 }
}
throw "MySQL did not start; see $data\mysqld.err"
