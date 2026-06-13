$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Assert-NativeSuccess {
    param([Parameter(Mandatory)][string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path (Join-Path $Root ".venv"))) {
    python -m venv (Join-Path $Root ".venv")
    Assert-NativeSuccess "Virtual environment creation"
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
Assert-NativeSuccess "Pip upgrade"
& $Python -m pip install -r (Join-Path $Root "requirements\dev-lock.txt")
Assert-NativeSuccess "Locked dependency installation"
& $Python -m pip install --no-deps -e $Root
Assert-NativeSuccess "Editable K-LIB Forge installation"

Push-Location (Join-Path $Root "apps\desktop")
try {
    npm ci
    Assert-NativeSuccess "Desktop dependency installation"
}
finally {
    Pop-Location
}

Write-Host "K-LIB Forge development environment is ready."
