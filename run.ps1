# One command to set up and run the Household API on Windows.
#   powershell -ExecutionPolicy Bypass -File run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. Virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1

# 2. Dependencies
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 3. Load .env if present
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

# 4. Generate a token on first run if none exists
if (-not $env:APP_TOKEN) {
    $env:APP_TOKEN = (python -c "import secrets; print(secrets.token_urlsafe(32))")
    Add-Content .env "APP_TOKEN=$($env:APP_TOKEN)"
    Write-Host "Generated a new APP_TOKEN and saved it to .env"
}
if (-not $env:DB_PATH) { $env:DB_PATH = "household.db" }

Write-Host "---------------------------------------------"
Write-Host "Token   : $env:APP_TOKEN"
Write-Host "Database: $env:DB_PATH"
Write-Host "Running : http://0.0.0.0:8000   (docs at /docs)"
Write-Host "---------------------------------------------"

uvicorn app:app --host 0.0.0.0 --port 8000
