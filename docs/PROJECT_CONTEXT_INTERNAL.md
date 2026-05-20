# CRM — внутренний контекст проекта (для продолжения в другом чате)

Скопируйте этот файл в новый чат: «продолжи проект по `docs/PROJECT_CONTEXT_INTERNAL.md`».

**Обновлено:** поворот на таблицу клиентов со статусами; AI-анализ и автоответы в мессенджерах убраны из UI (маршрут `/analyze` удалён).

---

## Назначение

Веб‑CRM на **Flask + SQLite** для малого бизнеса:

- **Главная** — таблица клиентов (имя, телефон, статус, оплата), поиск и фильтр по статусу.
- **Карточка клиента** — статус, комментарии, заказы, платежи.
- **Статусы** — набор по умолчанию + пользовательские статусы владельца.
- **Календарь** — записи на приём (`Appointment`).
- **Вебхуки** Telegram/WhatsApp — только приём и сохранение в `InboundMessage` (без автоответа ИИ). Маршруты `/inbox`, `/integrations` остаются, убраны из главного меню.

---

## Стек

Python, Flask, Flask-Login, Flask-SQLAlchemy, Flask-WTF (CSRF), requests (только вебхуки).

Запуск: `python app.py` → http://127.0.0.1:5000  
Тесты: `python -m pytest tests -v`

---

## Структура файлов

| Файл | Роль |
|------|------|
| `app.py` | Маршруты, логика |
| `models.py` | ORM |
| `client_helpers.py` | Статусы по умолчанию, расчёт оплаты |
| `status_defaults.py` | Список дефолтных статусов |
| `messaging.py` | Blueprint `/webhooks/*` |
| `schema_migrations.py` | SQLite ALTER без Alembic |
| `templates/clients.html` | Главная — таблица |
| `templates/client_detail.html` | Карточка |
| `templates/statuses.html` | Управление статусами |
| `docs/MESSAGING_SETUP_RU.md` | Настройка мессенджеров для пользователя |

---

## Модели

- **User** — `whatsapp_phone_number_id` для привязки WA вебхука.
- **ClientStatus** — `user_id`, `name`, `color` (Bootstrap: secondary, primary, success, …), `position`. Уникальность `(user_id, name)`.
- **Client** — `status_id` → ClientStatus, контакты, `notes`.
- **ClientComment** — лента комментариев в карточке.
- **Order**, **Payment** — как раньше; оплата в таблице: сумма заказов vs сумма платежей (`client_helpers.payment_summary`).
- **InboundMessage**, **Appointment** — без изменений по смыслу.

### Статусы по умолчанию (при регистрации)

Новый → Ожидает клиента → В работе → Заказ готов → Ожидает оплаты → Оплачен → Завершён → Отменён.

Пользователь добавляет свои на `/statuses`.

### Изоляция данных (мультитенантность)

Каждый **User** = отдельный владелец CRM:

- **Клиенты** (`Client.user_id`) — видны только после `filter_by(user_id=current_user.id)`.
- **Статусы** (`ClientStatus.user_id`) — свой набор на аккаунт; при регистрации создаётся отдельный набор с **своими id**.
- Назначение статуса клиенту только через `_client_status_or_404` (статус того же `user_id`).
- Удаление/фильтр статусов — только в рамках `current_user.id`.

Заказы/платежи/комментарии изолированы через клиента (`Client.user_id` в join).

---

## Ключевые маршруты

| URL | Описание |
|-----|----------|
| `/` | Таблица клиентов (`?q=`, `?status=`) |
| `/client/<id>` | Карточка |
| `/client/<id>/status` POST | Смена статуса |
| `/client/<id>/comment` POST | Комментарий |
| `/statuses` | Список + создание статуса |
| `/statuses/<id>/delete` POST | Удаление (если не используется) |
| `/integrations`, `/inbox`, `/calendar` | Вспомогательные |
| `/webhooks/whatsapp`, `/webhooks/telegram` | Публичные, CSRF exempt |

**Удалено:** `/analyze/<client_id>` (DeepSeek).

---

## Миграции SQLite

При старте: `db.create_all()` + `apply_all_sqlite_migrations(app)` (колонки `user.whatsapp_phone_number_id`, `client.status_id`). Для существующих пользователей без статусов — `ensure_user_statuses` и проставление «Новый».

---

## Переменные окружения

`.env.example`: `SECRET_KEY`, `DATABASE_URL`, `FLASK_DEBUG`, `WA_*`, `TELEGRAM_*`. Файл `.env` **не подхватывается автоматически** (нет python-dotenv).

---

## Следующие шаги (идеи, не сделано)

1. Быстрая смена статуса без перезагрузки (HTMX).
2. Привязка `InboundMessage` → `Client` по телефону.
3. Исходящие сообщения WA/TG из карточки (без ИИ).
4. Фильтр «только не оплаченные» на главной.
5. Alembic вместо ручных ALTER.
6. Часовой пояс пользователя.

---

## Как продолжать

1. Прочитать этот файл и `app.py` / `models.py`.
2. `python -m pytest tests`.
3. Не возвращать автоответ ИИ в мессенджерах без явного запроса пользователя.
