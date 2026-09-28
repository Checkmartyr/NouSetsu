param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$BinaryPath
)

$ErrorActionPreference = 'Stop'

$thumbprint = ($env:NOUSETSU_WINDOWS_CERT_THUMBPRINT -replace '\s', '').ToUpperInvariant()
if ([string]::IsNullOrWhiteSpace($thumbprint)) {
    throw 'Set NOUSETSU_WINDOWS_CERT_THUMBPRINT to the thumbprint of a trusted code-signing certificate in Cert:\CurrentUser\My.'
}

$timestampUrl = $env:NOUSETSU_WINDOWS_TIMESTAMP_URL
if ([string]::IsNullOrWhiteSpace($timestampUrl)) {
    throw 'Set NOUSETSU_WINDOWS_TIMESTAMP_URL to the RFC 3161 timestamp URL provided by your certificate issuer.'
}

if (-not (Test-Path -LiteralPath $BinaryPath -PathType Leaf)) {
    throw "Binary to sign does not exist: $BinaryPath"
}

$codeSigningOid = '1.3.6.1.5.5.7.3.3'
$certificate = Get-ChildItem -Path 'Cert:\CurrentUser\My' | Where-Object {
    (($_.Thumbprint -replace '\s', '').ToUpperInvariant() -eq $thumbprint) -and
    $_.HasPrivateKey -and
    ($_.EnhancedKeyUsageList | Where-Object { $_.ObjectId.Value -eq $codeSigningOid })
} | Select-Object -First 1

if (-not $certificate) {
    throw "No code-signing certificate with a private key and thumbprint $thumbprint was found in Cert:\CurrentUser\My."
}

$signTool = $env:TAURI_WINDOWS_SIGNTOOL_PATH
if ([string]::IsNullOrWhiteSpace($signTool)) {
    $signTool = (Get-Command 'signtool.exe' -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $signTool -PathType Leaf)) {
    throw "SignTool was not found at: $signTool"
}

& $signTool sign /sha1 $thumbprint /fd SHA256 /tr $timestampUrl /td SHA256 $BinaryPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $signTool verify /pa /v $BinaryPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
