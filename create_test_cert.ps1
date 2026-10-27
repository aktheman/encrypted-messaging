<#
.SYNOPSIS
    Create a self-signed certificate for code signing testing
.DESCRIPTION
    Generates a self-signed certificate with code signing EKU and exports as PFX.
    This certificate is NOT trusted by default - use only for testing!
.NOTES
    For production, purchase a certificate from a trusted CA (DigiCert, Sectigo, GlobalSign).
#>

param(
    [string]$Subject = "CN=Encrypted Messaging Test",
    [string]$PfxPath = "test-cert.pfx",
    [string]$PfxPassword = "test123",
    [int]$ValidityYears = 1
)

$ErrorActionPreference = "Stop"

Write-Host "Creating self-signed certificate for code signing testing..."
Write-Host "Subject: $Subject"
Write-Host "Output: $PfxPath"
Write-Host ""

# Create self-signed certificate with code signing EKU (1.3.6.1.5.5.7.3.3)
$cert = New-SelfSignedCertificate `
    -Subject $Subject `
    -CertStoreLocation 'Cert:\CurrentUser\My' `
    -KeyExportPolicy Exportable `
    -KeySpec Signature `
    -KeyLength 2048 `
    -HashAlgorithm SHA256 `
    -NotAfter (Get-Date).AddYears($ValidityYears) `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3')

$pwd = ConvertTo-SecureString -String $PfxPassword -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $PfxPath -Password $pwd

Write-Host ""
Write-Host "Certificate created successfully!"
Write-Host "  Thumbprint: $($cert.Thumbprint)"
Write-Host "  Valid until: $($cert.NotAfter)"
Write-Host "  PFX file: $PfxPath"
Write-Host "  Password: $PfxPassword"
Write-Host ""
Write-Host "To sign executables, run:"
Write-Host "  .\sign_executables.ps1 -PfxPath $PfxPath -PfxPassword $PfxPassword"
Write-Host ""
Write-Warning "This is a SELF-SIGNED certificate - NOT trusted by Windows SmartScreen!"
Write-Warning "For production, purchase a certificate from a trusted CA."