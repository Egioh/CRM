"""Исходящие сообщения WhatsApp Cloud API и Telegram Bot API."""

from __future__ import annotations

import os
from typing import Any, Optional

import requests

from models import Client, User


def send_telegram_raw(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    reply_markup: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    if not bot_token:
        return False, "Не задан Telegram bot token"
    if not chat_id:
        return False, "Не задан Telegram chat_id"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(
            url,
            json=payload,
            timeout=15,
        )
        data = r.json()
        if r.status_code == 200 and data.get("ok"):
            return True, "Сообщение отправлено в Telegram"
        return False, data.get("description") or f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, f"Ошибка сети: {e}"


def send_telegram_message(
    client: Client,
    text: str,
    *,
    user: Optional[User] = None,
    bot_token: Optional[str] = None,
    reply_markup: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """Backwards compatible wrapper used by CRM UI."""
    token = bot_token or (user.telegram_bot_token if user else None) or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return False, "Не задан TELEGRAM_BOT_TOKEN (или токен арендатора)"
    if not client.telegram_chat_id:
        return False, "У клиента не сохранён Telegram chat_id (нужно входящее сообщение)"
    return send_telegram_raw(
        bot_token=token,
        chat_id=client.telegram_chat_id,
        text=text,
        reply_markup=reply_markup,
    )


def send_whatsapp_message(user: User, client: Client, text: str) -> tuple[bool, str]:
    token = os.getenv("WA_ACCESS_TOKEN")
    phone_number_id = user.whatsapp_phone_number_id or os.getenv("WA_PHONE_NUMBER_ID")
    if not token:
        return False, "Не задан WA_ACCESS_TOKEN в .env"
    if not phone_number_id:
        return False, "Укажите Phone number ID в Интеграциях"
    if not client.phone:
        return False, "У клиента не указан телефон"
    to = "".join(c for c in client.phone if c.isdigit())
    if not to:
        return False, "Некорректный телефон клиента"
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code in (200, 201):
            return True, "Сообщение отправлено в WhatsApp"
        try:
            err = r.json()
            msg = err.get("error", {}).get("message", r.text[:300])
        except Exception:
            msg = r.text[:300]
        return False, f"WhatsApp API: {msg}"
    except requests.RequestException as e:
        return False, f"Ошибка сети: {e}"
