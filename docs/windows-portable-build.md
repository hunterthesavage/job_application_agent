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
4. use `STOP JAA.bat` later if you want to stop the local app server outside the UI

No separate Python install or local virtual environment is required.

## Build locally

Run this on Windows with PowerShell and a normal builder Python available:

```powershell
.\scripts\build_windows_portable.ps1
```

On `codex/windows-packaging-lab`, this build script starts from the exact known-good Windows release zip instead of rebuilding the app from repo source.

Output:

- package folder: `dist/windows-portable/JobApplicationAgent`
- zip file: `dist/windows-portable/JobApplicationAgent-windows-portable.zip`

## How it works

The lab script:

1. downloads or reuses the exact known-good Windows baseline zip
2. expands that working package into the build folder
3. strips macOS `._...` ghost files that confuse Windows testers
4. removes safe non-runtime Python clutter like `__pycache__`, `.pyc`, `.pyo`, `.js.map`, and Jupyter assets
5. overlays only the narrow app shutdown files needed for the in-app `Close Application` button
6. replaces the old foreground launcher with a hidden PowerShell start flow plus `launch_jaa.ps1`
7. adds `STOP JAA.bat` plus `stop_jaa.ps1`
8. rezips the finished package for sharing

## Recommended tester flow

For friend testers, share only the final portable zip and ask them to:

1. extract it
2. open the extracted folder
3. double-click `INSTALL JAA.bat`
4. use `STOP JAA.bat` later if needed

## GitHub workflow

The repo includes a maintainer-only GitHub Actions workflow at:

- `.github/workflows/windows-portable.yml`

Use `windows-portable.yml` when you want an Actions artifact build from the current branch.

The Actions artifact from `windows-portable.yml` is uploaded as the unpacked `JobApplicationAgent` folder so maintainers can:

1. download the artifact zip from Actions
2. extract it once
3. open the `JobApplicationAgent` folder
4. double-click `INSTALL JAA.bat`
5. use `STOP JAA.bat` later if needed

The public lab test download is still kept separate from the known-good fallback on `windows-portable-latest`, but it is refreshed manually from the latest passing Windows smoke artifact instead of through a dedicated release workflow.
