param(
    [string]$DistRoot = "dist/windows-desktop",
    [string]$AppName = "JobApplicationAgentDesktop",
    [switch]$BuildInstaller
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $repoRoot $DistRoot
$pyInstallerSpec = Join-Path $repoRoot "$AppName.spec"
$buildRoot = Join-Path $repoRoot "build"
$distAppRoot = Join-Path $repoRoot "dist"
$packageDir = Join-Path $distRoot $AppName
$portableZip = Join-Path $distRoot "$AppName-windows.zip"
$installerPath = Join-Path $distRoot "$AppName-setup.exe"
$installerScript = Join-Path $repoRoot "scripts/windows_desktop_installer.iss"
$appVersion = python -c "from config import APP_VERSION; print(APP_VERSION)"

function Remove-IfExists {
    param([string]$Path)
    if (Test-Path $Path) {
        Remove-Item -Path $Path -Recurse -Force
    }
}

Write-Host "==> Cleaning previous Windows desktop build"
Remove-IfExists $buildRoot
Remove-IfExists $distAppRoot
Remove-IfExists $portableZip
Remove-IfExists $installerPath
New-Item -ItemType Directory -Force -Path $distRoot | Out-Null

Write-Host "==> Ensuring PyInstaller is installed"
python -m pip install pyinstaller PySide6 qtpy | Out-Host

Write-Host "==> Building Windows desktop executable"
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name $AppName `
  --collect-all streamlit `
  --collect-all openai `
  --collect-all ddgs `
  --collect-all webview `
  --collect-all qtpy `
  --collect-all PySide6 `
  --add-data "app.py;." `
  --add-data "greenhouse_boards.txt;." `
  --add-data "lever_boards.txt;." `
  --add-data "services;services" `
  --add-data "views;views" `
  --add-data "ui;ui" `
  --add-data "src;src" `
  --add-data "config.py;." `
  desktop_app.py | Out-Host

if (-not (Test-Path (Join-Path $distAppRoot $AppName))) {
    throw "Expected PyInstaller output at dist/$AppName"
}

Move-Item -Path (Join-Path $distAppRoot $AppName) -Destination $packageDir -Force

$readme = @'
Job Application Agent - Windows Desktop Wrapper

How to use:
1. Extract this zip anywhere you like.
2. Open the extracted folder.
3. Double-click JobApplicationAgentDesktop.exe

Notes:
- This package includes its own Python runtime.
- The app opens in its own native window.
- If an external Apply link is opened, it will still use your default browser.
'@
Set-Content -Path (Join-Path $packageDir "WINDOWS_DESKTOP_README.txt") -Value $readme -Encoding ASCII

Write-Host "==> Creating Windows desktop zip"
Compress-Archive -Path $packageDir -DestinationPath $portableZip -Force

if ($BuildInstaller) {
    $iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) {
        throw "Inno Setup was not found at $iscc"
    }

    Write-Host "==> Creating Windows desktop installer"
    & $iscc "/DAppVersion=$appVersion" "/DRepoRoot=$repoRoot" $installerScript | Out-Host

    if (-not (Test-Path $installerPath)) {
        throw "Expected Windows installer at $installerPath"
    }
} else {
    Write-Host "==> Skipping installer build (use -BuildInstaller to produce a one-file setup.exe)"
}

Write-Host "==> Windows desktop package ready"
Write-Host "Package folder: $packageDir"
Write-Host "Package zip:    $portableZip"
if (Test-Path $installerPath) {
    Write-Host "Installer exe:  $installerPath"
}
