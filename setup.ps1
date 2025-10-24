# SPX 0DTE Options Trading Application - PyQt6 Edition
# Setup Script

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "SPX 0DTE Trader - PyQt6 Edition Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (Test-Path ".\.venv") {
    Write-Host "[OK] Virtual environment found" -ForegroundColor Green
} else {
    Write-Host "[CREATING] Virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    if ($?) {
        Write-Host "[OK] Virtual environment created" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "[ACTIVATING] Virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

Write-Host ""
Write-Host "[INSTALLING] Dependencies from requirements.txt..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if ($?) {
    Write-Host ""
    Write-Host "[SUCCESS] All dependencies installed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host "Setup Complete!" -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To run the application:" -ForegroundColor Yellow
    Write-Host "  1. Ensure TWS or IB Gateway is running (port 7497 for paper trading)"
    Write-Host "  2. Run: .\.venv\Scripts\python.exe main.py"
    Write-Host ""
    Write-Host "Or with venv activated:" -ForegroundColor Yellow
    Write-Host "  1. .\.venv\Scripts\Activate.ps1"
    Write-Host "  2. python main.py"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "[ERROR] Failed to install dependencies" -ForegroundColor Red
    Write-Host "Please check your internet connection and try again" -ForegroundColor Red
}
