# HTTPS tunnel to local CRM (Cloudflare Quick Tunnel).
# CRM must be running on port 5000 (start_public_test.ps1).
#
#   powershell -ExecutionPolicy Bypass -File scripts\start_cloudflared_tunnel.ps1

$ErrorActionPreference = "Stop"

$candidates = @(
    "${env:ProgramFiles}\cloudflared\cloudflared.exe",
    "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
    "cloudflared"
)

$cf = $null
foreach ($c in $candidates) {
    if ($c -eq "cloudflared") {
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
        if (Get-Command cloudflared -ErrorAction SilentlyContinue) { $cf = "cloudflared"; break }
    }
    elseif (Test-Path $c) { $cf = $c; break }
}

if (-not $cf) {
    Write-Host "cloudflared not found. Install:" -ForegroundColor Yellow
    Write-Host "  winget install --id Cloudflare.cloudflared --source winget"
    Write-Host "Close and reopen PowerShell, then run this script again."
    exit 1
}

$port = if ($env:FLASK_PORT) { $env:FLASK_PORT } else { "5000" }
$url = "http://127.0.0.1:$port"

Write-Host ""
Write-Host "=== Cloudflare Tunnel -> $url ===" -ForegroundColor Cyan
Write-Host "Copy https://....trycloudflare.com into .env as PUBLIC_BASE_URL"
Write-Host "Restart CRM. Open the site only via that HTTPS URL."
Write-Host ""
Write-Host "Using HTTP/2 (not QUIC) - helps when ISP/firewall blocks UDP." -ForegroundColor DarkGray
Write-Host ""

$tunnelArgs = @("tunnel", "--url", $url, "--protocol", "http2")
if ($cf -eq "cloudflared") {
    & cloudflared @tunnelArgs
}
else {
    & $cf @tunnelArgs
}
