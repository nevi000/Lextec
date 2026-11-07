<#
  LexTec Bridge - local development launcher (Windows PowerShell)

  Usage:   .\scripts\dev.ps1                  # set up if needed, then start API + web
           .\scripts\dev.ps1 -Seed            # additionally create synthetic demo cases (mock AI)
           .\scripts\dev.ps1 -ApiPort 8001    # if port 8000 is already used by another program

  Defaults - Frontend: http://localhost:5173    API: http://localhost:8000    API docs: http://localhost:8000/docs
  Press Ctrl+C to stop both processes.
#>
param([switch]$Seed, [int]$ApiPort = 8000, [int]$WebPort = 5173)

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

# --- run --------------------------------------------------------------------------------
Step "Starting API on http://localhost:$ApiPort and web on http://localhost:$WebPort (Ctrl+C to stop)"
$api = Start-Process -FilePath $py -ArgumentList @("-W", "ignore", "-m", "uvicorn", "app.main:app", "--reload", "--port", "$ApiPort") `
  -WorkingDirectory $apiDir -NoNewWindow -PassThru
$env:VITE_API_PROXY = "http://localhost:$ApiPort"
$env:VITE_PORT = "$WebPort"
$web = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") -WorkingDirectory $webDir -NoNewWindow -PassThru

try {
  Wait-Process -Id $api.Id, $web.Id -ErrorAction SilentlyContinue
  while (-not $api.HasExited -and -not $web.HasExited) { Start-Sleep -Seconds 1 }
} finally {
  foreach ($p in @($api, $web)) {
    if ($p -and -not $p.HasExited) { & taskkill /PID $p.Id /T /F | Out-Null }
  }
}
