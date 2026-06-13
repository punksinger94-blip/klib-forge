param(
    [switch]$Public
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Failures = [System.Collections.Generic.List[string]]::new()

function Pass {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Block {
    param([Parameter(Mandatory)][string]$Message)
    $Failures.Add($Message)
    Write-Host "[BLOCK] $Message" -ForegroundColor Red
}

function Assert-File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Label
    )
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Pass $Label
        return $true
    }
    Block "$Label is missing: $Path"
    return $false
}

if (-not (Test-Path -LiteralPath $Python)) {
    Block "Development environment is missing. Run .\scripts\bootstrap.ps1."
}
else {
    $Version = (& $Python -c "from klib_core import __version__; print(__version__)").Trim()
    if ($LASTEXITCODE -ne 0) {
        Block "Could not read project versions."
    }
    else {
        $DesktopVersion = (
            Get-Content -Raw -LiteralPath (Join-Path $Root "apps\desktop\package.json") |
                ConvertFrom-Json
        ).version
        $TauriVersion = (
            Get-Content -Raw -LiteralPath (
                Join-Path $Root "apps\desktop\src-tauri\tauri.conf.json"
            ) | ConvertFrom-Json
        ).version
        $CargoVersionMatch = Get-Content -LiteralPath (
            Join-Path $Root "apps\desktop\src-tauri\Cargo.toml"
        ) | Select-String -Pattern '^version = "([^"]+)"' | Select-Object -First 1
        $CargoVersion = $CargoVersionMatch.Matches[0].Groups[1].Value
        $DistinctVersions = @(
            $Version,
            $DesktopVersion,
            $CargoVersion,
            $TauriVersion
        ) | Sort-Object -Unique
        if ($DistinctVersions.Count -eq 1) {
            Pass "All package manifests agree on version $Version."
        }
        else {
            Block (
                "Version mismatch: Python=$Version, desktop=$DesktopVersion, " +
                "Cargo=$CargoVersion, Tauri=$TauriVersion"
            )
        }
    }
}

$Branch = (git -C $Root branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    Block "Could not determine the current Git branch."
}
elseif ($Branch -eq "main") {
    Pass "Current branch is main."
}
else {
    Block "Current branch is '$Branch'; releases must come from main."
}

$Status = git -C $Root status --porcelain
if ($LASTEXITCODE -ne 0) {
    Block "Could not inspect the Git worktree."
}
elseif ($Status) {
    Block "Git worktree is not clean."
}
else {
    Pass "Git worktree is clean."
}

if ($Version) {
    $Wheel = Join-Path $Root "dist\klib_forge-$Version-py3-none-any.whl"
    $Sdist = Join-Path $Root "dist\klib_forge-$Version.tar.gz"
    $InstallerName = "K-LIB Forge_${Version}_x64-setup.exe"
    $Installer = Join-Path $Root "dist\release\$InstallerName"
    $Checksums = Join-Path $Root "dist\release\SHA256SUMS.txt"

    $ArtifactChecks = @(
        (Assert-File -Path $Wheel -Label "Python wheel"),
        (Assert-File -Path $Sdist -Label "Python source archive"),
        (Assert-File -Path $Installer -Label "Windows installer"),
        (Assert-File -Path $Checksums -Label "SHA-256 checksum manifest"),
        (Assert-File -Path (Join-Path $Root "dist\release\sbom-python.cdx.json") -Label "Python SBOM"),
        (Assert-File -Path (Join-Path $Root "dist\release\sbom-npm.cdx.json") -Label "npm SBOM"),
        (Assert-File -Path (Join-Path $Root "dist\release\sbom-rust-metadata.json") -Label "Rust dependency metadata")
    )
    $ArtifactsPresent = $ArtifactChecks -notcontains $false

    if ($ArtifactsPresent) {
        $ExpectedHashes = @{}
        foreach ($Line in Get-Content -LiteralPath $Checksums -Encoding ascii) {
            if ($Line -match '^([0-9a-f]{64})  (.+)$') {
                $ExpectedHashes[$Matches[2]] = $Matches[1]
            }
        }
        $HashFailures = @()
        foreach ($Artifact in @($Wheel, $Sdist, $Installer)) {
            $Name = Split-Path -Leaf $Artifact
            $Actual = (Get-FileHash -LiteralPath $Artifact -Algorithm SHA256).Hash.ToLowerInvariant()
            if (-not $ExpectedHashes.ContainsKey($Name) -or $ExpectedHashes[$Name] -ne $Actual) {
                $HashFailures += $Name
            }
        }
        if ($HashFailures) {
            Block "Checksum verification failed for: $($HashFailures -join ', ')"
        }
        else {
            Pass "All release artifact checksums match."
        }

        try {
            Get-Content -Raw -LiteralPath (Join-Path $Root "dist\release\sbom-python.cdx.json") |
                ConvertFrom-Json | Out-Null
            Get-Content -Raw -LiteralPath (Join-Path $Root "dist\release\sbom-npm.cdx.json") |
                ConvertFrom-Json | Out-Null
            Get-Content -Raw -LiteralPath (Join-Path $Root "dist\release\sbom-rust-metadata.json") |
                ConvertFrom-Json | Out-Null
            Pass "Release metadata is valid JSON."
        }
        catch {
            Block "Release metadata contains invalid JSON: $($_.Exception.Message)"
        }
    }

    if ($Public -and (Test-Path -LiteralPath $Installer)) {
        $Signature = Get-AuthenticodeSignature -LiteralPath $Installer
        if ($Signature.Status -eq "Valid") {
            Pass "Windows installer has a valid Authenticode signature."
        }
        else {
            Block "Windows installer signature is $($Signature.Status)."
        }
    }
}

if ($Public) {
    $PreviousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $Origin = git -C $Root remote get-url origin 2>$null
    $OriginExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorPreference
    if ($OriginExitCode -ne 0 -or -not $Origin) {
        Block "No canonical origin remote is configured."
    }
    elseif ($Origin -notmatch 'github\.com[:/][^/]+/[^/]+(?:\.git)?$') {
        Block "Origin is not a canonical GitHub repository: $Origin"
    }
    else {
        Pass "Canonical GitHub origin is configured: $Origin"
        $PreviousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        git -C $Root ls-remote --exit-code origin HEAD *> $null
        $RemoteExitCode = $LASTEXITCODE
        $ErrorActionPreference = $PreviousErrorPreference
        if ($RemoteExitCode -eq 0) {
            Pass "Canonical origin is reachable."
        }
        else {
            Block "Canonical origin is not reachable with the current credentials."
        }
    }
}

if ($Failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Release readiness failed with $($Failures.Count) blocker(s)." -ForegroundColor Red
    exit 1
}

$Mode = if ($Public) { "public release" } else { "local candidate" }
Write-Host ""
Write-Host "K-LIB Forge is ready as a $Mode." -ForegroundColor Green
