# Публичный тест CRM с домашнего ПК (любая сеть + Telegram)

Цель: открыть веб-интерфейс и принимать вебхуки Telegram/WhatsApp с телефона или другой сети, не деплоя на Replit.

## Что понадобится

- Python 3.10+ и зависимости: `pip install -r requirements.txt`
- Файл `.env` (скопируйте из `.env.example`, задайте `SECRET_KEY`)
- **ngrok** (проще всего) или **Cloudflare Tunnel** — даёт публичный **HTTPS** URL на ваш `localhost:5000`
- Бот в [@BotFather](https://t.me/BotFather) и токен в CRM → **Интеграции**

Telegram **не** шлёт вебхуки на `http://127.0.0.1` — нужен именно публичный HTTPS.

---

## Быстрый старт (ngrok + Windows)

### 1. Запуск CRM

В PowerShell из папки проекта:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_public_test.ps1
```

Сервер слушает `0.0.0.0:5000` (доступен в локальной сети и через туннель).

Альтернатива (стабильнее под нагрузкой):

```powershell
pip install waitress
$env:FLASK_HOST="0.0.0.0"
python -c "from wsgi import app; from waitress import serve; serve(app, host='0.0.0.0', port=5000)"
```

### 2. Туннель ngrok

В **втором** окне терминала:

```bash
ngrok http 5000
```

Скопируйте строку **Forwarding**, например: `https://a1b2c3d4.ngrok-free.app`

### 3. Настройка `.env`

```env
PUBLIC_BASE_URL=https://a1b2c3d4.ngrok-free.app
SESSION_COOKIE_SECURE=1
TRUST_PROXY=1
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

Перезапустите CRM (шаг 1).

### 4. Вход в CRM

Откройте в браузере **HTTPS-адрес ngrok** (не `127.0.0.1`), зарегистрируйтесь / войдите.

> На бесплатном ngrok при первом заходе может быть страница-предупреждение — нажмите «Visit Site».

### 5. Telegram AI-бот

1. **Интеграции** → вставьте токен бота → включите AI-бота → **Сохранить**.
2. На странице появится **Webhook URL** с вашим `PUBLIC_BASE_URL`.
3. Подключите вебхук (подставьте свой токен и URL из CRM):

```text
https://api.telegram.org/bot<ВАШ_ТОКЕН>/setWebhook?url=https://a1b2c3d4.ngrok-free.app/webhooks/telegram/<telegram_webhook_token_из_CRM>
```

Проверка:

```text
https://api.telegram.org/bot<ВАШ_ТОКЕН>/getWebhookInfo
```

4. Напишите боту в Telegram — ответ должен прийти, запись появится в CRM.

### 6. WhatsApp (опционально)

В Meta укажите Callback URL:

`https://a1b2c3d4.ngrok-free.app/webhooks/whatsapp`

и тот же verify token, что в `.env` (`WA_VERIFY_TOKEN`).

---

## Cloudflare Tunnel (бесплатно, постоянный поддомен)

1. Установите `cloudflared`.
2. `cloudflared tunnel --url http://localhost:5000`
3. Скопируйте выданный `https://....trycloudflare.com` в `PUBLIC_BASE_URL`.
4. Дальше — как в шагах 3–5 выше.

---

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `PUBLIC_BASE_URL` | Публичный HTTPS без слэша в конце — для отображения webhook URL |
| `TRUST_PROXY` | `1` — учитывать `X-Forwarded-Proto/Host` от ngrok |
| `SESSION_COOKIE_SECURE` | `1` при HTTPS (можно включить автоматически, если `PUBLIC_BASE_URL` начинается с `https://`) |
| `FLASK_HOST` | `0.0.0.0` — слушать все интерфейсы |
| `FLASK_PORT` | Порт (по умолчанию `5000`) |

---

## Ограничения домашнего теста

- ПК должен быть включён; при перезапуске ngrok URL **меняется** (на free-плане) — обновите `.env` и `setWebhook`.
- Не открывайте порт 5000 напрямую в интернет без файрвола — безопаснее только туннель.
- Встроенный `python app.py` — для теста; для длительного показа клиентам лучше Waitress + туннель.

---

## Устранение неполадок

| Симптом | Что проверить |
|---------|----------------|
| `cloudflared` не распознано | Установка: `winget install --id Cloudflare.cloudflared --source winget`, **закройте и откройте PowerShell**, или скрипт `scripts\start_cloudflared_tunnel.ps1` |
| ngrok `ERR_NGROK_9040` / IP blocked | Используйте **cloudflared** вместо ngrok (см. выше) |
| cloudflared `QUIC timeout` / цикл ERR | Скрипт уже использует `--protocol http2`; проверьте файрвол/VPN; попробуйте другую сеть (мобильный интернет) |
| CRM открывается только локально | Запущен ли туннель; заходите по **https** URL туннеля |
| В интеграциях webhook с `127.0.0.1` | Задан ли `PUBLIC_BASE_URL` и перезапущен ли сервер |
| Бот молчит, в CRM есть входящие | В логе CRM: `send failed` + таймаут `api.telegram.org` — **с ПК не уходят ответы** (блокировка). VPN, `TELEGRAM_HTTPS_PROXY` в `.env`, или VPS/Replit. Проверка: `python scripts/test_telegram_outbound.py` |
| Бот молчит, входящих нет | `getWebhookInfo`, токен в CRM, AI-бот включён, URL совпадает с CRM, туннель жив |
| Сессия сбрасывается | `SESSION_COOKIE_SECURE=1` при HTTPS |
| 403 от ngrok | Страница «Visit Site» на free-плане — откройте URL в браузере один раз |
