@echo off
title THAI LION AIR - eMRO Systems (Port 8000 and 8001)
cd /d "D:\Project inventory"

if exist "C:\Python313\python.exe" (
    "C:\Python313\python.exe" run_both.py
) else (
    python run_both.py
)

echo.
echo ========================================================
echo The services have stopped.
echo Press any key to close this window...
echo ========================================================
pause >nul
