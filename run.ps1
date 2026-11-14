# EduNest 2.0 one-command dev start for Windows PowerShell.  .\run.ps1 [-Reset]
param([switch]$Reset)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location "$Root\backend"
if (-not (Test-Path .venv)) {
  Write-Host "Creating Python virtualenv..."
  python -m venv .venv
  .\.venv\Scripts\pip install -q -r requirements.txt
}
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if ($Reset -or -not (Test-Path edunest.db)) { .\.venv\Scripts\python -m app.seed --reset }
Set-Location "$Root\frontend"
if (-not (Test-Path node_modules)) { npm install --no-audit --no-fund }
$api = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$Root\backend" ".\.venv\Scripts\uvicorn.exe" "app.main:app --reload --port 8000"
Write-Host "`n  EduNest 2.0 -> http://localhost:5173   (API docs: http://localhost:8000/docs)`n"
try { npm run dev } finally { Stop-Process -Id $api.Id -ErrorAction SilentlyContinue }
