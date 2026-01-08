@echo off
echo ========================================
echo    GIF Forge - GitHub Upload Script
echo ========================================
echo.

cd /d "%~dp0"

echo Checking for Git...
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed!
    echo Download it from: https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)
echo [OK] Git found
echo.

echo Initializing repository...
git init

echo.
echo Adding files...
git add .

echo.
echo Creating commit...
git commit -m "Initial commit - GIF Forge application"

echo.
echo Setting up remote...
git branch -M main
git remote remove origin >nul 2>nul

set /p TOKEN=Enter your GitHub Personal Access Token:
git remote add origin https://ZxPwdz:%TOKEN%@github.com/ZxPwdz/gif-forge.git

echo.
echo Pushing to GitHub...
git push -u origin main --force

echo.
if %errorlevel% equ 0 (
    echo ========================================
    echo    Upload Complete!
    echo ========================================
    echo.
    echo Your repository: https://github.com/ZxPwdz/gif-forge
) else (
    echo ========================================
    echo    Upload Failed
    echo ========================================
    echo.
    echo Make sure your token has "repo" permissions.
)

echo.
pause
