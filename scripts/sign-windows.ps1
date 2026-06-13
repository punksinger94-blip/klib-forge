param(
    [Parameter(Mandatory)]
    [string]$Path,
    [string]$CertificatePath = $env:WINDOWS_CERTIFICATE_PATH,
    [string]$CertificatePassword = $env:WINDOWS_CERTIFICATE_PASSWORD,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Path)) {
    throw "File not found: $Path"
}
if (-not $CertificatePath -or -not (Test-Path -LiteralPath $CertificatePath)) {
    throw "Set WINDOWS_CERTIFICATE_PATH to a trusted code-signing PFX."
}

$SignTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $SignTool) {
    $SignTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" `
        -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
}
if (-not $SignTool) {
    throw "signtool.exe was not found. Install the Windows SDK."
}
$SignToolPath = if ($SignTool.Source) { $SignTool.Source } else { $SignTool.FullName }

& $SignToolPath sign /fd SHA256 /td SHA256 /tr $TimestampUrl `
    /f $CertificatePath /p $CertificatePassword $Path
if ($LASTEXITCODE -ne 0) {
    throw "Windows signing failed with exit code $LASTEXITCODE."
}

$Signature = Get-AuthenticodeSignature -LiteralPath $Path
if ($Signature.Status -ne "Valid") {
    throw "Signature verification failed: $($Signature.Status)"
}
Write-Host "Signed and timestamped: $Path"
