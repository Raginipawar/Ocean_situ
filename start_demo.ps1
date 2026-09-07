# VARUNA — one-command demo launcher, built for the offline jury round.
#
# Uses a PRODUCTION build of the frontend, not `npm run dev`. Reason this
# matters: Vite's dev server compiles routes on first visit -- the very
# first navigation to a Three.js-heavy route (Digital Twin / the globe) can
# hang 20-30+ seconds while it transforms everything, which looks exactly
# like a broken site to someone watching live. A production build has zero
# on-demand compilation; every navigation is fast from the first one.
#
# Also starts the Graph Fusion Engine with real Person 4 model-pipeline
# data, with an automatic silent fallback to mock data if the pipeline hits
# any issue (FallbackModelSource in graph_fusion/adapters.py) -- the site
# should never go down because of it.
#
# Run from anywhere:  .\start_demo.ps1
# Stop: close the two PowerShell windows it opens, or Ctrl+C in each.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
# Vite's own default preview port -- NOT passed as a --port flag below.
# `npm run preview -- --port 4173` silently drops --port somewhere in
# PowerShell's argument passing (vite ends up treating "4173" as a
# positional root path instead, and then can't find dist/). Relying on the
# default sidesteps that entirely; keep this in sync if that ever changes.
$frontendPort = 4173

Write-Host "=== VARUNA demo launcher ===" -ForegroundColor Cyan
Write-Host ""

# --- 1. Build the frontend (production, no dev-server compile-on-visit) ---
Write-Host "[1/3] Building frontend for production..." -ForegroundColor Cyan
Push-Location "$root\frontend"
npm run build
if (-not (Test-Path "dist\index.html")) {
    throw "Build finished but dist\index.html is missing -- something went wrong."
}
Pop-Location
# Small buffer: this project lives in a live-synced OneDrive folder, which
# has occasionally shown a brief lag between a fast build finishing and the
# new dist/ files being visible to the very next process that reads them.
Start-Sleep -Seconds 2
Write-Host "      Build complete." -ForegroundColor Green

# --- 2. Graph Fusion Engine, real Person 4 model data, safety-net fallback on ---
Write-Host ""
Write-Host "[2/3] Starting Graph Fusion Engine (port 8000, real model-pipeline data)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\varuna-graph-fusion'; " +
    ".\.venv\Scripts\Activate.ps1; " +
    "`$env:VARUNA_MODEL_SOURCE = 'pipeline'; " +
    "`$env:VARUNA_CORS_ORIGINS = 'http://localhost:$frontendPort,http://127.0.0.1:$frontendPort'; " +
    "Write-Host 'Graph Fusion Engine -- keep this window open during the demo' -ForegroundColor Green; " +
    "uvicorn graph_fusion.api:app --host 127.0.0.1 --port 8000"
)

Write-Host "      Waiting for it to come up..." -ForegroundColor DarkGray
$engineReady = $false
$health = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        if ($health.status -eq "ok") { $engineReady = $true; break }
    } catch {}
}

if ($engineReady) {
    Write-Host "      Engine is up -- status: $($health.status), region: $($health.region)" -ForegroundColor Green
} else {
    Write-Host "      Engine did not respond within 30s -- check its window for errors." -ForegroundColor Red
    Write-Host "      (The site will still start, but Digital Twin will show 'can't reach backend'.)" -ForegroundColor Yellow
}

# --- 3. Serve the production build ---
Write-Host ""
Write-Host "[3/3] Serving production build on port $frontendPort..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\frontend'; " +
    "Write-Host 'Frontend (production build) -- keep this window open during the demo' -ForegroundColor Green; " +
    "npm run preview"
)

Write-Host ""
Write-Host "=== Ready ===" -ForegroundColor Cyan
Write-Host "Open http://localhost:$frontendPort and go to Digital Twin." -ForegroundColor Yellow
Write-Host "First real-data fusion call typically takes 1-4 seconds." -ForegroundColor Yellow
Write-Host ""
Write-Host "Sanity check anytime: curl http://127.0.0.1:8000/health" -ForegroundColor DarkGray
