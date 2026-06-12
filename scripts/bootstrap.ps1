$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $Root ".venv"))) {
    python -m venv (Join-Path $Root ".venv")
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -e "${Root}[dev]"

Push-Location (Join-Path $Root "apps\desktop")
try {
    npm install
}
finally {
    Pop-Location
}

Write-Host "K-LIB Forge development environment is ready."
