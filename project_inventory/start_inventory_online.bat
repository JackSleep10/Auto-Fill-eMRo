@echo off
chcp 65001 >nul
title eMRO Inventory Search Online (Port 8001 + Cloudflare Tunnel)
cd /d "D:\Project inventory"

echo ========================================================
echo   eMRO Inventory Search - Starting Server + Tunnel
echo ========================================================
start "Inventory Web Server (8001)" cmd /k "cd /d D:\Project inventory && python web_app.py"
timeout /t 3 /nobreak >nul
start "" "http://localhost:8001"

if exist "cloudflared.exe" (
    echo Starting Cloudflare Tunnel for http://localhost:8001 ...
    cloudflared.exe tunnel --url http://localhost:8001
) else if exist "D:\Project dashboard\cloudflared.exe" (
    echo Starting Cloudflare Tunnel for http://localhost:8001 ...
    "D:\Project dashboard\cloudflared.exe" tunnel --url http://localhost:8001
) else (
    echo cloudflared.exe not found. Running local/LAN mode only.
    pause
)
