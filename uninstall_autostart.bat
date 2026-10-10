@echo off
chcp 65001 >nul
cd /d "D:\Project dashboard"

echo ======================================================
echo    Remove Auto-Start from Windows Boot
echo ======================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {
    $startupFolder = [Environment]::GetFolderPath('Startup')
    $targetVbs = Join-Path $startupFolder 'eMRO_Monitor_Startup.vbs'
    if (Test-Path $targetVbs) {
        Remove-Item $targetVbs -Force
        Write-Host '[SUCCESS] Removed eMRO_Monitor_Startup.vbs from Windows Startup.' -ForegroundColor Green
    } else {
        Write-Host '[INFO] Auto-start file was not found in Startup folder.' -ForegroundColor Cyan
    }
}"

pause
