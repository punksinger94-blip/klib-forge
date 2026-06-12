$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Api = Join-Path $Root ".venv\Scripts\klib-api.exe"

if (-not (Test-Path $Api)) {
    throw "Run .\scripts\bootstrap.ps1 first."
}

Start-Process -FilePath $Api -WorkingDirectory $Root -WindowStyle Hidden
Push-Location (Join-Path $Root "apps\desktop")
try {
    npm run dev
}
finally {
    Pop-Location
}

