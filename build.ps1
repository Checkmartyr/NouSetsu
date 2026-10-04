<#
.SYNOPSIS
    Build script for NouSetsu (Vite Frontend, Python Sidecar, and Tauri Desktop App).

.DESCRIPTION
    Automates building NouSetsu components across Node.js/Vite, Python/PyInstaller,
    and Rust/Tauri. Supports granular targets, fast-path caching, pre-build testing,
    and release packaging.

.PARAMETER Target
    Build target:
    - 'All' / 'Desktop' / 'Installer': Full desktop application with installer.
    - 'Frontend': Builds only the Vite/React web application (web/dist).
    - 'Backend' / 'Sidecar': Builds only the PyInstaller self-contained backend sidecar.

.PARAMETER Configuration
    Build configuration: 'Release' (default, optimized) or 'Debug' (unoptimized, with debug symbols).

.PARAMETER SkipSidecar
    Skips rebuilding the Python backend sidecar if it is already present in src-tauri/binaries.

.PARAMETER SkipFrontend
    Skips rebuilding the Vite frontend if web/dist is already present.

.PARAMETER NoBundle
    Builds the desktop binary without generating the NSIS/MSI installer package.

.PARAMETER RunTests
    Executes Python pytest and Rust cargo tests before building.

.PARAMETER InstallDeps
    Syncs Python build dependencies (uv sync --group desktop-build) and runs npm install.

.PARAMETER Clean
    Removes build output directories (web/dist, src-tauri/target/backend-*, src-tauri/binaries/nousetsu-backend) before building.

.PARAMETER Bundles
    Specifies installer bundle formats for Tauri (e.g. 'nsis' or 'msi'). Default: 'nsis'.

.EXAMPLE
    .\build.ps1
    Builds the full release desktop application and installer.

.EXAMPLE
    .\build.ps1 -Target Frontend
    Fast-builds only the web frontend in ~4 seconds.

.EXAMPLE
    .\build.ps1 -SkipSidecar
    Re-bundles the desktop application using the existing pre-built backend sidecar.

.EXAMPLE
    .\build.ps1 -Clean -RunTests
    Performs a clean build preceded by automated tests.
#>

[CmdletBinding()]
param(
    [ValidateSet('All', 'Desktop', 'Frontend', 'Backend', 'Sidecar', 'Installer')]
    [string]$Target = 'All',

    [ValidateSet('Release', 'Debug')]
    [string]$Configuration = 'Release',

    [switch]$SkipSidecar,
    [switch]$SkipFrontend,
    [switch]$NoBundle,
    [switch]$RunTests,
    [switch]$InstallDeps,
    [switch]$Clean,
    [string]$Bundles = 'nsis'
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$buildStartTime = [System.Diagnostics.Stopwatch]::StartNew()

# -----------------------------------------------------------------------------
# Color & Formatting Helpers
# -----------------------------------------------------------------------------
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor DarkYellow
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor DarkYellow
}

function Write-Step {
    param([string]$Step, [string]$Text)
    Write-Host ""
    Write-Host "[$Step] $Text" -ForegroundColor Green
}

function Write-Info {
    param([string]$Text)
    Write-Host "       $Text" -ForegroundColor Gray
}

function Write-Success {
    param([string]$Text)
    Write-Host "  [OK] $Text" -ForegroundColor DarkGreen
}

function Write-Warn {
    param([string]$Text)
    Write-Host " [WARN] $Text" -ForegroundColor Yellow
}

function Write-Failure {
    param([string]$Text)
    Write-Host "[FAIL] $Text" -ForegroundColor Red
}

function Format-FileSize {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

# -----------------------------------------------------------------------------
# Directory & Path Discovery
# -----------------------------------------------------------------------------
$RootDir = $PSScriptRoot
$WebDir = Join-Path $RootDir "web"
$FrontendDist = Join-Path $WebDir "dist"
$TauriDir = Join-Path $RootDir "src-tauri"
$PyprojectPath = Join-Path $RootDir "pyproject.toml"
$CargoTomlPath = Join-Path $TauriDir "Cargo.toml"
$TauriConfPath = Join-Path $TauriDir "tauri.conf.json"
$BackendBinaryDir = Join-Path $TauriDir "binaries\nousetsu-backend"
$BackendBinaryExe = Join-Path $BackendBinaryDir "nousetsu-backend.exe"

Write-Header "NouSetsu Build Orchestrator (=^･ω･^=)★"
Write-Info "Working Directory : $RootDir"
Write-Info "Target            : $Target"
Write-Info "Configuration     : $Configuration"
Write-Info "Skip Sidecar      : $(if ($SkipSidecar) {'Yes'} else {'No'})"
Write-Info "Skip Frontend     : $(if ($SkipFrontend) {'Yes'} else {'No'})"
Write-Info "No Bundle         : $(if ($NoBundle) {'Yes'} else {'No'})"

# -----------------------------------------------------------------------------
# 1. Prerequisite Tool Verification
# -----------------------------------------------------------------------------
Write-Step "1/6" "Verifying prerequisite build tools..."

$requiredTools = @('node', 'npm', 'uv', 'cargo')
foreach ($tool in $requiredTools) {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Failure "Missing required tool: '$tool' was not found in PATH."
        throw "Please install '$tool' before running the build script."
    }
    Write-Info "${tool}: $($cmd.Source)"
}

# Detect Tauri CLI
$hasCargoTauri = (Get-Command "cargo-tauri.exe" -ErrorAction SilentlyContinue) -or (
    & cargo tauri --version 2>$null
)
if ($hasCargoTauri) {
    Write-Info "tauri-cli: cargo tauri (native)"
} else {
    Write-Info "tauri-cli: npx fallback (@tauri-apps/cli)"
}
Write-Success "All prerequisite tools are installed and ready."

# -----------------------------------------------------------------------------
# 2. Version Synchronization Audit
# -----------------------------------------------------------------------------
Write-Step "2/6" "Auditing version consistency across project configurations..."

$tauriVersion = $null
if (Test-Path -LiteralPath $TauriConfPath) {
    $tauriConf = Get-Content -LiteralPath $TauriConfPath -Raw -Encoding utf8 | ConvertFrom-Json
    $tauriVersion = $tauriConf.version
}

$cargoVersion = $null
if (Test-Path -LiteralPath $CargoTomlPath) {
    $cargoMatch = Select-String -Path $CargoTomlPath -Pattern '^version\s*=\s*"([^"]+)"'
    if ($cargoMatch) { $cargoVersion = $cargoMatch.Matches[0].Groups[1].Value }
}

$pyVersion = $null
if (Test-Path -LiteralPath $PyprojectPath) {
    $pyMatch = Select-String -Path $PyprojectPath -Pattern '^version\s*=\s*"([^"]+)"'
    if ($pyMatch) { $pyVersion = $pyMatch.Matches[0].Groups[1].Value }
}

Write-Info "tauri.conf.json : $tauriVersion"
Write-Info "Cargo.toml      : $cargoVersion"
Write-Info "pyproject.toml  : $pyVersion"

if ($tauriVersion -and $cargoVersion -and $pyVersion) {
    if ($tauriVersion -ne $cargoVersion -or $tauriVersion -ne $pyVersion) {
        Write-Warn "Version mismatch detected between configurations ($tauriVersion vs $cargoVersion vs $pyVersion)."
    } else {
        Write-Success "Version alignment verified: v$tauriVersion across all files."
    }
}

# -----------------------------------------------------------------------------
# 3. Clean & Install Dependencies (Optional)
# -----------------------------------------------------------------------------
if ($Clean) {
    Write-Step "3/6" "Cleaning previous build artifacts..."
    $pathsToClean = @(
        $FrontendDist,
        (Join-Path $TauriDir "target\backend-dist"),
        (Join-Path $TauriDir "target\backend-work"),
        (Join-Path $TauriDir "binaries\nousetsu-backend")
    )
    foreach ($p in $pathsToClean) {
        if (Test-Path -LiteralPath $p) {
            Write-Info "Removing $p"
            Remove-Item -LiteralPath $p -Recurse -Force
        }
    }
    Write-Success "Clean completed."
}

if ($InstallDeps) {
    Write-Step "3/6" "Syncing Python and Node dependencies..."
    Write-Info "Syncing Python desktop-build dependencies via uv..."
    & uv sync --group desktop-build
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed with exit code $LASTEXITCODE" }

    Write-Info "Installing frontend dependencies via npm..."
    & npm --prefix $WebDir install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed with exit code $LASTEXITCODE" }

    Write-Success "Dependencies synced."
}

# -----------------------------------------------------------------------------
# 4. Automated Tests Gate (Optional)
# -----------------------------------------------------------------------------
if ($RunTests) {
    Write-Step "4/6" "Running automated quality assurance tests..."
    Write-Info "Running Python pytest suite..."
    & uv run --no-sync python -m pytest tests/
    if ($LASTEXITCODE -ne 0) { throw "pytest suite failed with exit code $LASTEXITCODE" }

    Write-Info "Running Rust unit tests in src-tauri..."
    Push-Location $TauriDir
    try {
        & cargo test
        if ($LASTEXITCODE -ne 0) { throw "cargo test failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
    Write-Success "All tests passed cleanly."
}

# -----------------------------------------------------------------------------
# 5. Build Phases
# -----------------------------------------------------------------------------
$needFrontend = ($Target -in @('All', 'Desktop', 'Frontend', 'Installer')) -and (-not $SkipFrontend)
$needBackend  = ($Target -in @('All', 'Desktop', 'Backend', 'Sidecar', 'Installer')) -and (-not $SkipSidecar)
$needDesktop  = $Target -in @('All', 'Desktop', 'Installer')

# Phase A: Frontend Build
if ($needFrontend) {
    Write-Step "5/6" "Building Vite + React Frontend..."
    $feStart = [System.Diagnostics.Stopwatch]::StartNew()
    & npm --prefix $WebDir run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE" }
    $feStart.Stop()
    Write-Success ("Built frontend in {0:N2}s -> {1}" -f $feStart.Elapsed.TotalSeconds, $FrontendDist)
} elseif ($SkipFrontend) {
    Write-Info "Skipping frontend build (-SkipFrontend specified)."
}

# Phase B: Python Backend Sidecar Build
if ($needBackend) {
    Write-Step "5/6" "Building Python Backend Sidecar (PyInstaller)..."
    $beStart = [System.Diagnostics.Stopwatch]::StartNew()
    & uv run --no-sync python (Join-Path $TauriDir "build_sidecar.py")
    if ($LASTEXITCODE -ne 0) { throw "Backend sidecar build failed with exit code $LASTEXITCODE" }
    $beStart.Stop()
    Write-Success ("Built backend sidecar in {0:N2}s -> {1}" -f $beStart.Elapsed.TotalSeconds, $BackendBinaryExe)
} elseif ($SkipSidecar) {
    Write-Info "Skipping backend sidecar build (-SkipSidecar specified)."
    if (-not (Test-Path -LiteralPath $BackendBinaryExe)) {
        Write-Warn "Pre-built backend sidecar not found at: $BackendBinaryExe"
        Write-Warn "Desktop build may fail if sidecar binaries are missing."
    }
}

# Phase C: Tauri Desktop Application & Installer Packaging
if ($needDesktop) {
    Write-Step "6/6" "Compiling and bundling Tauri Desktop App..."
    $tauriStart = [System.Diagnostics.Stopwatch]::StartNew()

    $tauriArgs = @("build")
    if ($Configuration -eq 'Debug') {
        $tauriArgs += "--debug"
    }
    if ($NoBundle) {
        $tauriArgs += "--no-bundle"
    } elseif ($Bundles) {
        $tauriArgs += @("--bundles", $Bundles)
    }

    # If sidecar or frontend was skipped, override beforeBuildCommand so Tauri doesn't re-run it
    if ($SkipSidecar -or $SkipFrontend) {
        $customConfig = '{"build":{"beforeBuildCommand":""}}'
        $tauriArgs += @("-c", $customConfig)
    }

    Push-Location $TauriDir
    try {
        if ($hasCargoTauri) {
            Write-Info "Executing: cargo tauri $($tauriArgs -join ' ')"
            & cargo tauri @tauriArgs
        } else {
            Write-Info "Executing: npx @tauri-apps/cli $($tauriArgs -join ' ')"
            & npx --prefix $WebDir @tauri-apps/cli @tauriArgs
        }
        if ($LASTEXITCODE -ne 0) { throw "Tauri desktop build failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }

    $tauriStart.Stop()
    Write-Success ("Desktop build completed in {0:N2}s." -f $tauriStart.Elapsed.TotalSeconds)
}

# -----------------------------------------------------------------------------
# Summary Report
# -----------------------------------------------------------------------------
$buildStartTime.Stop()
Write-Header "Build Completed Successfully! (=^･ω･^=)★ ♪"
Write-Host ("Total Execution Time: {0:N2} seconds" -f $buildStartTime.Elapsed.TotalSeconds) -ForegroundColor Cyan
Write-Host ""
Write-Host "Generated Artifacts:" -ForegroundColor White

if (Test-Path -LiteralPath $FrontendDist) {
    $feItemCount = (Get-ChildItem -Recurse -File $FrontendDist | Measure-Object).Count
    Write-Host "  • Web Frontend       : $FrontendDist ($feItemCount files)" -ForegroundColor Gray
}

if (Test-Path -LiteralPath $BackendBinaryExe) {
    $beSize = (Get-Item -LiteralPath $BackendBinaryExe).Length
    Write-Host "  • Backend Sidecar    : $BackendBinaryExe ($(Format-FileSize $beSize))" -ForegroundColor Gray
}

$targetProfile = if ($Configuration -eq 'Debug') { 'debug' } else { 'release' }
$desktopExe = Join-Path $TauriDir "target\$targetProfile\nousetsu-desktop.exe"
if (-not (Test-Path -LiteralPath $desktopExe)) {
    $desktopExe = Join-Path $TauriDir "target\$targetProfile\nousetsu.exe"
}
if (Test-Path -LiteralPath $desktopExe) {
    $dtSize = (Get-Item -LiteralPath $desktopExe).Length
    Write-Host "  • Desktop Executable : $desktopExe ($(Format-FileSize $dtSize))" -ForegroundColor Green
}

$nsisDir = Join-Path $TauriDir "target\$targetProfile\bundle\nsis"
if (Test-Path -LiteralPath $nsisDir) {
    $installers = Get-ChildItem -Path $nsisDir -Filter "*.exe"
    foreach ($inst in $installers) {
        Write-Host "  • Windows Installer  : $($inst.FullName) ($(Format-FileSize $inst.Length))" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "All requested components are built and ready, Master! Nya~!" -ForegroundColor Magenta
