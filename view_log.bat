@echo off
chcp 65001 >nul
cd /d "D:\Project dashboard"

echo ======================================================
echo    eMRO Inventory Monitor - Live Log Stream
echo    (กด Ctrl+C เพื่อหยุดดู)
echo ======================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {
    $logFile = 'data\monitor.log'
    if (Test-Path $logFile) {
        Get-Content $logFile -Tail 30 -Wait
    } else {
        Write-Host 'Log file does not exist yet. Please start monitor first.' -ForegroundColor Yellow
        pause
    }
}"
