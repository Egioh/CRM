## CRM (Flask + SQLite)

### Что это
Мини‑CRM: таблица клиентов со статусами (в т.ч. свои), карточка с комментариями, заказами и платежами, календарь записей.

Есть интеграция **Telegram AI‑бота на каждого арендатора**: клиент пишет в Telegram, бот отвечает, показывает услуги/цены, собирает контакт, предлагает время (с учётом конфликтов и рабочих часов) и создаёт запись в календаре **только после подтверждения**.

**Внутренний контекст для ИИ / продолжения работы:** [docs/PROJECT_CONTEXT_INTERNAL.md](docs/PROJECT_CONTEXT_INTERNAL.md)

### Быстрый старт (Windows)

Создайте и активируйте виртуальное окружение:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Установите зависимости:

```bash
pip install -r requirements.txt
```

Создайте `.env` (можно скопировать из `.env.example`) и задайте как минимум `SECRET_KEY`. Файл подхватывается автоматически (`python-dotenv`).

Запуск:

```bash
python app.py
```

Откройте в браузере: `http://127.0.0.1:5000`

### Мессенджеры (Telegram + WhatsApp)

Пошаговая настройка вебхуков и переменных окружения: [docs/MESSAGING_SETUP_RU.md](docs/MESSAGING_SETUP_RU.md)

### Переменные окружения
- **`SECRET_KEY`**: секрет для сессий (обязательно поменять).
- **`FLASK_DEBUG`**: `1/true/yes` чтобы включить debug, иначе выключен.
- **`DATABASE_URL`**: строка подключения SQLAlchemy (по умолчанию `sqlite:///instance/crm.db`; для PostgreSQL: `postgresql+psycopg2://user:pass@localhost:5432/crm`). Перенос с SQLite: [docs/POSTGRES_MIGRATION_RU.md](docs/POSTGRES_MIGRATION_RU.md).

## Тесты (перед продакшеном)

```powershell
python -m pytest -q
python -m pytest -q --cov=. --cov-report=term-missing
```

Подробнее: [docs/TESTING_PRODUCTION_RU.md](docs/TESTING_PRODUCTION_RU.md).
- **`DEEPSEEK_API_KEY`**: ключ DeepSeek для ИИ‑понимания сообщений в Telegram (если не задан, бот будет работать по простым правилам без LLM).
- **`DEEPSEEK_MODEL`** (опционально): модель DeepSeek (по умолчанию `deepseek-v4-flash`).
- **`SESSION_COOKIE_SECURE`** (опционально): `1/true/yes`, если CRM работает по HTTPS (рекомендуется в проде).

> `.env` не коммитьте — он в `.gitignore`.

---

## Telegram AI‑бот (по одному боту на арендатора)

### Как это устроено
- Каждый арендатор создаёт своего бота в BotFather и сохраняет токен в CRM: **Интеграции → Telegram AI‑бот**.
- CRM генерирует секретный URL вебхука на арендатора:
  - `https://ВАШ_ДОМЕН/webhooks/telegram/<telegram_webhook_token>`
- Вебхук принимает апдейты Telegram и отвечает **от имени конкретного арендатора**.

### Что умеет MVP
- `/services` — показать услуги (из раздела **Услуги** в CRM).
- “запиши меня …” / свободный текст — бот пытается понять намерение, собрать контакт, выбрать услугу и время.
- Проверяет **рабочие часы**, **конфликты** и предлагает ближайшие окна кнопками.
- Создаёт `Client`, `Appointment` (`source=telegram_ai`) и `ClientReminder` (напоминание “онлайн-запись”) **только после подтверждения**.

### Локальная разработка
Telegram **не сможет** слать вебхук на `http://127.0.0.1:5000/...`. Нужен публичный HTTPS URL (туннель) или деплой.

### Публичный тест с вашего ПК (любая сеть + бот)

Пошагово: **[docs/PUBLIC_TEST_RU.md](docs/PUBLIC_TEST_RU.md)**

Кратко:

1. `powershell -ExecutionPolicy Bypass -File scripts\start_public_test.ps1`
2. В другом окне: `ngrok http 5000` → скопировать `https://....ngrok-free.app`
3. В `.env`: `PUBLIC_BASE_URL=https://....ngrok-free.app`, `SESSION_COOKIE_SECURE=1`, `TRUST_PROXY=1`
4. Перезапустить CRM, открыть сайт по **HTTPS** ngrok, в **Интеграциях** скопировать Webhook URL → `setWebhook`

---

## Деплой прототипа на Replit

### 1) Импорт репозитория
Создайте Repl → Import from GitHub → выберите репозиторий.

### 2) Secrets (Environment variables)
В Replit → Secrets добавьте минимум:
- `SECRET_KEY` — длинная случайная строка
- `DATABASE_URL` — например `sqlite:///crm.db` (для прототипа)
- `DEEPSEEK_API_KEY` — если хотите LLM‑понимание сообщений

### 3) Запуск
Для прототипа можно запускать:

```bash
python app.py
```

Replit даст публичный URL вида `https://<repl>.repl.co` (или новый домен). Используйте его при настройке Telegram webhook:

`https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<ВАШ_REPL_ДОМЕН>/webhooks/telegram/<telegram_webhook_token>`

### Тесты

После `pip install -r requirements.txt` запускайте так (на Windows надёжнее, чем команда `pytest` без PATH):

```bash
python -m pytest tests -v
```

