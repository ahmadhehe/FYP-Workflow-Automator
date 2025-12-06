# Browser Agent - Start Script
# This script starts both the backend server and frontend development server

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           Browser Agent - Development Servers             ║" -ForegroundColor Cyan  
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
$venvPath = ".\venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvPath)) {
    Write-Host "❌ Virtual environment not found. Please run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Check if node_modules exists in frontend
$nodeModules = ".\frontend\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location .\frontend
    npm install
    Pop-Location
    Write-Host "✓ Frontend dependencies installed" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "🐍 Activating Python virtual environment..." -ForegroundColor Yellow
& $venvPath

# Start backend server in background
Write-Host "🚀 Starting backend server on http://localhost:8000..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & ".\venv\Scripts\python.exe" server.py
}

# Wait a moment for backend to start
Start-Sleep -Seconds 2

# Start frontend in foreground
Write-Host "🎨 Starting frontend on http://localhost:3000..." -ForegroundColor Yellow
Write-Host ""
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Backend API:    http://localhost:8000" -ForegroundColor Green
Write-Host "  API Docs:       http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Frontend:       http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop both servers" -ForegroundColor DarkGray
Write-Host ""
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host ""

Push-Location .\frontend
try {
    npm start
} finally {
    Pop-Location
    # Stop backend when frontend exits
    Write-Host ""
    Write-Host "🛑 Stopping backend server..." -ForegroundColor Yellow
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -ErrorAction SilentlyContinue
    Write-Host "✓ Servers stopped" -ForegroundColor Green
}
