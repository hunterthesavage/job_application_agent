# Windows Portable Build

This document is for maintainers who want to produce the easier Windows tester package.

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

The Release workflow publishes:

- tag: `windows-portable-latest`
- title: `Windows Portable Latest`
- asset: `JobApplicationAgent-windows-portable.zip`

That is the simplest download path to hand to non-technical testers.
