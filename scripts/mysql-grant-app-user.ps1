<#
  Create/refresh the least-privilege runtime account `tycoons_app`.

    * SELECT, INSERT, UPDATE, DELETE on application tables - no DDL, no DROP, no GRANT
    * audit_logs:      SELECT, INSERT only (append-only even without the triggers)
    * alembic_version: SELECT only (readiness check)

  Grants are per table, so re-run this after every migration that adds a table.
  The existing `tycoons` account remains the schema owner used only by Alembic
  (MIGRATION_DATABASE_URL). backend\.env is updated so that:
      DATABASE_URL           -> tycoons_app (the API)
      MIGRATION_DATABASE_URL -> tycoons     (alembic)
#>
param([string]$Database = 'tycoons', [string]$User = 'tycoons_app')
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$bin = Join-Path $root '.tools\mysql\bin'
$envFile = Join-Path $root 'backend\.env'
$env:MYSQL_PWD = (Get-Content (Join-Path $root '.tools\mysql-root-password.txt') -Raw).Trim()
function Invoke-Sql([string]$sql) { $sql | & "$bin\mysql.exe" --host=127.0.0.1 --port=3308 -uroot -N; if ($LASTEXITCODE -ne 0) { throw "SQL failed" } }

$lines = Get-Content $envFile
$current = ($lines | Where-Object { $_ -match "^DATABASE_URL=mysql\+pymysql://$User`:" }) -replace "^DATABASE_URL=mysql\+pymysql://$User`:([^@]+)@.*$", '$1'
# One row per host ('127.0.0.1' and 'localhost'), so any count above zero means it exists
$exists = [int](Invoke-Sql "SELECT COUNT(*) FROM mysql.user WHERE user='$User';") -gt 0
if ($exists -and $current) { $pw = $current } else {
  $chars = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'.ToCharArray()  # pragma: allowlist secret
  $b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  $pw = -join ($b | ForEach-Object { $chars[$_ % $chars.Length] })
  if ($exists) { Invoke-Sql "ALTER USER '$User'@'127.0.0.1' IDENTIFIED BY '$pw'; ALTER USER '$User'@'localhost' IDENTIFIED BY '$pw';" }
  else { Invoke-Sql "CREATE USER '$User'@'127.0.0.1' IDENTIFIED BY '$pw'; CREATE USER '$User'@'localhost' IDENTIFIED BY '$pw';" }
}

$tables = (Invoke-Sql "SELECT table_name FROM information_schema.tables WHERE table_schema='$Database' AND table_type='BASE TABLE';") -split "`r?`n" | Where-Object { $_ }
$sql = @()
foreach ($h in "'$User'@'127.0.0.1'", "'$User'@'localhost'") {
  $sql += "REVOKE ALL PRIVILEGES, GRANT OPTION FROM $h;"
  foreach ($t in $tables) {
    $priv = switch ($t) { 'audit_logs' { 'SELECT, INSERT' } 'alembic_version' { 'SELECT' } default { 'SELECT, INSERT, UPDATE, DELETE' } }
    $sql += "GRANT $priv ON ``$Database``.``$t`` TO $h;"
  }
}
Invoke-Sql ($sql -join "`n")

# Point the API at the restricted account; keep the owner for migrations.
$owner = ($lines | Where-Object { $_ -match '^DATABASE_URL=mysql\+pymysql://tycoons:' }) -replace '^DATABASE_URL=', ''
$out = @($lines | Where-Object { $_ -notmatch '^(DATABASE_URL|MIGRATION_DATABASE_URL)=' })
$out += "DATABASE_URL=mysql+pymysql://$User`:$pw@127.0.0.1:3308/$Database`?charset=utf8mb4"
if ($owner) { $out += "MIGRATION_DATABASE_URL=$owner" }
elseif ($m = $lines | Where-Object { $_ -match '^MIGRATION_DATABASE_URL=' }) { $out += $m }
[IO.File]::WriteAllLines($envFile, $out, (New-Object Text.UTF8Encoding $false))
$env:MYSQL_PWD = $null
Write-Host "Granted $User on $($tables.Count) tables of $Database (audit_logs: SELECT, INSERT)."
