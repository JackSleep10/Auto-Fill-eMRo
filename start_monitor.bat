@echo off
chcp 65001 >nul
cd /d "D:\Project dashboard"

echo ======================================================
echo    eMRO Inventory Monitor - Start in Background
echo ======================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {
    $pidFile = 'data\monitor.pid'
    if (Test-Path $pidFile) {
        $p = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
            Write-Host '[INFO] Monitor is ALREADY running with PID:' $p -ForegroundColor Yellow
            exit 0
        }
    }
    Start-Process wscript.exe -ArgumentList 'run_background.vbs'
    Start-Sleep -Seconds 2
    if (Test-Path $pidFile) {
        $newPid = Get-Content $pidFile -ErrorAction SilentlyContinue
        Write-Host '[SUCCESS] Monitor started in background with PID:' $newPid -ForegroundColor Green
    } else {
        Write-Host '[SUCCESS] Monitor background launcher executed.' -ForegroundColor Green
    }
    Write-Host 'You can check status anytime using: check_status.bat' -ForegroundColor Cyan
    Write-Host 'You can view live logs using:       view_log.bat' -ForegroundColor Cyan
}"

pause
