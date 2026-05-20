"""
Вебхуки для внешних каналов (Telegram, WhatsApp Cloud API).

Сохраняет входящие сообщения в InboundMessage. Владелец CRM для WhatsApp
определяется по User.whatsapp_phone_number_id = metadata.phone_number_id.
Для Telegram при ровно одном пользователе в БД сообщения привязываются к нему.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Optional

from flask import Blueprint, abort, current_app, jsonify, request

from client_linking import (
    find_or_create_client_for_telegram,
    find_or_create_client_for_whatsapp,
)
from models import InboundMessage, User, db

bp = Blueprint("messaging", __name__, url_prefix="/webhooks")

MESSAGING_CSRF_EXEMPT_ENDPOINTS = (
    "messaging.whatsapp_webhook",
    "messaging.telegram_webhook",
)


def _wa_verify_token() -> Optional[str]:
    return os.getenv("WA_VERIFY_TOKEN")


def _wa_app_secret() -> Optional[str]:
    return os.getenv("WA_APP_SECRET")


def _telegram_webhook_secret() -> Optional[str]:
    return os.getenv("TELEGRAM_WEBHOOK_SECRET")


def _verify_meta_signature(raw_body: bytes, signature_header: str) -> bool:
    secret = _wa_app_secret()
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = (
        "sha256="
        + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)


def _telegram_secret_ok() -> bool:
    expected = _telegram_webhook_secret()
    if not expected:
        return True
    got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return hmac.compare_digest(got, expected)


def _user_id_for_whatsapp_phone_number_id(phone_number_id: Optional[str]) -> Optional[int]:
    if not phone_number_id:
        return None
    u = User.query.filter_by(whatsapp_phone_number_id=str(phone_number_id)).first()
    return u.id if u else None


def _user_id_for_telegram_fallback() -> Optional[int]:
    """Если в CRM один пользователь — привязываем Telegram к нему. Иначе user_id остаётся NULL."""
    if User.query.count() == 1:
        return User.query.first().id
    return None


def _log_incoming(channel: str, payload: Any) -> None:
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)[:4000]
    except Exception:
        text = str(payload)[:4000]
    current_app.logger.info("messaging.%s: %s", channel, text)


def _persist_whatsapp_payload(data: dict[str, Any]) -> None:
    entries = data.get("entry") or []
    for entry in entries:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            meta = value.get("metadata") or {}
            phone_number_id = meta.get("phone_number_id")
            if phone_number_id is not None:
                phone_number_id = str(phone_number_id)
            user_id = _user_id_for_whatsapp_phone_number_id(phone_number_id)

            for msg in value.get("messages") or []:
                from_wa = msg.get("from")
                if not from_wa:
                    continue
                text_body = (msg.get("text") or {}).get("body") or ""
                try:
                    raw = json.dumps(msg, ensure_ascii=False)[:20000]
                except Exception:
                    raw = "{}"
                row = InboundMessage(
                    user_id=user_id,
                    channel="whatsapp",
                    external_sender_id=str(from_wa),
                    external_chat_id=str(from_wa),
                    wa_phone_number_id=phone_number_id,
                    body=text_body,
                    raw_json=raw,
                )
                if user_id:
                    client = find_or_create_client_for_whatsapp(
                        user_id, str(from_wa)
                    )
                    row.client_id = client.id
                db.session.add(row)
    db.session.commit()


def _persist_telegram_update(data: dict[str, Any]) -> None:
    msg = data.get("message") or data.get("edited_message")
    if not isinstance(msg, dict):
        return

    chat = msg.get("chat") or {}
    from_user = (msg.get("from") or {}).get("id")
    if not from_user:
        return

    text_body = msg.get("text") or msg.get("caption") or ""
    if isinstance(text_body, list):
        text_body = ""
    if not isinstance(text_body, str):
        text_body = str(text_body)

    user_id = _user_id_for_telegram_fallback()
    chat_id = str(chat.get("id") or "")
    from_data = msg.get("from") or {}
    display_name = (from_data.get("first_name") or "").strip()
    last = from_data.get("last_name")
    if last:
        display_name = f"{display_name} {last}".strip()
    if not display_name:
        display_name = None

    try:
        raw = json.dumps(data, ensure_ascii=False)[:20000]
    except Exception:
        raw = "{}"

    row = InboundMessage(
        user_id=user_id,
        channel="telegram",
        external_sender_id=str(from_user),
        external_chat_id=chat_id,
        wa_phone_number_id=None,
        body=text_body,
        raw_json=raw,
    )
    if user_id and chat_id:
        client = find_or_create_client_for_telegram(
            user_id, chat_id, display_name=display_name
        )
        if not client.telegram_chat_id:
            client.telegram_chat_id = chat_id
        row.client_id = client.id
    db.session.add(row)
    db.session.commit()


@bp.route("/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        verify = _wa_verify_token()
        if (
            mode == "subscribe"
            and verify
            and token == verify
            and challenge is not None
        ):
            return challenge, 200, {"Content-Type": "text/plain; charset=utf-8"}
        abort(403)

    raw = request.get_data()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_meta_signature(raw, sig):
        abort(403)

    if not raw:
        data: dict[str, Any] = {}
    else:
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            abort(400)

    _log_incoming("whatsapp", data)

    try:
        _persist_whatsapp_payload(data)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("whatsapp persist failed")

    return jsonify({"status": "ok"}), 200


@bp.route("/telegram", methods=["POST"])
def telegram_webhook():
    if not _telegram_secret_ok():
        abort(403)

    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        abort(400)

    if not isinstance(data, dict):
        abort(400)

    _log_incoming("telegram", data)

    try:
        _persist_telegram_update(data)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("telegram persist failed")

    return jsonify({"ok": True}), 200
