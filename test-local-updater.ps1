param(
    [string]$UpdateVersion = '0.4.9'
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if ($UpdateVersion -notmatch '^\d+\.\d+\.\d+$') {
    Write-Host 'Update version must use x.y.z format.' -ForegroundColor Red
    exit 2
}

Write-Host 'Building the base local-updater installer...'
uv run python -m nousetsu.cli.local_updater_build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host 'Install the base installer in your disposable Windows test environment.'
Write-Host 'Installer directory: src-tauri/target/release/bundle/nsis/'
Read-Host 'After installing it and closing the app, press Enter to build the update' | Out-Null

Write-Host "Building local updater version $UpdateVersion..."
uv run python -m nousetsu.cli.local_updater_build --version $UpdateVersion
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$nsisDirectory = Join-Path $PSScriptRoot 'src-tauri\target\release\bundle\nsis'
$installer = Join-Path $nsisDirectory "Nousetsu_${UpdateVersion}_x64-setup.exe"
$signature = "$installer.sig"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf) -or
    -not (Test-Path -LiteralPath $signature -PathType Leaf)) {
    Write-Host "Expected installer and signature were not found for version $UpdateVersion." -ForegroundColor Red
    exit 1
}

$feedDirectory = Join-Path $PSScriptRoot 'update-feed'
New-Item -ItemType Directory -Path $feedDirectory -Force | Out-Null
Copy-Item -LiteralPath $installer -Destination $feedDirectory -Force
Copy-Item -LiteralPath $signature -Destination $feedDirectory -Force

Write-Host 'Copied installer and signature into update-feed/.'
Write-Host "Update latest.json with version $UpdateVersion, the matching signature, and installer URL."
