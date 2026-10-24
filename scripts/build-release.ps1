<#
  Build a deployable release for cPanel/Passenger hosting:
    .tools\release\tycoons-<stamp>.zip  containing
      app\  alembic\  alembic.ini  passenger_wsgi.py  requirements-server.txt
      frontend_dist\   (the built React site, served by FastAPI via FRONTEND_DIST)
  Never includes .env, tests, storage, virtualenvs or caches.
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$stage = Join-Path $root ".tools\release\stage-$stamp"
$zip = Join-Path $root ".tools\release\tycoons-$stamp.zip"
New-Item -ItemType Directory -Force $stage | Out-Null

Push-Location (Join-Path $root 'frontend')
npm.cmd run build | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'frontend build failed' }
Pop-Location

$be = Join-Path $root 'backend'
Copy-Item -Recurse (Join-Path $be 'app') (Join-Path $stage 'app')
Copy-Item -Recurse (Join-Path $be 'alembic') (Join-Path $stage 'alembic')
foreach ($f in 'alembic.ini', 'passenger_wsgi.py', 'migrate.py', 'requirements-server.txt') { Copy-Item (Join-Path $be $f) $stage }
Copy-Item -Recurse (Join-Path $root 'frontend\dist') (Join-Path $stage 'frontend_dist')
Get-ChildItem $stage -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Get-ChildItem $stage -Recurse -File -Include '*.pyc', '.env', '*.prebak' | Remove-Item -Force

# Forward-slash entry names: Windows' Compress-Archive writes backslashes, which unzip on Linux keeps literally.
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$fs = [IO.File]::Open($zip, 'Create')
$archive = New-Object IO.Compression.ZipArchive($fs, [IO.Compression.ZipArchiveMode]::Create)
Get-ChildItem $stage -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($stage.Length + 1).Replace('\', '/')
  [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $rel, 'Optimal') | Out-Null
}
$archive.Dispose(); $fs.Dispose()
Remove-Item -Recurse -Force $stage
Write-Host "Release: $zip ($([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB)"
$zip
