# Start CRM for public testing (Cloudflare Tunnel).
# From repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\start_public_test.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Write-Host "Create .env from .env.example and set SECRET_KEY." -ForegroundColor Yellow
    if (Test-Path ".env.example") { Copy-Item ".env.example" ".env" }
}

Write-Host ""
Write-Host "=== CRM public test ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Step 1. This window runs the server on 0.0.0.0:5000"
Write-Host "Step 2. In another PowerShell window run the tunnel:"
Write-Host "        powershell -ExecutionPolicy Bypass -File scripts\start_cloudflared_tunnel.ps1"
Write-Host ""
Write-Host "Step 3. Copy HTTPS URL from tunnel output (https://....trycloudflare.com)"
Write-Host "        into .env:"
Write-Host "        PUBLIC_BASE_URL=https://....trycloudflare.com"
Write-Host "        SESSION_COOKIE_SECURE=1"
Write-Host "        TRUST_PROXY=1"
Write-Host ""
Write-Host "Step 4. Restart this script, open CRM via the tunnel HTTPS URL"
Write-Host "Step 5. Integrations -> copy Webhook URL -> setWebhook in Telegram"
Write-Host ""
Write-Host "Details: docs\PUBLIC_TEST_RU.md"
Write-Host ""

$env:FLASK_HOST = "0.0.0.0"
$env:FLASK_PORT = "5000"
if (-not $env:TRUST_PROXY) { $env:TRUST_PROXY = "1" }

python app.py
