## CRM (Flask + SQLite)

### Что это
Мини‑CRM: таблица клиентов со статусами (в т.ч. свои), карточка с комментариями, заказами и платежами, календарь записей. Вебхуки Telegram/WhatsApp только для приёма сообщений (без автоответа ИИ).

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
- **`DATABASE_URL`**: строка подключения SQLAlchemy (по умолчанию `sqlite:///crm.db`).
- **`DEEPSEEK_API_KEY`**: ключ DeepSeek для AI‑анализа (если не задан, анализ вернёт понятное сообщение).

### Тесты

После `pip install -r requirements.txt` запускайте так (на Windows надёжнее, чем команда `pytest` без PATH):

```bash
python -m pytest tests -v
```

