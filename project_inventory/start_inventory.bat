@echo off
chcp 65001 >nul
title eMRO Inventory Search (Port 8001)
cd /d "D:\Project inventory"

echo ========================================================
echo   eMRO Inventory Search - Starting on Port 8001
echo ========================================================
echo.
start "" "http://localhost:8001"
python web_app.py
pause
