# Install dependencies and Playwright browser
Write-Host "Installing Python packages from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "Installing Playwright Chromium browser..." -ForegroundColor Cyan
python -m playwright install chromium

Write-Host "`nSetup complete! You can now run scripts\run.ps1 to start the monitor." -ForegroundColor Green
