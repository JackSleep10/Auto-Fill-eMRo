@echo off
chcp 65001 >nul
title Thai Lion Air - GSE Work Order (Cloudflare Online)
cd /d "D:\Project dashboard"

:: Kill any previous stray processes
taskkill /f /im cloudflared.exe >nul 2>&1
set "OLDPID="
if exist "data\web_app.pid" set /p OLDPID=<"data\web_app.pid"
if defined OLDPID taskkill /f /pid %OLDPID% >nul 2>&1
del "data\web_app.pid" >nul 2>&1

:: Start Flask Web Server silently in background
start /b python web_app.py >nul 2>&1

:: Delete old log and start Cloudflare Tunnel silently in background
del "data\cloudflare.log" >nul 2>&1
start /b "" "cloudflared.exe" tunnel --url http://127.0.0.1:8000 --logfile "data\cloudflare.log"

set "CF_URL=https://mia-reproduced-dress-culture.trycloudflare.com"

:: Wait a few seconds for tunnel to connect and extract URL
for /l %%i in (1,1,6) do (
    timeout /t 1 /nobreak >nul
    if exist "data\cloudflare.log" (
        for /f "delims=" %%u in ('python -c "import re; m=re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', open('data/cloudflare.log', encoding='utf-8', errors='ignore').read()); print(m.group(0) if m else '')"') do (
            if not "%%u"=="" set "CF_URL=%%u"
        )
    )
)

cls
echo ================================================================
echo   THAI LION AIR - GSE WORK ORDER CREATOR
echo ================================================================
echo.
echo   [Online URL]  : %CF_URL%
echo   [Local URL]   : http://localhost:8000
echo.
echo   Status: Online and Ready!
echo.
echo   Keep this single window open while using the system.
echo   To stop the server: Close this window or press any key.
echo ================================================================
echo.

start "" "http://localhost:8000"

pause >nul

echo Stopping server...
taskkill /f /im cloudflared.exe >nul 2>&1
set "OLDPID="
if exist "data\web_app.pid" set /p OLDPID=<"data\web_app.pid"
if defined OLDPID taskkill /f /pid %OLDPID% >nul 2>&1
del "data\web_app.pid" >nul 2>&1
