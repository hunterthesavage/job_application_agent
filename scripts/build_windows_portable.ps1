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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $repoRoot $BuildRoot
$packageRoot = Join-Path $distRoot $PackageName
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
foreach ($pid in $pids) {
    try {
        Stop-Process -Id ([int]$pid) -Force -ErrorAction Stop
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
