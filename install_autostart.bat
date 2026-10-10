@echo off
chcp 65001 >nul
cd /d "D:\Project dashboard"

echo ======================================================
echo    Install Auto-Start on Windows Boot
echo ======================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {
    $startupFolder = [Environment]::GetFolderPath('Startup')
    $targetVbs = Join-Path $startupFolder 'eMRO_Monitor_Startup.vbs'
    $content = @'
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\Project dashboard"
WScript.Sleep 10000
WshShell.Run "C:\Python313\pythonw.exe main.py", 0, False
'@
    [System.IO.File]::WriteAllText($targetVbs, $content)
    Write-Host ('[SUCCESS] Created auto-start launcher at:') -ForegroundColor Green
    Write-Host ('  ' + $targetVbs) -ForegroundColor Cyan
    Write-Host '`neMRO Monitor will automatically start 10s after Windows boot.' -ForegroundColor Green
}"

pause
