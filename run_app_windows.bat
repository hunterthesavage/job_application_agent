@echo off
setlocal

cd /d "%~dp0"

if not exist .venv (
    echo Virtual environment not found. Run install_windows.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

if not exist data mkdir data
if not exist backups mkdir backups
if not exist logs mkdir logs

streamlit run app.py

endlocal
