# Перенос CRM с SQLite (instance/crm.db) на PostgreSQL.
# Запуск из корня репозитория:
#   powershell -ExecutionPolicy Bypass -File scripts\migrate_to_postgres.ps1 `
#     -PostgresUrl "postgresql+psycopg2://crm:crm@localhost:5432/crm"

param(
    [Parameter(Mandatory = $true)]
    [string]$PostgresUrl,
    [string]$SqliteUrl = "",
    [switch]$UpdateEnv,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $SqliteUrl) {
    $dbPath = Join-Path $Root "instance\crm.db"
    if (-not (Test-Path $dbPath)) {
        Write-Host "Не найден instance\crm.db. Укажите -SqliteUrl." -ForegroundColor Red
        exit 1
    }
    $SqliteUrl = "sqlite:///$($dbPath.Replace('\', '/'))"
}

Write-Host "SQLite:  $SqliteUrl" -ForegroundColor Cyan
Write-Host "Postgres: $($PostgresUrl -replace ':[^:@]+@', ':****@')" -ForegroundColor Cyan
Write-Host ""

pip install psycopg2-binary -q 2>$null

$env:POSTGRES_URL = $PostgresUrl
$env:SQLITE_URL = $SqliteUrl

if ($DryRun) {
    python scripts/migrate_sqlite_to_postgres.py --dry-run
    exit $LASTEXITCODE
}

Write-Host "1/2 Создание таблиц в PostgreSQL..." -ForegroundColor Yellow
python scripts/bootstrap_postgres.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "2/2 Копирование данных..." -ForegroundColor Yellow
python scripts/migrate_sqlite_to_postgres.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($UpdateEnv) {
    $envFile = Join-Path $Root ".env"
    if (Test-Path $envFile) {
        $lines = Get-Content $envFile -Encoding UTF8
        $found = $false
        $newLines = foreach ($line in $lines) {
            if ($line -match '^\s*DATABASE_URL\s*=') {
                $found = $true
                "DATABASE_URL=$PostgresUrl"
            } else {
                $line
            }
        }
        if (-not $found) {
            $newLines += "DATABASE_URL=$PostgresUrl"
        }
        Set-Content -Path $envFile -Value $newLines -Encoding UTF8
        Write-Host ""
        Write-Host ".env обновлён: DATABASE_URL -> PostgreSQL" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Готово. Перезапустите CRM (start_public_test.ps1 или python app.py)." -ForegroundColor Green
Write-Host "Проверка: python scripts/verify_postgres.py" -ForegroundColor Gray
