$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$CargoBin = Join-Path $env:USERPROFILE ".cargo\bin"

function Assert-NativeSuccess {
    param([Parameter(Mandatory)][string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path $Python)) {
    throw "Run .\scripts\bootstrap.ps1 first."
}

if (Test-Path $CargoBin) {
    $env:Path = "$CargoBin;$env:Path"
}

Push-Location $Root
try {
    & $Python -m ruff check .
    Assert-NativeSuccess "Ruff"
    & $Python -m pytest
    Assert-NativeSuccess "Pytest"

    $Dist = Join-Path $Root "dist"
    New-Item -ItemType Directory -Force -Path $Dist | Out-Null
    Get-ChildItem -LiteralPath $Dist -File |
        Where-Object { $_.Name -match '\.(whl|tar\.gz)$' } |
        Remove-Item -Force

    & $Python -m build
    Assert-NativeSuccess "Python package build"
    $Packages = Get-ChildItem -LiteralPath $Dist -File |
        Where-Object { $_.Name -match '\.(whl|tar\.gz)$' }
    & $Python -m twine check $Packages.FullName
    Assert-NativeSuccess "Twine package validation"
}
finally {
    Pop-Location
}

Push-Location (Join-Path $Root "apps\desktop")
try {
    npm run build
    Assert-NativeSuccess "Desktop frontend build"
    if (Get-Command cargo -ErrorAction SilentlyContinue) {
        & (Join-Path $Root "scripts\package-sidecar.ps1")
        npm run tauri build
        Assert-NativeSuccess "Tauri desktop build"
    }
    else {
        Write-Warning "Rust/Cargo is unavailable; frontend built, native Tauri build skipped."
    }
}
finally {
    Pop-Location
}

Write-Host "K-LIB Forge v1.0.0 build completed."
