@echo off
REM Double-click this file to play Operation Shadow.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The game is not installed yet. Double-click setup.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 (
    echo.
    echo The game closed with an error. Details are in data\logs\game.log
    pause
)
