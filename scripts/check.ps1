<#
  Run every quality and security gate locally (same as CI):
    lint (ruff incl. bandit rules), types (mypy), backend tests (pytest, real MySQL),
    dependency audit (pip-audit, npm audit), secret scan (detect-secrets),
    frontend tests (vitest) and production build.
  Exit code is non-zero if any gate fails.
#>
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root 'backend\.venv\Scripts'
$results = [ordered]@{}
function Step([string]$name, [scriptblock]$cmd) {
  Write-Host "`n=== $name ===" -ForegroundColor Cyan
  & $cmd
  $results[$name] = ($LASTEXITCODE -eq 0)
}

Push-Location (Join-Path $root 'backend')
Step 'ruff (lint + security rules)' { & "$py\ruff.exe" check app tests }
Step 'mypy (types)' { & "$py\mypy.exe" }
Step 'pytest (backend)' { & "$py\python.exe" -m pytest -q }
Step 'pip-audit (runtime + dev deps)' { & "$py\pip-audit.exe" -r requirements-dev.txt --progress-spinner off }
Pop-Location

Push-Location $root
Step 'detect-secrets (audited exceptions are marked inline: pragma: allowlist secret)' {
  $files = git ls-files --cached --others --exclude-standard | Where-Object { $_ -notmatch 'package-lock.json|\.(png|jpg|woff2)$|the-tycoons-hotel.html' }
  & "$py\detect-secrets-hook.exe" $files
}
Pop-Location

Push-Location (Join-Path $root 'frontend')
Step 'npm audit' { npm.cmd audit --audit-level=low }
Step 'vitest (frontend)' { npx.cmd vitest run }
Step 'vite build' { npx.cmd vite build }
Pop-Location

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
$failed = 0
foreach ($k in $results.Keys) {
  if ($results[$k]) { Write-Host "PASS  $k" -ForegroundColor Green } else { Write-Host "FAIL  $k" -ForegroundColor Red; $failed++ }
}
exit $failed
