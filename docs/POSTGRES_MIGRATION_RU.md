# Перенос CRM на PostgreSQL (Windows)

Данные сейчас в **`instance/crm.db`** (SQLite). После переноса CRM читает только PostgreSQL.

## 1. Установите PostgreSQL

1. Скачайте установщик: https://www.postgresql.org/download/windows/
2. Запомните пароль суперпользователя `postgres`.
3. Порт по умолчанию: **5432**.

Или (если есть winget):

```powershell
winget install PostgreSQL.PostgreSQL.17
```

## 2. Создайте базу и пользователя

Откройте **SQL Shell (psql)** или pgAdmin и выполните:

```sql
CREATE USER crm WITH PASSWORD 'ваш_надёжный_пароль';
CREATE DATABASE crm OWNER crm;
GRANT ALL PRIVILEGES ON DATABASE crm TO crm;
```

Строка подключения для CRM:

```text
postgresql+psycopg2://crm:ваш_надёжный_пароль@localhost:5432/crm
```

## 3. Зависимости Python

```powershell
cd C:\Users\Anastasia\Desktop\CRM
pip install -r requirements.txt
```

(`psycopg2-binary` уже в `requirements.txt`.)

## 4. Остановите CRM

Закройте окно с `start_public_test.ps1` / `python app.py`, чтобы SQLite не был заблокирован.

## 5. Перенос одной командой

```powershell
cd C:\Users\Anastasia\Desktop\CRM

powershell -ExecutionPolicy Bypass -File scripts\migrate_to_postgres.ps1 `
  -PostgresUrl "postgresql+psycopg2://crm:ВАШ_ПАРОЛЬ@localhost:5432/crm" `
  -UpdateEnv
```

- `-UpdateEnv` — подставит `DATABASE_URL` в `.env`.
- Без `-UpdateEnv` — только копирование данных; URL в `.env` поменяйте вручную.

Просмотр без записи:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\migrate_to_postgres.ps1 `
  -PostgresUrl "postgresql+psycopg2://crm:...@localhost:5432/crm" -DryRun
```

## 6. Проверка и запуск

```powershell
python scripts/verify_postgres.py
powershell -ExecutionPolicy Bypass -File scripts\start_public_test.ps1
```

Войдите под своим email — клиенты и заказы должны совпадать с SQLite.

## 7. Резервная копия SQLite

Скопируйте файл перед переносом:

```powershell
Copy-Item instance\crm.db instance\crm.db.backup
```

## Ручной режим (два шага)

```powershell
$env:POSTGRES_URL = "postgresql+psycopg2://crm:...@localhost:5432/crm"
$env:SQLITE_URL = "sqlite:///C:/Users/Anastasia/Desktop/CRM/instance/crm.db"

python scripts/bootstrap_postgres.py
python scripts/migrate_sqlite_to_postgres.py
```

В `.env`:

```env
DATABASE_URL=postgresql+psycopg2://crm:...@localhost:5432/crm
```

## Частые ошибки

| Ошибка | Решение |
|--------|---------|
| `connection refused` | Служба PostgreSQL не запущена (services.msc → postgresql). |
| `password authentication failed` | Проверьте логин/пароль в URL. |
| `database "crm" does not exist` | Выполните `CREATE DATABASE crm`. |
| `нет таблиц в PostgreSQL` | Сначала `bootstrap_postgres.py`. |
| После переноса 0 пользователей | Неверный `DATABASE_URL` или миграция не выполнена. |

## Откат на SQLite

В `.env`:

```env
DATABASE_URL=sqlite:///instance/crm.db
```

Перезапустите CRM. Файл `instance/crm.db` не удаляется при миграции.
