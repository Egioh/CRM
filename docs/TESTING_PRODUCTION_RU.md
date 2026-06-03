# Тестирование перед продакшеном

## Запуск

```powershell
cd C:\Users\Anastasia\Desktop\CRM
pip install -r requirements.txt
python -m pytest -q
```

С покрытием:

```powershell
python -m pytest -q --cov=. --cov-report=term-missing --cov-config=.coveragerc
```

## Маркеры

| Маркер | Назначение |
|--------|------------|
| `smoke` | Доступность маршрутов |
| `unit` | Хелперы без полного HTTP |
| `security` | RBAC и изоляция tenant |
| `slow` | Тяжёлые / внешние моки |

```powershell
python -m pytest -m security -q
python -m pytest -m "not slow" -q
```

## Что покрыто

- Авторизация, регистрация, CSRF (частично)
- Клиенты, заказы, платежи, статусы, календарь, услуги
- WhatsApp/Telegram вебхуки (моки)
- Telegram AI tenant webhook
- Отчёты, сотрудники, админы, расходы
- RBAC: admin не видит /integrations и /admins
- IDOR: чужие client/order/staff недоступны
- Unit: client_helpers, reports_helpers, i18n, phone, recurrence, migrate defaults

## Перед деплоем (чеклист)

1. `python -m pytest -q` — все зелёные
2. `SECRET_KEY` в `.env` — длинная случайная строка (не `change-me`)
3. `DATABASE_URL` — PostgreSQL в проде
4. `SESSION_COOKIE_SECURE=1` за HTTPS
5. Не коммитить `.env`, `.env.postgres.local`, `*.db`
6. Проверить `PUBLIC_BASE_URL` и вебхук Telegram после рестарта туннеля
