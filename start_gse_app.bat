@echo off
chcp 65001 >nul
cd /d "D:\Project dashboard"

echo ======================================================
echo    Lion Air - GSE Work Order Automation Web App
echo ======================================================
echo.
echo Starting GSE W/O Web Server on http://localhost:8000 ...
echo Opening web browser...
start http://localhost:8000
python web_app.py
pause
