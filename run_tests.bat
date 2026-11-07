@echo off
REM Runs the automated tests (no game window), then the in-game play-test (opens the window briefly).
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pytest
".venv\Scripts\python.exe" main.py --autotest
pause
