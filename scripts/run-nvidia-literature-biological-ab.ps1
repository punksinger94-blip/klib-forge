param(
    [string]$Model = "minimaxai/minimax-m3",
    [ValidateRange(1, 10)]
    [int]$Repeats = 1,
    [switch]$Crossover,
    [string]$Output
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Run .\scripts\bootstrap.ps1 first."
}

if (-not $Output) {
    $Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $Output = Join-Path $Root "build\experiments\nvidia-literature-biological-ab-$Timestamp.json"
}
$Log = [System.IO.Path]::ChangeExtension($Output, ".log")

function Read-ApiKey([string]$Prompt) {
    $SecureValue = Read-Host $Prompt -AsSecureString
    $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
}

$SetBaseline = -not $env:NVIDIA_BASELINE_API_KEY
$SetKlib = -not $env:NVIDIA_KLIB_API_KEY

try {
    if ($SetBaseline) {
        $env:NVIDIA_BASELINE_API_KEY = Read-ApiKey "NVIDIA baseline API key"
    }
    if ($SetKlib) {
        $env:NVIDIA_KLIB_API_KEY = Read-ApiKey "NVIDIA K-LIB API key"
    }

    $Arguments = @(
        "-m",
        "klib_cli.main",
        "nvidia-literature-ab",
        "--model",
        $Model,
        "--repeats",
        $Repeats,
        "--output",
        $Output
    )
    if ($Crossover) {
        $Arguments += "--crossover"
    }

    & $Python @Arguments *> $Log
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        Get-Content -LiteralPath $Log
        throw (
            "NVIDIA literature biology A/B test failed with exit code " +
            "$ExitCode. See $Log."
        )
    }
    Get-Content -LiteralPath $Log
}
finally {
    if ($SetBaseline) {
        Remove-Item Env:NVIDIA_BASELINE_API_KEY -ErrorAction SilentlyContinue
    }
    if ($SetKlib) {
        Remove-Item Env:NVIDIA_KLIB_API_KEY -ErrorAction SilentlyContinue
    }
}
