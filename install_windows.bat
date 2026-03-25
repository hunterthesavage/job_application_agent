@echo off
setlocal

cd /d "%~dp0"

echo ==> Job Application Agent Windows install

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3 is required but was not found.
        echo Install Python from https://www.python.org/downloads/windows/
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

echo ==> Creating virtual environment
%PYTHON_CMD% -m venv .venv
if errorlevel 1 exit /b 1

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

echo ==> Upgrading pip
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

echo ==> Installing requirements
pip install -r requirements.txt
if errorlevel 1 exit /b 1

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

endlocal
