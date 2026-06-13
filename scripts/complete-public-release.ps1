param(
    [string]$Owner = "punksinger94-blip",
    [string]$Repository = "klib-forge",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Version = (& $Python -c "from klib_core import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not determine the package version."
}

$Installer = Join-Path $Root (
    "apps\desktop\src-tauri\target\release\bundle\nsis\" +
    "K-LIB Forge_${Version}_x64-setup.exe"
)
& (Join-Path $Root "scripts\sign-windows.ps1") -Path $Installer
if ($LASTEXITCODE -ne 0) {
    throw "Installer signing failed."
}

& (Join-Path $Root "scripts\generate-release-metadata.ps1") -Installer $Installer
if ($LASTEXITCODE -ne 0) {
    throw "Release metadata generation failed."
}

& (Join-Path $Root "scripts\publish-github-release.ps1") `
    -Owner $Owner `
    -Repository $Repository `
    -Visibility $Visibility
if ($LASTEXITCODE -ne 0) {
    throw "GitHub publication failed."
}
