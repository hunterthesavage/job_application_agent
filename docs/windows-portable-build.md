# Windows Portable Build

This document is for maintainers who want to produce the easier Windows tester package.

## Known Good Recovery Baseline

The current public Windows release is a recovery baseline taken from the exact zip that was confirmed working on a Windows machine:

- asset: `JobApplicationAgent-windows-portable.zip`
- tag: `windows-portable-latest`
- size: `142,376,536` bytes
- SHA256: `b1058358dfce16c9c58a52ec5c32ae1a08f0caefa1da2633887365901d7ba2a8`

Important:

- this exact known-good package includes `INSTALL JAA.bat`
- it does not include `STOP JAA.bat`
- it does not include the later in-app shutdown experiment

Until a replacement package is verified end to end, treat this asset as the Windows fallback baseline and keep new packaging work off `main`.

## What it creates

The portable build packages:

- the app source
- an embedded Windows Python runtime
- Python dependencies already installed into the package
- a double-click launcher batch file

That means testers can:

1. unzip the package
2. open the folder
3. double-click `INSTALL JAA.bat`
4. use `STOP JAA.bat` later if you want to stop the local app server outside the UI

No separate Python install or local virtual environment is required.

## Build locally

Run this on Windows with PowerShell and a normal builder Python available:

```powershell
.\scripts\build_windows_portable.ps1
```

Output:

- package folder: `dist/windows-portable/JobApplicationAgent`
- zip file: `dist/windows-portable/JobApplicationAgent-windows-portable.zip`

## How it works

The script:

1. downloads the official embedded Python zip from python.org
2. expands it into the package
3. installs `requirements.txt` into the embedded runtime's `Lib/site-packages`
4. copies the app source into an `app/` folder
5. writes a batch launcher that starts Streamlit with the bundled Python
6. zips the finished package for sharing

## Recommended tester flow

For friend testers, share only the final portable zip and ask them to:

1. extract it
2. open the extracted folder
3. double-click `INSTALL JAA.bat`
4. use `STOP JAA.bat` later if needed

## GitHub workflow

The repo includes a manual GitHub Actions workflow at:

- `.github/workflows/windows-portable.yml`
- `.github/workflows/windows-portable-release.yml`

Use `windows-portable.yml` when you want a maintainer-only Actions artifact build.

Use `windows-portable-release.yml` when you want a friend-tester-friendly GitHub Release download.

The Actions artifact from `windows-portable.yml` is uploaded as the unpacked `JobApplicationAgent` folder so maintainers can:

1. download the artifact zip from Actions
2. extract it once
3. open the `JobApplicationAgent` folder
4. double-click `INSTALL JAA.bat`
5. use `STOP JAA.bat` later if needed

The Release workflow publishes:

- tag: `windows-portable-latest`
- title: `Windows Portable Latest`
- asset: `JobApplicationAgent-windows-portable.zip`

That is the simplest download path to hand to non-technical testers. Future experiments should happen on `codex/windows-packaging-lab` and only replace the release asset after a full Windows retest passes.
