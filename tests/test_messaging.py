"""Вебхуки Telegram / WhatsApp (без CSRF, публичные URL)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest


def test_whatsapp_get_verify_success(client, monkeypatch):
    monkeypatch.setenv("WA_VERIFY_TOKEN", "my-verify")
    r = client.get(
        "/webhooks/whatsapp",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": "my-verify",
            "hub.challenge": "999888",
        },
    )
    assert r.status_code == 200
    assert r.data == b"999888"


def test_whatsapp_get_verify_wrong_token(client, monkeypatch):
    monkeypatch.setenv("WA_VERIFY_TOKEN", "expected")
    r = client.get(
        "/webhooks/whatsapp",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "1",
        },
    )
    assert r.status_code == 403


def test_whatsapp_post_without_app_secret_accepts_json(client):
    r = client.post(
        "/webhooks/whatsapp",
        data=json.dumps({"object": "whatsapp_business_account", "entry": []}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_whatsapp_post_with_app_secret_requires_signature(client, monkeypatch):
    monkeypatch.setenv("WA_APP_SECRET", "meta-secret")
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    r = client.post(
        "/webhooks/whatsapp",
        data=body,
        content_type="application/json",
    )
    assert r.status_code == 403

    sig = (
        "sha256="
        + hmac.new(b"meta-secret", body, hashlib.sha256).hexdigest()
    )
    r2 = client.post(
        "/webhooks/whatsapp",
        data=body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": sig},
    )
    assert r2.status_code == 200


def test_telegram_post_requires_secret_when_configured(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "tg-secret")
    r = client.post(
        "/webhooks/telegram",
        data=json.dumps({"update_id": 1}),
        content_type="application/json",
    )
    assert r.status_code == 403

    r2 = client.post(
        "/webhooks/telegram",
        data=json.dumps({"update_id": 1}),
        content_type="application/json",
        headers={"X-Telegram-Bot-Api-Secret-Token": "tg-secret"},
    )
    assert r2.status_code == 200
    assert r2.get_json() == {"ok": True}


def test_webhook_posts_do_not_require_csrf_token(client_csrf, monkeypatch):
    monkeypatch.delenv("WA_APP_SECRET", raising=False)
    r = client_csrf.post(
        "/webhooks/whatsapp",
        data="{}",
        content_type="application/json",
    )
    assert r.status_code == 200
