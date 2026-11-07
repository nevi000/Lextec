<#
  LexTec Bridge - local development launcher (Windows PowerShell)

  Usage:   .\scripts\dev.ps1                  # set up if needed, then start API + web
           .\scripts\dev.ps1 -Seed            # additionally create synthetic demo cases (mock AI)
           .\scripts\dev.ps1 -ApiPort 8001    # if port 8000 is already used by another program
           .\scripts\dev.ps1 -Lan             # Sprachbruecke: let a phone on the same Wi-Fi open the web app (API stays on localhost)
           .\scripts\dev.ps1 -Lan -LanIp 192.168.1.20   # if the automatically chosen address is not the one your phone can reach

  Defaults - Frontend: http://localhost:5173    API: http://localhost:8000    API docs: http://localhost:8000/docs
  Press Ctrl+C to stop both processes.
#>
param([switch]$Seed, [switch]$Lan, [string]$LanIp = "", [int]$ApiPort = 8000, [int]$WebPort = 5173)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $root "apps\api"
$webDir = Join-Path $root "apps\web"
$py = Join-Path $apiDir ".venv\Scripts\python.exe"

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Green }

# --- .env -------------------------------------------------------------------------------
if (-not (Test-Path (Join-Path $root ".env"))) {
  Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
  Step "Created .env from .env.example (AI_PROVIDER=mock, no API key needed)"
}

# --- backend setup ----------------------------------------------------------------------
if (-not (Test-Path $py)) {
  Step "Creating Python virtual environment (apps/api/.venv)"
  if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv venv --python 3.12 (Join-Path $apiDir ".venv")
    uv pip install --python $py -e "$apiDir[dev]"
  } else {
    python -m venv (Join-Path $apiDir ".venv")
    & $py -m pip install --quiet -e "$apiDir[dev]"
  }
}

# --- frontend setup ---------------------------------------------------------------------
if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
  Step "Installing frontend dependencies (npm install)"
  Push-Location $webDir; npm install; Pop-Location
}

# --- database ---------------------------------------------------------------------------
Step "Applying database migrations"
Push-Location $apiDir
& $py -W ignore -m app.cli migrate
if ($Seed) { Step "Seeding synthetic demo cases"; & $py -W ignore -m app.cli seed-demo }
Pop-Location

# --- ports ------------------------------------------------------------------------------
foreach ($port in @($ApiPort, $WebPort)) {
  $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($busy) {
    $name = (Get-Process -Id $busy[0].OwningProcess -ErrorAction SilentlyContinue).ProcessName
    throw "Port $port is already in use by '$name' (PID $($busy[0].OwningProcess)). Stop it or choose another port, e.g. -ApiPort 8001 / -WebPort 5174."
  }
}

# --- LAN mode (Sprachbruecke on a phone) ------------------------------------------------------
$publicBase = $null
if ($Lan) {
  # Candidates = IPv4 addresses of connected physical-looking adapters. The one that owns the default route is
  # preferred (that is the Wi-Fi/Ethernet/hotspot the phone is on); WSL/Hyper-V/Docker/VPN adapters are listed but not chosen.
  $virtual = "vEthernet|WSL|Hyper-V|Docker|VPN|VirtualBox|VMware|Loopback|Bluetooth|TAP|Tailscale|ZeroTier"
  $default = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue | Sort-Object { $_.RouteMetric + (Get-NetIPInterface -InterfaceIndex $_.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).InterfaceMetric } | Select-Object -First 1
  $cands = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    ForEach-Object {
      $net = Get-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue
      [pscustomobject]@{ Ip = $_.IPAddress; Alias = $_.InterfaceAlias; Index = $_.InterfaceIndex; Profile = $net.NetworkCategory
        Virtual = ($_.InterfaceAlias -match $virtual); Default = ($default -and $_.InterfaceIndex -eq $default.InterfaceIndex) } })
  Step "Network addresses of this computer:"
  foreach ($c in $cands) {
    $tag = if ($c.Default) { "default route" } elseif ($c.Virtual) { "virtual adapter" } else { "" }
    Write-Host ("    {0,-16} {1,-34} {2,-8} {3}" -f $c.Ip, $c.Alias, $c.Profile, $tag)
  }
  if ($LanIp) { $chosen = $cands | Where-Object { $_.Ip -eq $LanIp } | Select-Object -First 1
    if (-not $chosen) { throw "-LanIp $LanIp is not an address of this computer (see the list above)." } }
  else { $chosen = ($cands | Where-Object { $_.Default -and -not $_.Virtual } | Select-Object -First 1)
    if (-not $chosen) { $chosen = ($cands | Where-Object { -not $_.Virtual } | Select-Object -First 1) } }
  if (-not $chosen) { throw "No usable network address found. Connect to Wi-Fi/Ethernet or pass -LanIp <address>." }
  $lanIp = $chosen.Ip
  $publicBase = "http://${lanIp}:$WebPort"
  $env:VITE_HOST = "0.0.0.0"                 # web server listens on the network; localhost keeps working
  $env:BRIDGE_PUBLIC_BASE_URL = $publicBase  # the QR code uses exactly this address
  Step "LAN mode: the phone opens $publicBase (same network only). The API is NOT exposed; the phone may only use /api/bridge/*."
  if ($chosen.Profile -eq "Public") {
    Write-Host "    Note: this network is classified 'Public' by Windows (typical for hotspots/guest Wi-Fi); inbound connections are blocked unless allowed below." -ForegroundColor Yellow
  }
}

# --- run --------------------------------------------------------------------------------
Step "Starting API on http://localhost:$ApiPort and web on http://localhost:$WebPort (Ctrl+C to stop)"
$api = Start-Process -FilePath $py -ArgumentList @("-W", "ignore", "-m", "uvicorn", "app.main:app", "--reload", "--port", "$ApiPort") `
  -WorkingDirectory $apiDir -NoNewWindow -PassThru
$env:VITE_API_PROXY = "http://localhost:$ApiPort"
$env:VITE_PORT = "$WebPort"
$web = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") -WorkingDirectory $webDir -NoNewWindow -PassThru

if ($Lan) {
  # Verify what the phone needs: the web server must answer on the network address (not only on localhost).
  $ok = $false
  for ($i = 0; $i -lt 40 -and -not $ok; $i++) {
    Start-Sleep -Milliseconds 500
    try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "$publicBase/"; $ok = $true } catch { }
  }
  if ($ok) { Step "Reachable on $publicBase from this computer." }
  else { Write-Host "    $publicBase does not answer yet. Check the messages above (port in use? Vite error?)." -ForegroundColor Red }
  # Firewall: is there already an inbound allow rule for node.exe / this port for the active profile?
  $node = (Get-Command node -ErrorAction SilentlyContinue).Source
  $rules = Get-NetFirewallRule -Direction Inbound -Enabled True -Action Allow -ErrorAction SilentlyContinue
  $allowed = $false
  foreach ($r in $rules) {
    $app = ($r | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue).Program
    $port = ($r | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue).LocalPort
    $profileOk = ($r.Profile -eq "Any") -or ($r.Profile.ToString() -match $chosen.Profile.ToString())
    if ($profileOk -and (($node -and $app -and $app -ieq $node) -or $port -contains "$WebPort")) { $allowed = $true; break }
  }
  if ($allowed) { Step "Firewall: an inbound allow rule for this port/node.exe already exists for the '$($chosen.Profile)' profile." }
  else {
    Write-Host "    Firewall: no matching allow rule found. If the phone cannot connect, run in an ADMIN PowerShell (narrow: this port, this network profile, local subnet only):" -ForegroundColor Yellow
    Write-Host "    New-NetFirewallRule -DisplayName 'LexTec dev web $WebPort' -Direction Inbound -Protocol TCP -LocalPort $WebPort -Profile $($chosen.Profile) -RemoteAddress LocalSubnet -Action Allow" -ForegroundColor Yellow
    Write-Host "    Remove after the demo:  Remove-NetFirewallRule -DisplayName 'LexTec dev web $WebPort'" -ForegroundColor Yellow
  }
}

try {
  Wait-Process -Id $api.Id, $web.Id -ErrorAction SilentlyContinue
  while (-not $api.HasExited -and -not $web.HasExited) { Start-Sleep -Seconds 1 }
} finally {
  foreach ($p in @($api, $web)) {
    if ($p -and -not $p.HasExited) { & taskkill /PID $p.Id /T /F | Out-Null }
  }
}
