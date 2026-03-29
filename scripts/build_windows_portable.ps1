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

[theme]
base = "dark"
'@
Set-Content -Path (Join-Path $appRoot ".streamlit/config.toml") -Value $streamlitConfig -Encoding ASCII

$launcher = @'
@echo off
setlocal

cd /d "%~dp0app"

if not exist data mkdir data
if not exist backups mkdir backups
if not exist logs mkdir logs
if not exist .streamlit mkdir .streamlit

if not exist .streamlit\config.toml (
    (
        echo [client]
        echo toolbarMode = "minimal"
        echo showSidebarNavigation = false
        echo.
        echo [theme]
        echo base = "dark"
    ) > .streamlit\config.toml
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8505'"
"..\python\python.exe" -m streamlit run app.py --server.headless true --server.port 8505
if errorlevel 1 (
    echo.
    echo Job Application Agent failed to launch.
    echo Keep this window open and share the error details with the maintainer.
    pause
    exit /b 1
)

endlocal
'@
Set-Content -Path (Join-Path $packageRoot "Launch Job Application Agent.bat") -Value $launcher -Encoding ASCII

$readme = @'
Job Application Agent - Windows Portable Package

How to use:
1. Extract this folder anywhere you like.
2. Open the extracted folder.
3. Double-click "Launch Job Application Agent.bat".
4. Your browser should open to http://localhost:8505

Notes:
- This package already includes its own Python runtime.
- You do not need to install Python separately.
- Keep the python and app folders next to the launcher batch file.
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
