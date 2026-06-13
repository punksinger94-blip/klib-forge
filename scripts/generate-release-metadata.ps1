param(
    [Parameter(Mandatory)]
    [string]$Installer
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$ReleaseDir = Join-Path $Root "dist\release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

function Assert-NativeSuccess {
    param([Parameter(Mandatory)][string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

$Artifacts = @(
    Get-ChildItem (Join-Path $Root "dist\*") -File -Include *.whl, *.tar.gz
)
$Artifacts += Get-Item -LiteralPath $Installer

$Checksums = foreach ($Artifact in $Artifacts) {
    $Hash = Get-FileHash -LiteralPath $Artifact.FullName -Algorithm SHA256
    "$($Hash.Hash.ToLowerInvariant())  $($Artifact.Name)"
}
$Checksums | Set-Content -LiteralPath (Join-Path $ReleaseDir "SHA256SUMS.txt") -Encoding ascii

& $Python -m pip_audit `
    --format cyclonedx-json `
    --output (Join-Path $ReleaseDir "sbom-python.cdx.json")
Assert-NativeSuccess "Python dependency audit"

Push-Location (Join-Path $Root "apps\desktop")
try {
    npm sbom --sbom-format cyclonedx > (Join-Path $ReleaseDir "sbom-npm.cdx.json")
    Assert-NativeSuccess "npm SBOM generation"
}
finally {
    Pop-Location
}

Push-Location (Join-Path $Root "apps\desktop\src-tauri")
try {
    cargo metadata --format-version 1 > (Join-Path $ReleaseDir "sbom-rust-metadata.json")
    Assert-NativeSuccess "Rust dependency metadata generation"
}
finally {
    Pop-Location
}

Copy-Item -LiteralPath $Installer -Destination $ReleaseDir -Force
Write-Host "Release checksums and SBOM metadata written to $ReleaseDir"
