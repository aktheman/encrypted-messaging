<#
.SYNOPSIS
    Code signing script for Encrypted Messaging executables
.DESCRIPTION
    Signs the three executables (GUI, TUI, Server) with a code signing certificate
    to avoid Windows SmartScreen warnings.
.NOTES
    Requires a valid code signing certificate (PFX file) from a trusted CA.
    You can get one from: DigiCert, Sectigo, GlobalSign, etc.
    For development, you can create a self-signed certificate but it won't be trusted by default.

    Requires Windows SDK (for signtool.exe).
    Install from: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$PfxPath,

    [Parameter(Mandatory=$true)]
    [string]$PfxPassword,

    [string]$TimestampUrl = "http://timestamp.digicert.com",

    [string]$ProjectDir = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

Write-Host "============================================"
Write-Host "Encrypted Messaging - Code Signing"
Write-Host "============================================"
Write-Host ""

# Find signtool (comes with Windows SDK)
$SignToolPath = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
if (-not (Test-Path $SignToolPath)) {
    # Try alternative locations
    $SignToolPath = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter "signtool.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}

if (-not $SignToolPath -or -not (Test-Path $SignToolPath)) {
    Write-Error "signtool.exe not found."
    Write-Host ""
    Write-Host "Please install Windows SDK to get signtool.exe:"
    Write-Host "  https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/"
    Write-Host ""
    Write-Host "Or specify the path manually by editing this script."
    exit 1
}

Write-Host "Using signtool: $SignToolPath"
Write-Host ""

$Exes = @(
    "$ProjectDir\dist\encrypted-messaging-gui\encrypted-messaging-gui.exe",
    "$ProjectDir\dist\encrypted-messaging-tui\encrypted-messaging-tui.exe",
    "$ProjectDir\dist\encrypted-messaging-server\encrypted-messaging-server.exe"
)

$AllFound = $true
foreach ($Exe in $Exes) {
    if (-not (Test-Path $Exe)) {
        Write-Warning "Executable not found: $Exe"
        $AllFound = $false
    }
}

if (-not $AllFound) {
    Write-Error "Some executables not found. Please build first."
    exit 1
}

Write-Host "Signing $($Exes.Count) executables..."
Write-Host ""

$SuccessCount = 0
foreach ($Exe in $Exes) {
    Write-Host "Signing: $Exe"

    $Args = @(
        "sign",
        "/f", $PfxPath,
        "/p", $PfxPassword,
        "/tr", $TimestampUrl,
        "/td", "sha256",
        "/fd", "sha256",
        "/v",
        $Exe
    )

    $Result = & $SignToolPath @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to sign $Exe"
        Write-Host ""
        Write-Host "Common issues:"
        Write-Host "  - Certificate password incorrect"
        Write-Host "  - Certificate not valid for code signing (needs EKU 1.3.6.1.5.5.7.3.3)"
        Write-Host "  - Timestamp server unreachable (try without /tr for testing)"
        exit 1
    }

    Write-Host "Successfully signed: $Exe"
    $SuccessCount++
}

Write-Host ""
Write-Host "============================================"
Write-Host "All $SuccessCount executables signed successfully!"
Write-Host "============================================"
Write-Host ""
Write-Host "Verify signatures with:"
Write-Host "  $SignToolPath verify /v /pa <exe-path>"
Write-Host ""
Write-Host "Note: Self-signed certificates will still show SmartScreen warnings."
Write-Host "For production, use a certificate from a trusted CA (DigiCert, Sectigo, GlobalSign)."