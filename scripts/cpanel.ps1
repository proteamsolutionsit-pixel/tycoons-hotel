<#
  cPanel API helpers for deploying (no SSH needed).
  Staging (devtycoonshotel.proteam.co.in):  $env:CP_TARGET = '';     . .\scripts\cpanel.ps1
  Live (thetycoonshotel.com):               $env:CP_TARGET = 'live'; . .\scripts\cpanel.ps1   (uses cpanel-live.txt)
  Credentials: cpanel.txt in the project root (git-ignored), two lines:
      username- <cpanel user>
      token- <API token>      (cPanel > Security > Manage API Tokens; revoke when no longer needed)
  The token is never printed. Responses are decoded from the raw stream as UTF-8,
  because Windows PowerShell 5.1 mis-reads cPanel's quoted charset and garbles text.
#>
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.Net.Http

$root = Split-Path -Parent $PSScriptRoot
# Target: development (default) or live.  $env:CP_TARGET = 'live'; . .\scripts\cpanel.ps1
$script:CpTarget = if ($env:CP_TARGET -eq 'live') { 'live' } else { 'dev' }
$cred = Get-Content (Join-Path $root $(if ($script:CpTarget -eq 'live') { 'cpanel-live.txt' } else { 'cpanel.txt' }))
$script:CpUser = ($cred[0] -replace '^[^-:=]+[-:=]\s*', '').Trim()
$script:CpToken = ($cred[1] -replace '^[^-:=]+[-:=]\s*', '').Trim()
$script:CpDomain = if ($script:CpTarget -eq 'live') { 'thetycoonshotel.com' } else { 'devtycoonshotel.proteam.co.in' }
# cPanel answers on the server's shared hostname certificate; pin to the server
# IP and accept that certificate for :2083 only (the site itself uses AutoSSL).
$script:CpHost = '78.159.97.108'
$script:CpHome = if ($env:CP_HOME) { $env:CP_HOME } elseif ($script:CpTarget -eq 'live') { "/home2/$($script:CpUser)" } else { "/home3/$($script:CpUser)" }

# A compiled callback: PowerShell scriptblocks cannot run on HttpClient's network
# thread in Windows PowerShell 5.1. Accepts the certificate only for the cPanel host.
if (-not ([System.Management.Automation.PSTypeName]'CpCertPolicy').Type) {
  Add-Type -ReferencedAssemblies System.Net.Http -TypeDefinition @"
using System; using System.Net.Http; using System.Net.Security; using System.Security.Cryptography.X509Certificates;
public static class CpCertPolicy {
  public static string Host;
  public static HttpClientHandler NewHandler() {
    var h = new HttpClientHandler();
    h.ServerCertificateCustomValidationCallback = (HttpRequestMessage m, X509Certificate2 c, X509Chain ch, SslPolicyErrors e) =>
      e == SslPolicyErrors.None || (m.RequestUri.Host == Host && m.RequestUri.Port == 2083);
    return h;
  }
}
"@
}
[CpCertPolicy]::Host = $script:CpHost

function New-CpClient {
  $h = [CpCertPolicy]::NewHandler()
  $c = New-Object System.Net.Http.HttpClient($h)
  $c.Timeout = [TimeSpan]::FromMinutes(10)
  $c.DefaultRequestHeaders.TryAddWithoutValidation('Authorization', "cpanel $($script:CpUser):$($script:CpToken)") | Out-Null
  return $c
}

function Read-CpResponse($resp) {
  $bytes = $resp.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
  $text = [Text.Encoding]::UTF8.GetString($bytes)
  if (-not $resp.IsSuccessStatusCode) { throw "HTTP $([int]$resp.StatusCode): $text" }
  try { return $text | ConvertFrom-Json } catch { return $text }
}

function ConvertTo-Query([hashtable]$p) {
  ($p.GetEnumerator() | ForEach-Object { [uri]::EscapeDataString($_.Key) + '=' + [Net.WebUtility]::UrlEncode([string]$_.Value) }) -join '&'
}

# UAPI: Invoke-Uapi Mysql create_database @{ name = '...' }
function Invoke-Uapi([string]$module, [string]$func, [hashtable]$params = @{}) {
  $c = New-CpClient
  try {
    $body = New-Object System.Net.Http.StringContent((ConvertTo-Query $params), [Text.Encoding]::UTF8, 'application/x-www-form-urlencoded')
    $r = Read-CpResponse ($c.PostAsync("https://$($script:CpHost):2083/execute/$module/$func", $body).GetAwaiter().GetResult())
  } finally { $c.Dispose() }
  if ($r.status -ne 1) { throw "$module/$func failed: $(($r.errors) -join '; ')" }
  return $r.data
}

# API2 (for Fileman::fileop and Cron, which have no UAPI equivalent here)
function Invoke-Api2([string]$module, [string]$func, [hashtable]$params = @{}) {
  $q = @{ cpanel_jsonapi_user = $script:CpUser; cpanel_jsonapi_apiversion = '2'; cpanel_jsonapi_module = $module; cpanel_jsonapi_func = $func }
  foreach ($k in $params.Keys) { $q[$k] = $params[$k] }
  $c = New-CpClient
  try {
    $body = New-Object System.Net.Http.StringContent((ConvertTo-Query $q), [Text.Encoding]::UTF8, 'application/x-www-form-urlencoded')
    $r = Read-CpResponse ($c.PostAsync("https://$($script:CpHost):2083/json-api/cpanel", $body).GetAwaiter().GetResult())
  } finally { $c.Dispose() }
  $res = $r.cpanelresult
  if ($res.error -or ($res.event -and $res.event.result -ne 1)) { throw "$module::$func failed: $($res.error) $($res.data | ConvertTo-Json -Compress -Depth 5)" }
  return $res.data
}

# Upload a local file into a server directory (creates new files; refuses to overwrite)
function Send-CpFile([string]$localPath, [string]$remoteDir) {
  $c = New-CpClient
  try {
    $form = New-Object System.Net.Http.MultipartFormDataContent
    # Field names must be quoted for cPanel's parser; unquoted, "dir" is ignored and files land in ~/
    $form.Add((New-Object System.Net.Http.StringContent($remoteDir)), '"dir"')
    $form.Add((New-Object System.Net.Http.StringContent('1')), '"overwrite"')
    $bytes = [IO.File]::ReadAllBytes($localPath)
    $file = New-Object System.Net.Http.ByteArrayContent(, $bytes)
    # cPanel's parser needs quoted name/filename and no RFC 5987 filename* (which .NET adds by default)
    $file.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/octet-stream')
    $cd = New-Object System.Net.Http.Headers.ContentDispositionHeaderValue('form-data')
    $cd.Name = '"file-1"'
    $cd.FileName = '"' + [IO.Path]::GetFileName($localPath) + '"'
    $file.Headers.ContentDisposition = $cd
    $form.Add($file)
    $r = Read-CpResponse ($c.PostAsync("https://$($script:CpHost):2083/execute/Fileman/upload_files", $form).GetAwaiter().GetResult())
  } finally { $c.Dispose() }
  if ($r.status -ne 1 -or $r.data.failed -gt 0) { throw "upload failed: $(($r.errors) -join '; ') $($r.data.uploads | ConvertTo-Json -Compress)" }
}

# Write text to a server file (creates or replaces; byte-exact UTF-8, no BOM)
function Set-CpFileContent([string]$remoteDir, [string]$name, [string]$content) {
  Invoke-Uapi Fileman save_file_content @{ dir = $remoteDir; file = $name; content = $content; from_charset = 'UTF-8'; to_charset = 'UTF-8' } | Out-Null
}

function Get-CpFileContent([string]$remoteDir, [string]$name) {
  (Invoke-Uapi Fileman get_file_content @{ dir = $remoteDir; file = $name; from_charset = 'UTF-8'; to_charset = 'UTF-8' }).content
}

function Remove-CpPath([string]$path) {
  Invoke-Api2 Fileman fileop @{ op = 'unlink'; sourcefiles = $path; doubledecode = '0' } | Out-Null
}

function Expand-CpArchive([string]$archive, [string]$destDir) {
  Invoke-Api2 Fileman fileop @{ op = 'extract'; sourcefiles = $archive; destfiles = $destDir; doubledecode = '0' } | Out-Null
}

function Get-CpDirectory([string]$dir) {
  Invoke-Uapi Fileman list_files @{ dir = $dir; include_mime = '0'; show_hidden = '1' } | ForEach-Object { $_ }
}

# Passenger restarts the app when tmp/restart.txt changes
function Restart-CpPythonApp([string]$appRoot) {
  Set-CpFileContent "$appRoot/tmp" 'restart.txt' ([DateTime]::UtcNow.ToString('o'))
}

# Run a shell command once on the server through cron (there is no SSH), wait for it, and remove the
# cron line again. Returns the exit code and output. Polls every 40 s to keep API calls few.
#   $r = Invoke-CpOnce "cd ~/tycoons && ~/virtualenv/tycoons/3.10/bin/python migrate.py" 'migrate' 10
function Invoke-CpOnce([string]$cmd, [string]$tag, [int]$maxMinutes = 8) {
  $h = $script:CpHome
  $marker = "cron-$tag.done"
  $log = "$h/tmp/cron-$tag.log"
  $full = "( $cmd ) > $log 2>&1; echo `$? > $h/tmp/$marker"
  Invoke-Api2 Cron add_line @{ command = $full; minute = '*'; hour = '*'; day = '*'; month = '*'; weekday = '*' } | Out-Null
  $deadline = (Get-Date).AddMinutes($maxMinutes)
  $done = $false
  try {
    while ((Get-Date) -lt $deadline) {
      Start-Sleep -Seconds 40
      if (Get-CpDirectory "$h/tmp" | Where-Object { $_.file -eq $marker }) { $done = $true; break }
    }
  } finally {
    # API2 Cron::remove_line needs "linekey"; passing the key as "line" silently removes nothing
    foreach ($l in (Invoke-Api2 Cron listcron | Where-Object { $_.command -like "*$marker*" })) {
      Invoke-Api2 Cron remove_line @{ linekey = $l.linekey } | Out-Null
    }
    if (Invoke-Api2 Cron listcron | Where-Object { $_.command -like "*$marker*" }) { Write-Warning "one-off cron line $tag is still installed - remove it" }
  }
  if (-not $done) { throw "cron job $tag did not finish within $maxMinutes min" }
  $rc = (Get-CpFileContent "$h/tmp" $marker).Trim()
  $out = Get-CpFileContent "$h/tmp" "cron-$tag.log"
  Remove-CpPath "$h/tmp/$marker"; Remove-CpPath $log
  [pscustomobject]@{ ExitCode = $rc; Output = $out }
}
