"""Привязка входящих сообщений к клиентам."""

from __future__ import annotations

from models import Client, db
from client_helpers import default_status_for_user
from phone_utils import normalize_phone_digits, phones_match


def find_client_by_phone(user_id: int, phone: str) -> Client | None:
    for c in Client.query.filter_by(user_id=user_id).all():
        if phones_match(c.phone, phone):
            return c
    return None


def find_client_by_telegram_chat(user_id: int, chat_id: str) -> Client | None:
    if not chat_id:
        return None
    return Client.query.filter_by(
        user_id=user_id, telegram_chat_id=str(chat_id)
    ).first()


def find_or_create_client_for_whatsapp(
    user_id: int, phone: str, display_name: str | None = None
) -> Client:
    existing = find_client_by_phone(user_id, phone)
    if existing:
        return existing
    default_st = default_status_for_user(user_id)
    name = display_name or f"WhatsApp {phone}"
    client = Client(
        user_id=user_id,
        name=name[:100],
        phone=phone,
        status_id=default_st.id if default_st else None,
        notes="Создан автоматически из WhatsApp",
    )
    db.session.add(client)
    db.session.flush()
    return client


def find_or_create_client_for_telegram(
    user_id: int,
    chat_id: str,
    display_name: str | None = None,
) -> Client:
    existing = find_client_by_telegram_chat(user_id, chat_id)
    if existing:
        return existing
    default_st = default_status_for_user(user_id)
    name = (display_name or f"Telegram {chat_id}")[:100]
    client = Client(
        user_id=user_id,
        name=name,
        telegram_chat_id=str(chat_id),
        status_id=default_st.id if default_st else None,
        notes="Создан автоматически из Telegram",
    )
    db.session.add(client)
    db.session.flush()
    return client
