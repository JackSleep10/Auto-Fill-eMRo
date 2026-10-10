@echo off
chcp 65001 >nul
cd /d "D:\Project dashboard"

echo ======================================================
echo    eMRO Inventory Monitor - Current Status
echo ======================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {
    $pidFile = 'data\monitor.pid'
    $logFile = 'data\monitor.log'
    $isRunning = $false
    $procId = $null

    if (Test-Path $pidFile) {
        $p = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($p) {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            if ($proc) {
                $isRunning = $true
                $procId = $p
                $mem = [math]::Round($proc.WorkingSet64 / 1MB, 1)
                $startTime = $proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss')
                Write-Host 'Status:      RUNNING (กำลังทำงานเบื้องหลัง)' -ForegroundColor Green
                Write-Host ('Process PID: ' + $procId) -ForegroundColor Green
                Write-Host ('Memory:      ' + $mem + ' MB') -ForegroundColor Cyan
                Write-Host ('Started At:  ' + $startTime) -ForegroundColor Cyan
            }
        }
    }

    if (-not $isRunning) {
        Write-Host 'Status:      STOPPED (ไม่ได้ทำงานอยู่)' -ForegroundColor Red
    }

    Write-Host '`n---------------- Recent Logs (data\monitor.log) ----------------' -ForegroundColor DarkGray
    if (Test-Path $logFile) {
        Get-Content $logFile -Tail 15 | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host 'No log file found yet.' -ForegroundColor DarkGray
    }
    Write-Host '----------------------------------------------------------------`n' -ForegroundColor DarkGray
}"

pause
