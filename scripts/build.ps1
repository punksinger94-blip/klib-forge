$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Run .\scripts\bootstrap.ps1 first."
}

Push-Location $Root
try {
    & $Python -m ruff check .
    & $Python -m pytest
    & $Python -m build
}
finally {
    Pop-Location
}

Push-Location (Join-Path $Root "apps\desktop")
try {
    npm run build
    if (Get-Command cargo -ErrorAction SilentlyContinue) {
        npm run tauri build
    }
    else {
        Write-Warning "Rust/Cargo is unavailable; frontend built, native Tauri build skipped."
    }
}
finally {
    Pop-Location
}

Write-Host "K-LIB Forge v0.1 build completed."

