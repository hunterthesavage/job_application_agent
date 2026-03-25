@echo off
setlocal

cd /d "%~dp0"

if not exist app.py (
    echo This folder does not contain app.py.
    echo Open the extracted project folder that contains app.py, then run this launcher again.
    pause
    exit /b 1
)

if not exist .venv (
    echo Virtual environment not found. Run install_windows.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate the virtual environment.
    pause
    exit /b 1
)

if not exist data mkdir data
if not exist backups mkdir backups
if not exist logs mkdir logs

python -m streamlit run app.py --server.headless true --server.port 8505
if errorlevel 1 (
    echo Streamlit failed to launch. If this is the first run, try install_windows.bat again.
    pause
    exit /b 1
)

endlocal
