@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")

echo Build + Push main ... GitHub Actions 会自动构建并发布到 gh-pages
"%PY%" -m OpenBlogger.cli build --force

git add -A
git commit -m "site update [auto]"
git push origin main
echo.
echo Pushed. GitHub Actions deploys in 1-3 minutes.
pause
