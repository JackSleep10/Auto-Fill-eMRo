@echo off
chcp 65001 >nul
cd /d "D:\Project dashboard"

echo ======================================================
echo    eMRO Inventory Monitor - Stop Background Process
echo ======================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {
    $pidFile = 'data\monitor.pid'
    $stopped = $false
    if (Test-Path $pidFile) {
        $p = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($p) {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host ('[INFO] Stopping monitor process (PID: ' + $p + ')...') -ForegroundColor Yellow
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                $stopped = $true
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }

    # Also search for any stray pythonw processes running main.py if needed
    $strays = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*pythonw*main.py*' }
    foreach ($s in $strays) {
        Write-Host ('[INFO] Stopping background pythonw instance (PID: ' + $s.ProcessId + ')...') -ForegroundColor Yellow
        Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped = $true
    }

    if ($stopped) {
        Write-Host '[SUCCESS] eMRO Monitor has been stopped.' -ForegroundColor Green
    } else {
        Write-Host '[INFO] No running eMRO Monitor process was found.' -ForegroundColor Cyan
    }
}"

pause
