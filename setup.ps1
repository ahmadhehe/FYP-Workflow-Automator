# Run this script to set up the browser automation agent
# PowerShell setup script

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Browser Automation Agent - Setup Script" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create virtual environment
if (!(Test-Path "venv")) {
    Write-Host "Step 1: Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Virtual environment created successfully" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Step 1: Virtual environment already exists" -ForegroundColor Green
}

Write-Host ""

# Step 2: Activate virtual environment and install packages
Write-Host "Step 2: Activating virtual environment and installing packages..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

Write-Host "Installing Python packages..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Python packages installed successfully" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to install Python packages" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 3: Install Playwright browsers
Write-Host "Step 3: Installing Playwright browsers..." -ForegroundColor Yellow
playwright install chromium
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Playwright browsers installed successfully" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to install Playwright browsers" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 4: Create .env file if it doesn't exist
if (!(Test-Path ".env")) {
    Write-Host "Step 4: Creating .env file..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "[OK] .env file created" -ForegroundColor Green
    Write-Host ""
    Write-Host "[WARNING] IMPORTANT: Edit .env and add your API key!" -ForegroundColor Magenta
    Write-Host "          Run: notepad .env" -ForegroundColor Magenta
} else {
    Write-Host "Step 4: .env file already exists" -ForegroundColor Green
}

Write-Host ""

# Summary
Write-Host "========================================================" -ForegroundColor Green
Write-Host "              Setup Complete!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Activate virtual environment: " -NoNewline
Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "2. Edit .env file with your API key: " -NoNewline
Write-Host "notepad .env" -ForegroundColor Yellow
Write-Host "3. Run the test: " -NoNewline
Write-Host "python agent.py" -ForegroundColor Yellow
Write-Host "4. Try examples: " -NoNewline
Write-Host "python examples.py" -ForegroundColor Yellow
Write-Host "5. Start API server: " -NoNewline
Write-Host "python server.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "Note: Always activate the virtual environment before running scripts!" -ForegroundColor Gray
Write-Host "For detailed instructions, see SETUP.md" -ForegroundColor Gray
Write-Host ""
