@echo off
REM One-time setup: creates the .venv folder and installs Panda3D, numpy and pytest.
cd /d "%~dp0"
REM A leftover PostgreSQL setting on this PC breaks pip downloads. Clear it for this window only.
set CURL_CA_BUNDLE=
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || (echo Python 3 is not installed or not on PATH. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo Setup finished. Double-click run_game.bat to play.
pause
