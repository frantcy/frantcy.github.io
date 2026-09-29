@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")

echo Building + Deploy to gh-pages...
"%PY%" -m OpenBlogger.cli build --force

rem .nojekyll: 禁止 GitHub Pages 用 Jekyll 二次加工
type nul > "Rendered\.nojekyll"

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
