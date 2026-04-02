# Desktop Wrapper Spike

## Goal

Prove that Job Application Agent can launch in a native desktop window without opening the browser and without rewriting the current Streamlit UI.

## First Spike Scope

- Keep the existing Python + Streamlit app
- Start the local server in the background
- Open the app inside a native desktop window via `pywebview`
- Close the local server when the desktop window closes

## Mac Launcher

After installing requirements, launch the spike wrapper with:

```bash
./run_desktop_app.sh
```

Or double-click:

```text
run_desktop_app.command
```

## First macOS Bundle Build

Build the native app bundle with:

```bash
./scripts/build_macos_desktop_app.sh
```

The build now outputs:

```text
dist/Job Application Agent.app
dist/desktop-wrapper-release/JobApplicationAgent-macos-desktop-wrapper-<version>.zip
```

## First Windows Wrapper Build

Build the Windows desktop wrapper package on Windows with:

```powershell
.\scripts\build_windows_desktop.ps1
```

The first pass outputs:

```text
dist/windows-desktop/JobApplicationAgentDesktop
dist/windows-desktop/JobApplicationAgentDesktop-windows.zip
```

## Smoke Test

You can run the wrapper smoke test with:

```bash
.venv/bin/python scripts/run_desktop_wrapper_smoke.py
```

It verifies:

- the desktop launcher starts
- the local app becomes healthy
- the homepage is served
- the wrapper exits cleanly after an auto-close window cycle
- the local server shuts down with the window

## What This Spike Proves

- native app window instead of a browser tab
- hidden local server still works with the existing app
- current close and review flows remain usable in a desktop shell

## What This Spike Does Not Solve Yet

- packaged `.app` or `.exe` delivery
- auto-update behavior
- replacing the Streamlit UI
- native scheduled background execution outside the current app logic

## Next Packaging Follow-Up

If the wrapper feels good, the next step is packaging:

- macOS: `pyinstaller`
- Windows: `pyinstaller`

That packaging step should stay on this branch until we decide the wrapper is stable enough for broader testing.
