@echo off
chcp 65001 >nul
title PUSH TO GITHUB - Auto-Fill-eMRo
cd /d "D:\Project dashboard"

echo ========================================================
echo   Pushing Auto-Fill-eMRo to GitHub
echo   Repository: https://github.com/JackSleep10/Auto-Fill-eMRo
echo ========================================================
echo.

git push -u origin main --force

echo.
echo ========================================================
echo   Done! Press any key to close this window.
echo ========================================================
pause >nul
