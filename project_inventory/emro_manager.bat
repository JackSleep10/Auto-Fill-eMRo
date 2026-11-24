@echo off
chcp 65001 >nul
title THAI LION AIR - eMRO Systems Control
setlocal EnableDelayedExpansion

:MENU
cls
echo =====================================================================
echo           THAI LION AIR - eMRO SYSTEMS CONTROL CENTER
echo =====================================================================
echo.
powershell.exe -NoProfile -Command "& {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress
    if (-not $ip) { $ip = '127.0.0.1' }

    $p8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    $p8001 = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue

    Write-Host '  [สถานะบริการ]' -ForegroundColor Cyan
    if ($p8000) {
        $pid8000 = $p8000.OwningProcess[0]
        Write-Host ('   [RUNNING] 1. GSE Work Order Creator  : Port 8000 (PID: ' + $pid8000 + ')') -ForegroundColor Green
        Write-Host ('             URL: http://localhost:8000 หรือ http://' + $ip + ':8000') -ForegroundColor DarkGray
    } else {
        Write-Host '   [STOPPED] 1. GSE Work Order Creator  : Port 8000 (ไม่ได้รัน)' -ForegroundColor Red
    }

    if ($p8001) {
        $pid8001 = $p8001.OwningProcess[0]
        Write-Host ('   [RUNNING] 2. Inventory Search (DM01) : Port 8001 (PID: ' + $pid8001 + ')') -ForegroundColor Green
        Write-Host ('             URL: http://localhost:8001 หรือ http://' + $ip + ':8001') -ForegroundColor DarkGray
    } else {
        Write-Host '   [STOPPED] 2. Inventory Search (DM01) : Port 8001 (ไม่ได้รัน)' -ForegroundColor Red
    }
}"

echo.
echo =====================================================================
echo   [1] ตรวจสอบสถานะอีกครั้ง (Refresh Status)
echo   [2] สั่งเริ่มทำงานทั้ง 2 ระบบในเบื้องหลัง (Start Both - Background)
echo   [3] รีสตาร์ทระบบทั้ง 2 ใหม่ (Restart Both)
echo   [4] หยุดการทำงานทั้ง 2 ระบบ (Stop Both)
echo ---------------------------------------------------------------------
echo   [5] เปิดเว็บ GSE Work Order (Port 8000)
echo   [6] เปิดเว็บ Inventory Search (Port 8001)
echo   [7] เปิดดูไฟล์ Log (GSE W/O / Inventory)
echo   [0] ปิดหน้าต่างนี้ (Exit)
echo =====================================================================
set /p opt="กรุณาเลือกเมนู [0-7]: "

if "%opt%"=="1" goto MENU
if "%opt%"=="2" goto START_SERVICES
if "%opt%"=="3" goto RESTART_SERVICES
if "%opt%"=="4" goto STOP_SERVICES
if "%opt%"=="5" goto OPEN_8000
if "%opt%"=="6" goto OPEN_8001
if "%opt%"=="7" goto VIEW_LOGS
if "%opt%"=="0" exit /b 0
goto MENU

:START_SERVICES
echo.
echo กำลังสั่งเริ่มทำงานทั้ง 2 ระบบในเบื้องหลัง (Background)...
wscript.exe "D:\Project inventory\scripts\start_both_background.vbs"
timeout /t 3 /nobreak >nul
goto MENU

:RESTART_SERVICES
echo.
echo กำลังหยุดบริการเดิม...
powershell.exe -NoProfile -Command "& {
    $ports = @(8000, 8001)
    foreach ($pt in $ports) {
        $conns = Get-NetTCPConnection -LocalPort $pt -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}"
timeout /t 2 /nobreak >nul
echo กำลังเริ่มระบบใหม่ในเบื้องหลัง...
wscript.exe "D:\Project inventory\scripts\start_both_background.vbs"
timeout /t 4 /nobreak >nul
goto MENU

:STOP_SERVICES
echo.
echo กำลังหยุดการทำงานของทั้ง 2 ระบบ...
powershell.exe -NoProfile -Command "& {
    $ports = @(8000, 8001)
    foreach ($pt in $ports) {
        $conns = Get-NetTCPConnection -LocalPort $pt -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host ('หยุด Process PID: ' + $c.OwningProcess + ' ที่รันพอร์ต ' + $pt) -ForegroundColor Yellow
        }
    }
}"
timeout /t 2 /nobreak >nul
goto MENU

:OPEN_8000
start http://localhost:8000
goto MENU

:OPEN_8001
start http://localhost:8001
goto MENU

:VIEW_LOGS
cls
echo =====================================================================
echo   [1] เปิดดู Log ของ GSE Work Order (Port 8000)
echo   [2] เปิดดู Log ของ Inventory Search (Port 8001)
echo   [B] กลับไปเมนูหลัก
echo =====================================================================
set /p logopt="เลือกดู Log: "
if /i "%logopt%"=="1" (
    if exist "D:\Project dashboard\data\logs\web_app.log" (
        start notepad.exe "D:\Project dashboard\data\logs\web_app.log"
    ) else (
        echo ยังไม่มีไฟล์ log
        pause
    )
)
if /i "%logopt%"=="2" (
    if exist "D:\Project inventory\data\logs\web_app.log" (
        start notepad.exe "D:\Project inventory\data\logs\web_app.log"
    ) else (
        echo ยังไม่มีไฟล์ log
        pause
    )
)
goto MENU
