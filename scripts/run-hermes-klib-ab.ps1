param(
    [string]$Output,
    [string]$LibraryId = "biology-core-reference"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $Output) {
    $Output = Join-Path $Root "build\experiments\hermes-klib-ab-$Timestamp.json"
}

function Invoke-HermesPrompt {
    param([Parameter(Mandatory)][string]$Prompt)

    $result = & hermes -z $Prompt 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($result | Out-String).Trim()
    if ($exitCode -ne 0) {
        throw "Hermes prompt failed with exit code ${exitCode}: $text"
    }
    return $text
}

function Score-Output {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string[]]$Checks
    )

    $passed = 0
    foreach ($check in $Checks) {
        if ($Text.ToLowerInvariant().Contains($check.ToLowerInvariant())) {
            $passed += 1
        }
    }
    return [math]::Round($passed / [double]$Checks.Count, 2)
}

$checks = @("7.5", "minute 11", "34.2", "2.10", "10-aster-9-internal-assay.md")

$mcpTest = (& hermes mcp test klib_forge 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Hermes MCP test failed: $mcpTest"
}

$baselinePrompt = @"
Without using tools or K-LIB, answer: In the fictional Aster-9 internal assay,
what are the primer ratio, readout minute, and abort thresholds? If unknown,
say unknown.
"@

$klibPrompt = @"
Use the klib_forge K-LIB tools to search $LibraryId, then answer: In the
fictional Aster-9 internal assay, what are the primer ratio, readout minute,
and abort thresholds? Cite the source title.
"@

$baselineOutput = Invoke-HermesPrompt -Prompt $baselinePrompt
$klibOutput = Invoke-HermesPrompt -Prompt $klibPrompt
$baselineScore = Score-Output -Text $baselineOutput -Checks $checks
$klibScore = Score-Output -Text $klibOutput -Checks $checks

$report = [ordered]@{
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    benchmark = "Hermes Agent K-LIB MCP A/B"
    library_id = $LibraryId
    checks = $checks
    mcp_test = $mcpTest
    baseline = [ordered]@{
        label = "hermes_without_k_lib_tools"
        score = $baselineScore
        output = $baselineOutput
    }
    klib = [ordered]@{
        label = "hermes_with_klib_forge_mcp"
        score = $klibScore
        output = $klibOutput
    }
    score_delta = [math]::Round($klibScore - $baselineScore, 2)
}

$Output = [System.IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $Output -Encoding UTF8

Write-Host "Without K-LIB: $baselineScore"
Write-Host "With K-LIB: $klibScore"
Write-Host "Delta: $($report.score_delta)"
Write-Host "Report: $Output"
