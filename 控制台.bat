@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal enabledelayedexpansion
set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")

:menu
cls
echo ==========================================
echo   OpenBlogger Control Panel
echo ==========================================
echo.
echo   [1] Write     New diary for today
echo   [2] Config    Open site.json
echo   [3] Preview   Build + Server + Browser
echo   [4] Build     Render only
echo   [5] PushSrc   Push main branch
echo   [6] Deploy    Push main (Actions 自动部署)
echo   [7] PushAll   Build + Push main (推荐)
echo   [8] Folder    Open Raw folder
echo   [9] Exit
echo.
set "opt="
set /p "opt=Select [1-9]: "

if "%opt%"=="1" goto write
if "%opt%"=="2" goto config
if "%opt%"=="3" goto serve
if "%opt%"=="4" goto build
if "%opt%"=="5" goto pushmain
if "%opt%"=="6" goto deploy
if "%opt%"=="7" goto pushall
if "%opt%"=="8" goto folder
if "%opt%"=="9" goto exit
goto menu

:write
"%PY%" new_post.py
echo.
pause
goto menu

:folder
start "" "Raw"
goto menu

:config
start "" "site.json"
goto menu

:build
echo.
echo Building...
"%PY%" -m OpenBlogger.cli build --force
echo.
echo Build done.
pause
goto menu

:serve
echo.
echo Building + preview...
"%PY%" -m OpenBlogger.cli build --force
start "" http://localhost:8080
"%PY%" -m OpenBlogger.cli serve
goto menu

:pushmain
echo.
set "msg=update"
set /p "msg=Commit message: "
git add -A
git commit -m "!msg!"
git push origin main
echo.
echo Push done.
pause
goto menu

:deploy
echo.
echo Build + Push main ... GitHub Actions 会自动部署
"%PY%" -m OpenBlogger.cli build --force
git add -A
git commit -m "site update [auto]"
git push origin main
echo.
echo Pushed. GitHub Actions will deploy in 1-3 minutes.
pause
goto menu

:pushall
echo.
set "msg=update"
set /p "msg=Commit message: "
"%PY%" -m OpenBlogger.cli build --force
git add -A
git commit -m "!msg!"
git push origin main
echo.
echo All done. GitHub Actions builds and deploys in 1-3 minutes.
pause
goto menu

:exit
echo Bye!
timeout /t 1 >nul
