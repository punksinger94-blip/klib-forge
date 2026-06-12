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

$Rustc = Get-Command rustc -ErrorAction SilentlyContinue
if (-not $Rustc) {
    throw "Rust is required to determine the Tauri target triple."
}

$TargetTriple = (& rustc --print host-tuple).Trim()
if (-not $TargetTriple) {
    throw "Could not determine the Rust target triple."
}

$BuildRoot = Join-Path $Root "build\sidecar"
$DistRoot = Join-Path $BuildRoot "dist"
$WorkRoot = Join-Path $BuildRoot "work"
$SpecRoot = Join-Path $BuildRoot "spec"
$BinaryRoot = Join-Path $Root "apps\desktop\src-tauri\binaries"
$SchemaSource = Join-Path $Root "packages\klib-core\src\klib_core\schemas"
$EntryPoint = Join-Path $Root "services\api\sidecar.py"

New-Item -ItemType Directory -Force -Path $DistRoot, $WorkRoot, $SpecRoot, $BinaryRoot |
    Out-Null

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name klib-api `
    --distpath $DistRoot `
    --workpath $WorkRoot `
    --specpath $SpecRoot `
    --paths (Join-Path $Root "packages\klib-core\src") `
    --paths (Join-Path $Root "services\api\src") `
    --collect-submodules uvicorn `
    --add-data "${SchemaSource};klib_core/schemas" `
    $EntryPoint

$SourceBinary = Join-Path $DistRoot "klib-api.exe"
if (-not (Test-Path $SourceBinary)) {
    throw "PyInstaller did not create $SourceBinary."
}

$TargetBinary = Join-Path $BinaryRoot "klib-api-$TargetTriple.exe"
Copy-Item -Force -LiteralPath $SourceBinary -Destination $TargetBinary

Write-Host "Packaged K-LIB API sidecar: $TargetBinary"
