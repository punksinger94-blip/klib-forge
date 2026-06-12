$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$CargoBin = Join-Path $env:USERPROFILE ".cargo\bin"

if (-not (Test-Path $Python)) {
    throw "Run .\scripts\bootstrap.ps1 first."
}

if (Test-Path $CargoBin) {
    $env:Path = "$CargoBin;$env:Path"
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
        & (Join-Path $Root "scripts\package-sidecar.ps1")
        npm run tauri build
    }
    else {
        Write-Warning "Rust/Cargo is unavailable; frontend built, native Tauri build skipped."
    }
}
finally {
    Pop-Location
}

Write-Host "K-LIB Forge v0.1.1 build completed."
