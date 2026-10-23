<#
  One-time setup of the portable MySQL server used for local development.

  - initialises .tools/mysql-data
  - sets a random root password (saved to .tools/mysql-root-password.txt)
  - creates databases `tycoons` and `tycoons_test` and user `tycoons`
  - writes DATABASE_URL / TEST_DATABASE_URL into backend/.env

  Requires .tools/mysql (the MySQL 8.4 Windows "ZIP Archive" build). Refuses
  to run if the data directory already exists.
#>
# 'Continue', not 'Stop': mysqld logs to stderr, which Windows PowerShell 5.1
# would otherwise turn into a terminating error. Exit codes are checked instead.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot

$bin = Join-Path $root '.tools\mysql\bin'
$base = Join-Path $root '.tools\mysql'
$data = Join-Path $root '.tools\mysql-data'
$ini = Join-Path $root 'scripts\mysql\my.ini'
if (-not (Test-Path "$bin\mysqld.exe")) { throw "MySQL not found at $bin. See README > Database." }
if (Test-Path $data) { throw "$data already exists - MySQL is already initialised." }

function New-Secret([int]$len = 24) {
  $chars = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'.ToCharArray()
  $bytes = New-Object byte[] $len
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

& "$bin\mysqld.exe" --defaults-file="$ini" --basedir="$base" --datadir="$data" --initialize-insecure --console
if ($LASTEXITCODE -ne 0) { throw "mysqld --initialize failed" }

& (Join-Path $PSScriptRoot 'mysql-start.ps1')

$rootPw = New-Secret
$appPw = New-Secret
$sql = @"
ALTER USER 'root'@'localhost' IDENTIFIED BY '$rootPw';
CREATE DATABASE tycoons CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE tycoons_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'tycoons'@'127.0.0.1' IDENTIFIED BY '$appPw';
CREATE USER 'tycoons'@'localhost' IDENTIFIED BY '$appPw';
GRANT ALL PRIVILEGES ON tycoons.* TO 'tycoons'@'127.0.0.1', 'tycoons'@'localhost';
GRANT ALL PRIVILEGES ON tycoons_test.* TO 'tycoons'@'127.0.0.1', 'tycoons'@'localhost';
FLUSH PRIVILEGES;
"@
$sql | & "$bin\mysql.exe" -h127.0.0.1 -P3308 -uroot
if ($LASTEXITCODE -ne 0) { throw "Creating databases failed" }

Set-Content -Path (Join-Path $root '.tools\mysql-root-password.txt') -Value $rootPw -Encoding ascii

$envFile = Join-Path $root 'backend\.env'
if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $root 'backend\.env.example') $envFile }
$lines = @(Get-Content $envFile | Where-Object { $_ -notmatch '^(DATABASE_URL|TEST_DATABASE_URL)=' })
$lines += "DATABASE_URL=mysql+pymysql://tycoons:$appPw@127.0.0.1:3308/tycoons?charset=utf8mb4"
$lines += "TEST_DATABASE_URL=mysql+pymysql://tycoons:$appPw@127.0.0.1:3308/tycoons_test?charset=utf8mb4"
[IO.File]::WriteAllLines($envFile, $lines, (New-Object Text.UTF8Encoding $false))

Write-Host "MySQL initialised on 127.0.0.1:3308."
Write-Host "Root password: .tools\mysql-root-password.txt ; app credentials: backend\.env"
