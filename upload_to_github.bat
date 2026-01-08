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
git remote add origin https://github.com/ZxPwdz/gif-forge.git

echo.
echo ========================================
echo    Ready to push to GitHub
echo ========================================
echo.
echo You may be prompted to sign in to GitHub.
echo.
pause

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
    echo If authentication failed, you need a Personal Access Token:
    echo 1. Go to: https://github.com/settings/tokens
    echo 2. Click "Generate new token (classic)"
    echo 3. Give it a name and select "repo" scope
    echo 4. Copy the token and use it as your password
)

echo.
pause
