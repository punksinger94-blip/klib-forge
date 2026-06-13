param(
    [switch]$AllowUnsigned
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Version = (& $Python -c "from klib_core import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not determine the package version."
}

$GitStatus = git -C $Root status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect the Git worktree."
}
if ($GitStatus) {
    throw "Release requires a clean Git worktree."
}
$Branch = (git -C $Root branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not determine the current Git branch."
}
if ($Branch -ne "main") {
    throw "Release must run from the main branch."
}

$Tag = "v$Version"
$ExistingTag = git -C $Root tag --list $Tag
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect Git tags."
}
if ($ExistingTag) {
    throw "Tag $Tag already exists."
}

$Dist = Join-Path $Root "dist"
if (Test-Path -LiteralPath $Dist) {
    $ResolvedDist = (Resolve-Path -LiteralPath $Dist).Path
    if ($ResolvedDist -ne (Join-Path (Resolve-Path $Root).Path "dist")) {
        throw "Refusing to clean unexpected dist path: $ResolvedDist"
    }
    Remove-Item -LiteralPath $ResolvedDist -Recurse -Force
}

& (Join-Path $Root "scripts\build.ps1")

$Installer = Join-Path $Root (
    "apps\desktop\src-tauri\target\release\bundle\nsis\" +
    "K-LIB Forge_${Version}_x64-setup.exe"
)
if (-not (Test-Path -LiteralPath $Installer)) {
    throw "Expected installer was not produced: $Installer"
}

$Signature = Get-AuthenticodeSignature -LiteralPath $Installer
if (-not $AllowUnsigned -and $Signature.Status -ne "Valid") {
    throw "Installer signature is $($Signature.Status). Sign it before public release."
}

& (Join-Path $Root "scripts\generate-release-metadata.ps1") -Installer $Installer

if ($AllowUnsigned) {
    & (Join-Path $Root "scripts\release-doctor.ps1")
}
else {
    & (Join-Path $Root "scripts\release-doctor.ps1") -Public
}
if ($LASTEXITCODE -ne 0) {
    throw "Release readiness doctor failed."
}

Write-Host "Release candidate v$Version passed local preflight."
