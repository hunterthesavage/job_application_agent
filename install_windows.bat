@echo off
setlocal

cd /d "%~dp0"

echo ==> Job Application Agent Windows install

if not exist app.py (
    echo This folder does not contain app.py.
    echo Open the extracted project folder that contains app.py and requirements.txt, then run install_windows.bat again.
    pause
    exit /b 1
)

if not exist requirements.txt (
    echo requirements.txt was not found in this folder.
    echo Open the extracted project folder that contains app.py and requirements.txt, then run install_windows.bat again.
    pause
    exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3 is required but was not found.
        echo Install Python x64 from https://www.python.org/downloads/windows/
        echo For now, Python ARM64 is not supported by this app's Windows setup flow.
        echo During install, enable "Add Python to PATH".
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

echo ==> Creating virtual environment
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
    echo Failed to create the virtual environment.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate the virtual environment.
    pause
    exit /b 1
)

echo ==> Upgrading pip
python -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed while upgrading pip.
    pause
    exit /b 1
)

echo ==> Installing requirements
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed while installing requirements.
    pause
    exit /b 1
)

echo ==> Preparing local folders
if not exist data mkdir data
if not exist backups mkdir backups
if not exist logs mkdir logs
if not exist .streamlit mkdir .streamlit
if not exist data\.gitkeep type nul > data\.gitkeep
if not exist backups\.gitkeep type nul > backups\.gitkeep

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

echo.
echo Install complete.
echo Start the app with: run_app_windows.bat
pause

endlocal
