param(
    [string]$PythonVersion = "3.13.12",
    [string]$BuildRoot = "dist/windows-portable",
    [string]$PackageName = "JobApplicationAgent",
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $repoRoot $BuildRoot
$packageRoot = Join-Path $distRoot $PackageName
$pythonRoot = Join-Path $packageRoot "python"
$appRoot = Join-Path $packageRoot "app"
$sitePackages = Join-Path $pythonRoot "Lib/site-packages"
$pythonZipName = "python-$PythonVersion-embed-amd64.zip"
$pythonZipUrl = "https://www.python.org/ftp/python/$PythonVersion/$pythonZipName"
$pythonZipPath = Join-Path $distRoot $pythonZipName
$portableZipPath = Join-Path $distRoot "$PackageName-windows-portable.zip"
$buildPython = Get-Command python -ErrorAction Stop

Write-Host "==> Cleaning previous portable build"
if (Test-Path $packageRoot) {
    Remove-Item $packageRoot -Recurse -Force
}
if (Test-Path $portableZipPath) {
    Remove-Item $portableZipPath -Force
}

New-Item -ItemType Directory -Force -Path $distRoot | Out-Null
New-Item -ItemType Directory -Force -Path $pythonRoot | Out-Null
New-Item -ItemType Directory -Force -Path $appRoot | Out-Null
New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null

Write-Host "==> Downloading embedded Python $PythonVersion"
Invoke-WebRequest -Uri $pythonZipUrl -OutFile $pythonZipPath

Write-Host "==> Extracting embedded Python"
Expand-Archive -Path $pythonZipPath -DestinationPath $pythonRoot -Force

$pthFile = Get-ChildItem -Path $pythonRoot -Filter "python*._pth" | Select-Object -First 1
if (-not $pthFile) {
    throw "Could not find python*._pth in $pythonRoot"
}

$pthLines = @(
    "$($pthFile.BaseName).zip"
    "."
    "Lib\site-packages"
    "..\app"
    "import site"
)
Set-Content -Path $pthFile.FullName -Value $pthLines -Encoding ASCII

Write-Host "==> Installing app dependencies into embedded runtime"
& $buildPython.Source -m pip install --upgrade pip
& $buildPython.Source -m pip install --target $sitePackages -r (Join-Path $repoRoot "requirements.txt")

$copyItems = @(
    "app.py",
    "config.py",
    "requirements.txt",
    "README.md",
    "profile_context.txt",
    "services",
    "src",
    "ui",
    "views"
)

Write-Host "==> Copying app files"
foreach ($item in $copyItems) {
    Copy-Item -Path (Join-Path $repoRoot $item) -Destination $appRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $appRoot "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $appRoot "backups") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $appRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $appRoot ".streamlit") | Out-Null

$streamlitConfig = @'
[client]
toolbarMode = "minimal"
showSidebarNavigation = false

[browser]
gatherUsageStats = false

[theme]
base = "dark"
'@
Set-Content -Path (Join-Path $appRoot ".streamlit/config.toml") -Value $streamlitConfig -Encoding ASCII

$launcherName = "INSTALL JAA.bat"
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
Set-Content -Path (Join-Path $packageRoot $launcherName) -Value $installLauncher -Encoding ASCII

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

$stopScript = @'
$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot = Join-Path $rootDir "app"
$pidFile = Join-Path $appRoot "data\jaa_server.pid"

if (-not (Test-Path $pidFile)) {
    exit 1
}

$savedPid = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
if (-not ($savedPid -match '^\d+$')) {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

$proc = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
if (-not $proc) {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 1
}

Stop-Process -Id ([int]$savedPid) -Force -ErrorAction Stop
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
'@
Set-Content -Path (Join-Path $packageRoot "stop_jaa.ps1") -Value $stopScript -Encoding ASCII

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
Set-Content -Path (Join-Path $packageRoot "WINDOWS_PORTABLE_README.txt") -Value $readme -Encoding ASCII

if (-not $SkipZip) {
    Write-Host "==> Creating portable zip"
    Compress-Archive -Path $packageRoot -DestinationPath $portableZipPath -Force
}

Write-Host "==> Windows portable package ready"
Write-Host "Package folder: $packageRoot"
if (-not $SkipZip) {
    Write-Host "Package zip:    $portableZipPath"
}
