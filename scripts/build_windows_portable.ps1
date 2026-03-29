param(
    [string]$BuildRoot = "dist/windows-portable",
    [string]$PackageName = "JobApplicationAgent",
    [string]$BaselineZipPath = "",
    [string]$BaselineZipUrl = "https://github.com/hunterthesavage/job_application_agent/releases/download/windows-portable-latest/JobApplicationAgent-windows-portable.zip",
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"

function Remove-IfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (Test-Path $Path) {
        Remove-Item $Path -Recurse -Force
    }
}

function Remove-GhostFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    Get-ChildItem -Path $Root -Recurse -Force |
        Where-Object { $_.Name -like "._*" } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    Get-ChildItem -Path $Root -Directory -Force |
        Where-Object { $_.Name -eq "__MACOSX" } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

function Remove-PythonNoise {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonRoot
    )

    $safeRemoveDirs = @(
        "Lib/site-packages/share/jupyter"
    )

    foreach ($relative in $safeRemoveDirs) {
        $target = Join-Path $PythonRoot $relative
        if (Test-Path $target) {
            Remove-Item $target -Recurse -Force
        }
    }

    Get-ChildItem -Path $PythonRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    Get-ChildItem -Path $PythonRoot -Recurse -File -Include "*.pyc", "*.pyo", "*.js.map" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Copy-OverlayFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    $parent = Split-Path -Parent $Destination
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    Copy-Item -Path $Source -Destination $Destination -Force
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $repoRoot $BuildRoot
$packageRoot = Join-Path $distRoot $PackageName
$appRoot = Join-Path $packageRoot "app"
$pythonRoot = Join-Path $packageRoot "python"
$portableZipPath = Join-Path $distRoot "$PackageName-windows-portable.zip"
$downloadZipPath = Join-Path $distRoot "known-good-windows-portable.zip"

Write-Host "==> Cleaning previous portable build"
Remove-IfExists -Path $packageRoot
Remove-IfExists -Path $portableZipPath
Remove-IfExists -Path $downloadZipPath

New-Item -ItemType Directory -Force -Path $distRoot | Out-Null

if ([string]::IsNullOrWhiteSpace($BaselineZipPath)) {
    Write-Host "==> Downloading known-good baseline package"
    Invoke-WebRequest -Uri $BaselineZipUrl -OutFile $downloadZipPath
    $baselineZip = $downloadZipPath
} else {
    $baselineZip = (Resolve-Path $BaselineZipPath).Path
}

Write-Host "==> Expanding known-good baseline"
Expand-Archive -Path $baselineZip -DestinationPath $distRoot -Force

if (-not (Test-Path $packageRoot)) {
    throw "Expected extracted package folder at $packageRoot"
}

Write-Host "==> Removing macOS ghost files"
Remove-GhostFiles -Root $packageRoot

Write-Host "==> Removing safe Python packaging clutter"
if (Test-Path $pythonRoot) {
    Remove-PythonNoise -PythonRoot $pythonRoot
}

Write-Host "==> Overlaying narrow app shutdown updates"
Copy-OverlayFile -Source (Join-Path $repoRoot "app.py") -Destination (Join-Path $appRoot "app.py")
Copy-OverlayFile -Source (Join-Path $repoRoot "config.py") -Destination (Join-Path $appRoot "config.py")
Copy-OverlayFile -Source (Join-Path $repoRoot "services/app_control.py") -Destination (Join-Path $appRoot "services/app_control.py")

$installLauncher = @'
@echo off
setlocal

set "ROOT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%launch_jaa.ps1"
if errorlevel 1 (
    echo.
    echo Job Application Agent failed to launch.
    echo Check app\logs\jaa_stderr.log for details.
    pause
    exit /b 1
)

endlocal
'@
Set-Content -Path (Join-Path $packageRoot "INSTALL JAA.bat") -Value $installLauncher -Encoding ASCII

$launchScript = @'
$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot = Join-Path $rootDir "app"
$pythonExe = Join-Path $rootDir "python\python.exe"
$pidFile = Join-Path $appRoot "data\jaa_server.pid"
$stdoutLog = Join-Path $appRoot "logs\jaa_stdout.log"
$stderrLog = Join-Path $appRoot "logs\jaa_stderr.log"

foreach ($path in @(
    (Join-Path $appRoot "data"),
    (Join-Path $appRoot "backups"),
    (Join-Path $appRoot "logs"),
    (Join-Path $appRoot ".streamlit")
)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

if (-not (Test-Path $pythonExe)) {
    throw "Bundled Python runtime was not found."
}

if (Test-Path $pidFile) {
    $savedPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($savedPid -match '^\d+$') {
        $existing = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
        if ($existing) {
            Start-Process "http://127.0.0.1:8505"
            exit 0
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$arguments = @(
    "-m",
    "streamlit",
    "run",
    "app.py",
    "--server.headless", "true",
    "--server.address", "127.0.0.1",
    "--server.port", "8505",
    "--browser.gatherUsageStats", "false"
)

$proc = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList $arguments `
    -WorkingDirectory $appRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

Set-Content -Path $pidFile -Value $proc.Id -Encoding ASCII

$healthy = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    if ($proc.HasExited) {
        break
    }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8505/_stcore/health" -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
    }
}

if (-not $healthy -and $proc.HasExited) {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    throw "Job Application Agent exited before the local server became healthy."
}

Start-Process "http://127.0.0.1:8505"
'@
Set-Content -Path (Join-Path $packageRoot "launch_jaa.ps1") -Value $launchScript -Encoding ASCII

$stopLauncher = @'
@echo off
setlocal

set "ROOT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%stop_jaa.ps1"
if errorlevel 1 (
    echo.
    echo Job Application Agent was not running.
    pause
    exit /b 1
)

echo Job Application Agent stopped.
timeout /t 2 >nul
endlocal
'@
Set-Content -Path (Join-Path $packageRoot "STOP JAA.bat") -Value $stopLauncher -Encoding ASCII

$stopScript = @'
$ErrorActionPreference = "Stop"

$port = 8505
$pids = @()

try {
    $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
        Select-Object -ExpandProperty OwningProcess -Unique
} catch {
    $matches = netstat -ano | Select-String "LISTENING"
    foreach ($line in $matches) {
        $text = [string]$line
        if ($text -match "127\.0\.0\.1:$port\s+\S+\s+LISTENING\s+(\d+)$") {
            $pids += [int]$Matches[1]
        } elseif ($text -match "0\.0\.0\.0:$port\s+\S+\s+LISTENING\s+(\d+)$") {
            $pids += [int]$Matches[1]
        } elseif ($text -match "\[::\]:$port\s+\S+\s+LISTENING\s+(\d+)$") {
            $pids += [int]$Matches[1]
        }
    }
}

$pids = $pids | Where-Object { $_ -and $_ -ne 0 } | Sort-Object -Unique
if (-not $pids -or $pids.Count -eq 0) {
    exit 1
}

$stopped = $false
foreach ($targetPid in $pids) {
    try {
        Stop-Process -Id ([int]$targetPid) -Force -ErrorAction Stop
        $stopped = $true
    } catch {
    }
}

if (-not $stopped) {
    exit 1
}
'@
Set-Content -Path (Join-Path $packageRoot "stop_jaa.ps1") -Value $stopScript -Encoding ASCII

$readmePath = Join-Path $packageRoot "WINDOWS_PORTABLE_README.txt"
if (Test-Path $readmePath) {
    $readme = @'
Job Application Agent - Windows Portable Package

How to use:
1. Extract this folder anywhere you like.
2. Open the extracted folder.
3. Double-click "INSTALL JAA.bat".
4. Your browser should open to http://localhost:8505

Notes:
- This package already includes its own Python runtime.
- You do not need to install Python separately.
- Keep the python and app folders next to the launcher batch files.
- Use "STOP JAA.bat" when you want to fully stop the local app server.
- On first launch, Windows SmartScreen may ask for confirmation because this package is unsigned.
'@
    Set-Content -Path $readmePath -Value $readme -Encoding ASCII
}

if (-not $SkipZip) {
    Write-Host "==> Creating portable zip"
    Compress-Archive -Path $packageRoot -DestinationPath $portableZipPath -Force
}

Write-Host "==> Windows portable package ready"
Write-Host "Baseline zip:  $baselineZip"
Write-Host "Package folder: $packageRoot"
if (-not $SkipZip) {
    Write-Host "Package zip:    $portableZipPath"
}
