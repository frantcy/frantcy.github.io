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
echo   [1] Write     Open Raw folder
echo   [2] Config    Open site.json
echo   [3] Preview   Build + Server + Browser
echo   [4] Build     Render only
echo   [5] PushSrc   Push main branch
echo   [6] Deploy    Build + Push gh-pages
echo   [7] PushAll   Push main + gh-pages
echo   [8] Exit
echo.
set "opt="
set /p "opt=Select [1-8]: "

if "%opt%"=="1" goto write
if "%opt%"=="2" goto config
if "%opt%"=="3" goto serve
if "%opt%"=="4" goto build
if "%opt%"=="5" goto pushmain
if "%opt%"=="6" goto deploy
if "%opt%"=="7" goto pushall
if "%opt%"=="8" goto exit
goto menu

:write
start "" "Raw"
echo Raw folder opened.
pause
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
echo Build + Deploy gh-pages...
"%PY%" -m OpenBlogger.cli build --force
git add -f Rendered/
git commit -m "gh-pages deploy [auto]" 2>nul
git subtree split --prefix Rendered -b _ghp_tmp
git push origin _ghp_tmp:gh-pages --force
git branch -D _ghp_tmp 2>nul
git reset --soft HEAD~1 2>nul
git reset HEAD Rendered/ 2>nul
echo.
echo Deploy done.
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
git add -f Rendered/
git commit -m "gh-pages deploy [auto]" 2>nul
git subtree split --prefix Rendered -b _ghp_tmp
git push origin _ghp_tmp:gh-pages --force
git branch -D _ghp_tmp 2>nul
git reset --soft HEAD~1 2>nul
git reset HEAD Rendered/ 2>nul
echo.
echo All done.
pause
goto menu

:exit
echo Bye!
timeout /t 1 >nul
