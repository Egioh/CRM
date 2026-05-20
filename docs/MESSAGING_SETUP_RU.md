# Настройка Telegram и WhatsApp для CRM (вебхуки)

Эта инструкция для **владельца CRM**: как подключить входящие сообщения из **Telegram** и **WhatsApp** к вашему серверу, где запущено приложение Flask.

После настройки сервис будет принимать события по адресам:

- `https://ВАШ_ДОМЕН/webhooks/whatsapp` — WhatsApp Cloud API (Meta)
- `https://ВАШ_ДОМЕН/webhooks/telegram` — Telegram Bot API

### Привязка WhatsApp к вашему аккаунту в CRM

В веб‑интерфейсе CRM откройте раздел **«Интеграции»** и укажите **Phone number ID** из кабинета Meta (тот же идентификатор, что приходит в вебхуке как `metadata.phone_number_id`). Тогда входящие сообщения WhatsApp будут сохраняться во **«Входящие»** вашего пользователя.

Сейчас вебхуки **принимают, сохраняют в БД и логируют** сообщения (основа для будущего ИИ и автозаписи). Ручной календарь записей доступен в разделе **«Календарь»**.

---

## Общие требования

1. **Публичный HTTPS‑URL**  
   Meta и Telegram должны достучаться до вашего сервера из интернета. На своём компьютере для теста обычно используют **ngrok**, **Cloudflare Tunnel** или деплой на VPS / PaaS (Railway, Render, Fly.io и т.д.).

2. **Переменные окружения**  
   Скопируйте `.env.example` в `.env` и заполните значения из разделов ниже. Перезапустите приложение после изменений.

3. **Безопасность**  
   - Для WhatsApp задайте **`WA_APP_SECRET`** и проверку подписи `X-Hub-Signature-256` (уже реализовано в коде).  
   - Для Telegram при настройке вебхука укажите **секрет** и задайте **`TELEGRAM_WEBHOOK_SECRET`** — тогда запросы без заголовка `X-Telegram-Bot-Api-Secret-Token` будут отклоняться.

---

## Часть A. Telegram

### A1. Создать бота

1. Откройте Telegram, найдите **@BotFather**.  
2. Команда `/newbot` → имя и username бота.  
3. Сохраните **HTTP API token** (выглядит как `123456:ABC-DEF...`).

Токен положите в переменную окружения (на сервере или в `.env`):

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
```

> **Важно:** токен не публикуйте в чатах и не коммитьте в git. В репозитории держите только `.env.example` без реальных значений.

### A2. Секрет вебхука (рекомендуется)

При вызове `setWebhook` можно передать `secret_token`. Задайте длинную случайную строку и ту же строку в CRM:

```env
TELEGRAM_WEBHOOK_SECRET=случайная_длинная_строка
```

### A3. Указать URL вебхука

Подставьте свой домен и токен:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://ВАШ_ДОМЕН/webhooks/telegram&secret_token=<TELEGRAM_WEBHOOK_SECRET>
```

Удобнее через POST (curl), если в URL есть спецсимволы:

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://ВАШ_ДОМЕН/webhooks/telegram\",\"secret_token\":\"ВАШ_СЕКРЕТ\"}"
```

(В PowerShell кавычки экранируйте по-другому или используйте файл JSON.)

### A4. Проверка

- Напишите боту в личку.  
- В логах CRM должна появиться строка вида `telegram.message chat_id=... text='...'`.

### A5. Отключить вебхук (если нужно)

```text
https://api.telegram.org/bot<TOKEN>/deleteWebhook
```

---

## Часть B. WhatsApp (Meta Cloud API)

Ниже — типовой путь через **Meta for Developers** (WhatsApp Cloud API). У регионов и аккаунтов интерфейс может чуть отличаться, но шаги те же.

### B1. Аккаунт и приложение

1. Зайдите на [developers.facebook.com](https://developers.facebook.com/).  
2. **My Apps** → **Create App** → тип **Business** (или предложенный для WhatsApp).  
3. В продукте **WhatsApp** включите настройку API (Get started).

### B2. Тестовый номер и токен

В кабинете WhatsApp найдите:

- **Temporary access token** (или постоянный через System User — для продакшена).  
- **Phone number ID** (идентификатор номера отправителя).  
- При необходимости **WhatsApp Business Account ID**.

Для отправки сообщений из CRM позже понадобятся токен и Phone number ID; для **входящих вебхуков** достаточно настроек ниже.

### B3. Verify Token (строка, которую придумываете вы)

При подписке вебхука Meta отправит GET‑запрос с параметром `hub.verify_token`. В CRM должно быть **то же самое** значение:

```env
WA_VERIFY_TOKEN=любая_секретная_строка_которую_вы_придумали
```

### B4. App Secret (для подписи POST)

В настройках приложения Meta: **Settings → Basic → App secret**.

```env
WA_APP_SECRET=секрет_приложения_Meta
```

С этим значением CRM проверяет заголовок **`X-Hub-Signature-256`** у входящих POST — так вы убеждаетесь, что запрос пришёл от Meta.

### B5. Подписка на вебхук в Meta

1. В разделе WhatsApp → **Configuration** (или Webhooks) укажите **Callback URL**:  
   `https://ВАШ_ДОМЕН/webhooks/whatsapp`  
2. **Verify token** — ровно как в `WA_VERIFY_TOKEN`.  
3. Нажмите **Verify and save**. Meta сделает GET — приложение должно ответить `hub.challenge`.  
4. Подпишитесь на поле **`messages`** (и при необходимости `messaging_postbacks` и др.).

### B6. Локальная отладка

Meta не достучится до `http://127.0.0.1`. Используйте туннель, например ngrok:

```bash
ngrok http 5000
```

В Meta укажите выданный `https://....ngrok-free.app/webhooks/whatsapp`.

### B7. Проверка

- Отправьте сообщение на **тестовый** WhatsApp номер из кабинета Meta (или добавьте тестовый номер получателя по инструкции Meta).  
- В логах CRM должны появиться записи `whatsapp.message from=... text='...'`.

---

## Таблица переменных окружения

| Переменная | Обязательность | Назначение |
|------------|----------------|------------|
| `TELEGRAM_BOT_TOKEN` | Для ручных вызовов API / будущей отправки | Токен бота (не используется самим вебхуком приёма, но нужен для `setWebhook` и ответов) |
| `TELEGRAM_WEBHOOK_SECRET` | Рекомендуется | Должен совпадать с `secret_token` в `setWebhook` |
| `WA_VERIFY_TOKEN` | Обязательно для приёма GET от Meta | Проверка подписки вебхука |
| `WA_APP_SECRET` | Рекомендуется для продакшена | Проверка подписи POST `X-Hub-Signature-256` |

---

## Что дальше (идея «ИИ + запись»)

1. **Календарь и слоты в БД** — чтобы не было двойных записей.  
2. **Обработчик после вебхука** — распознать намерение (дата/услуга), вызвать только ваши функции создания записи.  
3. **Исходящие ответы** — Telegram `sendMessage`, WhatsApp `POST /{PHONE_NUMBER_ID}/messages` с токеном из Meta.  
4. **Очередь** (опционально) — Celery / RQ, если ИИ и внешние API долгие.

Если нужно, следующим шагом можно добавить в CRM страницу «Интеграции» с копированием URL вебхуков и статусом последнего события.
