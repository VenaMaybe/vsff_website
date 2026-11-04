param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$runtime = Join-Path $project '.mobile-test'
$statePath = Join-Path $runtime 'session.json'
$client = Join-Path $runtime 'cloudflared.exe'
$python = Join-Path $project '.venv\Scripts\python.exe'
$appFile = Join-Path $project 'app.py'

if ($Stop) {
    if (-not (Test-Path -LiteralPath $statePath)) { Write-Output 'No recorded mobile test session.'; exit }
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($entry in @(@{id=$state.tunnelPid;path=$client},@{id=$state.appPid;path=$python})) {
        $running = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
        if (-not $running) { continue }
        if ($running.Path -ne $entry.path) { throw 'PID no longer belongs to this mobile test. Refusing to stop it.' }
        if ($entry.path -eq $python) {
            $details = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.id)"
            if (-not $details.CommandLine.Contains($appFile)) { throw 'Python command no longer matches this app. Refusing to stop it.' }
        }
        Stop-Process -Id $entry.id
    }
    Remove-Item -LiteralPath $statePath
    Write-Output 'Mobile test stopped. The normal .env was not changed.'
    exit
}

# Run only after explicit approval of the public Cloudflare test endpoint.
# Existing Google login/document ACLs remain required; there is no test-login bypass.
if (-not (Test-Path -LiteralPath $client)) { throw 'Verified cloudflared.exe is missing from .mobile-test.' }
if ((Get-FileHash -LiteralPath $client -Algorithm SHA256).Hash.ToLower() -ne '2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343') { throw 'Cloudflare client checksum mismatch.' }
if (Test-Path -LiteralPath $statePath) { throw 'A mobile test session is recorded. Stop/review it before starting another.' }
$probe = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,5000)
try { $probe.Start() } catch { throw 'Port 5000 is in use. Stop the normal local app first; do not run two app instances against the same database.' } finally { $probe.Stop() }
$stamp = [guid]::NewGuid().ToString('N')
$tunnelLog = Join-Path $runtime "$stamp-tunnel.log"
$tunnelProcess = $null
$appProcess = $null
$overrides = @{}
try {
    $tunnelProcess = Start-Process -FilePath $client -ArgumentList @('tunnel','--no-autoupdate','--protocol','http2','--url','http://127.0.0.1:5000','--logfile',$tunnelLog) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime "$stamp-tunnel.out.log") -RedirectStandardError (Join-Path $runtime "$stamp-tunnel.err.log")
    $url = $null
    for ($attempt=0; $attempt -lt 45; $attempt++) {
        if ($tunnelProcess.HasExited) { throw 'Cloudflare exited before allocating an address. See the private runtime log.' }
        if (Test-Path -LiteralPath $tunnelLog) {
            $match = [regex]::Match((Get-Content -LiteralPath $tunnelLog -Raw),'https://[a-z0-9-]+\.trycloudflare\.com')
            if ($match.Success) { $url=$match.Value; break }
        }
        Start-Sleep -Seconds 1
    }
    if (-not $url) { throw 'Cloudflare did not provide a test address.' }
    $settings = @{
        PDF_REVIEW_ENV='development'; PDF_REVIEW_HOST='127.0.0.1'; PDF_REVIEW_PORT='5000'
        PDF_REVIEW_SERVER_NAME=([uri]$url).Host; PDF_REVIEW_SCHEME='https'
        PDF_REVIEW_COOKIE_SECURE='1'; PDF_REVIEW_PROXY_HOPS='1'; FLASK_DEBUG='0'
    }
    foreach ($key in $settings.Keys) {
        $overrides[$key]=[Environment]::GetEnvironmentVariable($key,'Process')
        [Environment]::SetEnvironmentVariable($key,$settings[$key],'Process')
    }
    $appProcess = Start-Process -FilePath $python -ArgumentList @('"'+$appFile+'"') -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime "$stamp-app.out.log") -RedirectStandardError (Join-Path $runtime "$stamp-app.err.log")
    $ready = $false
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        if ($appProcess.HasExited) { throw 'PDF Review exited. See its private runtime log.' }
        try {
            $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5000/healthz' -Headers @{Host=([uri]$url).Host} -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready=$true; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'PDF Review did not become ready.' }
    @{url=$url;tunnelPid=$tunnelProcess.Id;appPid=$appProcess.Id} | ConvertTo-Json | Set-Content -LiteralPath $statePath
    Write-Output "Mobile test address: $url"
    Write-Output "Add this exact redirect URI to the existing Google Web OAuth client: $url/auth/google/callback"
    Write-Output 'Keep the localhost redirect too. Open the HTTPS address on both devices after Google saves the new callback.'
    Write-Output 'Stop afterward with: .\mobile_https.ps1 -Stop'
} catch {
    if ($tunnelProcess -and -not $tunnelProcess.HasExited) { $tunnelProcess.Kill() }
    if ($appProcess -and -not $appProcess.HasExited) { $appProcess.Kill() }
    throw
} finally {
    foreach ($key in $overrides.Keys) { [Environment]::SetEnvironmentVariable($key,$overrides[$key],'Process') }
}
