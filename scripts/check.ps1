<#
  Runs every automated check: backend lint + tests + KB validation, frontend typecheck + tests + build.
  Usage: .\scripts\check.ps1            (add -E2E to also run the Playwright browser tests)
#>
param([switch]$E2E)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $root "apps\api"
$webDir = Join-Path $root "apps\web"
$py = Join-Path $apiDir ".venv\Scripts\python.exe"

function Run($label, $dir, [scriptblock]$cmd) {
  Write-Host "==> $label" -ForegroundColor Green
  Push-Location $dir
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"   # native tools write warnings to stderr; rely on exit codes instead
  try { & $cmd; if ($LASTEXITCODE -ne 0) { throw "$label FAILED (exit $LASTEXITCODE)" } }
  finally { $ErrorActionPreference = $prev; Pop-Location }
}

Run "ruff lint"            $apiDir { & $py -m ruff check . }
Run "ruff format check"    $apiDir { & $py -m ruff format --check . }
Run "knowledge base"       $apiDir { & $py -W ignore -m app.services.knowledge.cli }
Run "pytest"               $apiDir { & $py -W ignore -m pytest }
Run "typecheck"            $webDir { npm run typecheck }
Run "vitest"               $webDir { npm test }
Run "build"                $webDir { npm run build }
if ($E2E) { Run "playwright e2e" $webDir { npm run e2e } }
Write-Host "All checks passed." -ForegroundColor Green
