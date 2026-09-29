@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
echo Building...
"%PY%" -m OpenBlogger.cli build --force
echo.
echo Starting preview server...
"%PY%" -m OpenBlogger.cli serve
echo.
pause
