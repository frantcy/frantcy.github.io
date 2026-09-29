@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
"%PY%" -m OpenBlogger.cli build --force
echo.
pause
