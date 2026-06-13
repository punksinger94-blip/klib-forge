param(
    [string]$Owner = "punksinger94-blip",
    [string]$Repository = "klib-forge",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

function Assert-NativeSuccess {
    param([Parameter(Mandatory)][string]$Operation)
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI is required. Install it, then run 'gh auth login'."
}

gh auth status
Assert-NativeSuccess "GitHub authentication check"

$AuthenticatedOwner = (gh api user --jq .login).Trim()
Assert-NativeSuccess "GitHub account lookup"
if ($AuthenticatedOwner -ne $Owner) {
    throw "Authenticated GitHub account is '$AuthenticatedOwner', expected '$Owner'."
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Run .\scripts\bootstrap.ps1 first."
}
$Version = (& $Python -c "from klib_core import __version__; print(__version__)").Trim()
Assert-NativeSuccess "Version lookup"
$Tag = "v$Version"
$RepositoryFullName = "$Owner/$Repository"

$Status = git -C $Root status --porcelain
Assert-NativeSuccess "Git worktree inspection"
if ($Status) {
    throw "Publishing requires a clean Git worktree."
}
$Branch = (git -C $Root branch --show-current).Trim()
Assert-NativeSuccess "Git branch lookup"
if ($Branch -ne "main") {
    throw "Publishing must run from the main branch."
}

$ReleaseDir = Join-Path $Root "dist\release"
$Installer = Join-Path $ReleaseDir "K-LIB Forge_${Version}_x64-setup.exe"
$Artifacts = @(
    (Join-Path $Root "dist\klib_forge-$Version-py3-none-any.whl"),
    (Join-Path $Root "dist\klib_forge-$Version.tar.gz"),
    $Installer,
    (Join-Path $ReleaseDir "SHA256SUMS.txt"),
    (Join-Path $ReleaseDir "sbom-python.cdx.json"),
    (Join-Path $ReleaseDir "sbom-npm.cdx.json"),
    (Join-Path $ReleaseDir "sbom-rust-metadata.json")
)
foreach ($Artifact in $Artifacts) {
    if (-not (Test-Path -LiteralPath $Artifact -PathType Leaf)) {
        throw "Release artifact is missing: $Artifact"
    }
}

$Signature = Get-AuthenticodeSignature -LiteralPath $Installer
if ($Signature.Status -ne "Valid") {
    throw "Refusing publication: installer signature is $($Signature.Status)."
}

$ExistingOrigin = git -C $Root remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0 -or -not $ExistingOrigin) {
    gh repo view $RepositoryFullName --json nameWithOwner *> $null
    if ($LASTEXITCODE -ne 0) {
        $VisibilityFlag = if ($Visibility -eq "public") { "--public" } else { "--private" }
        gh repo create $RepositoryFullName $VisibilityFlag --source $Root --remote origin
        Assert-NativeSuccess "GitHub repository creation"
    }
    else {
        git -C $Root remote add origin "https://github.com/$RepositoryFullName.git"
        Assert-NativeSuccess "GitHub origin configuration"
    }
}
elseif ($ExistingOrigin -notmatch [regex]::Escape($RepositoryFullName)) {
    throw "Origin points to '$ExistingOrigin', expected '$RepositoryFullName'."
}

git -C $Root push -u origin main
Assert-NativeSuccess "Main branch push"

& (Join-Path $Root "scripts\release-doctor.ps1") -Public
Assert-NativeSuccess "Public release readiness doctor"

$ExistingTag = git -C $Root tag --list $Tag
Assert-NativeSuccess "Git tag inspection"
if (-not $ExistingTag) {
    git -C $Root tag -a $Tag -m "K-LIB Forge $Version"
    Assert-NativeSuccess "Release tag creation"
}

git -C $Root push origin $Tag
Assert-NativeSuccess "Release tag push"

$Notes = Join-Path $Root "docs\release-notes-$Version.md"
if (-not (Test-Path -LiteralPath $Notes -PathType Leaf)) {
    throw "Release notes are missing: $Notes"
}
gh release view $Tag --repo $RepositoryFullName *> $null
if ($LASTEXITCODE -eq 0) {
    gh release edit $Tag `
        --repo $RepositoryFullName `
        --title "K-LIB Forge $Version" `
        --notes-file $Notes
    Assert-NativeSuccess "Existing GitHub release update"
    gh release upload $Tag @Artifacts --repo $RepositoryFullName --clobber
    Assert-NativeSuccess "Existing GitHub release asset upload"
}
else {
    gh release create $Tag @Artifacts `
        --repo $RepositoryFullName `
        --title "K-LIB Forge $Version" `
        --notes-file $Notes `
        --verify-tag
    Assert-NativeSuccess "GitHub release publication"
}

$ReleaseUrl = (gh release view $Tag --repo $RepositoryFullName --json url --jq .url).Trim()
Assert-NativeSuccess "Published release lookup"
Write-Host "Published K-LIB Forge ${Version}: $ReleaseUrl"
