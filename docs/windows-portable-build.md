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
3. double-click `Launch Job Application Agent.bat`

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
3. double-click `Launch Job Application Agent.bat`

## GitHub workflow

The repo includes a manual GitHub Actions workflow at:

- `.github/workflows/windows-portable.yml`

Use that workflow when you want GitHub to build the package on a Windows runner and upload the portable zip as an artifact.
