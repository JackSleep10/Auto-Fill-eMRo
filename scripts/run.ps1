# Start eMRO Monitor
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
Write-Host "Starting eMRO Inventory Monitor..." -ForegroundColor Green
python main.py
