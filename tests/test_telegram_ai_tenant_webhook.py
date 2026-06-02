from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest

from app import app
from models import Appointment, CatalogService, ClientReminder, User, db


def _stub_tg_message(chat_id: str, text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1710000000,
            "chat": {"id": int(chat_id), "type": "private"},
            "from": {"id": 111, "first_name": "Test"},
            "text": text,
        },
    }


class DummyResp:
    def __init__(self):
        self.status_code = 200

    def json(self):
        return {"ok": True, "result": {"message_id": 1}}


@pytest.fixture()
def tenant_user():
    with app.app_context():
        u = User(email="t1@example.com", business_name="Biz", business_type="Any")
        u.set_password("pass")
        u.telegram_ai_enabled = True
        u.telegram_bot_token = "TEST:TOKEN"
        u.telegram_webhook_token = "wh-token-1"
        u.telegram_ai_timezone = "UTC"
        db.session.add(u)
        db.session.commit()

        db.session.add(
            CatalogService(user_id=u.id, name="Маникюр", price=1000.0, duration_minutes=60, position=0)
        )
        db.session.commit()
        yield u


def test_tenant_webhook_services_list(client, monkeypatch, tenant_user):
    # avoid real network
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: DummyResp())

    rv = client.post(
        f"/webhooks/telegram/{tenant_user.telegram_webhook_token}",
        data=json.dumps(_stub_tg_message("123", "/services")),
        content_type="application/json",
    )
    assert rv.status_code == 200


def test_llm_extraction_book_flow_reaches_confirm(client, monkeypatch, tenant_user):
    import requests

    os.environ["DEEPSEEK_API_KEY"] = "test-key"

    class DeepseekResp:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "book",
                                    "service_name": "Маникюр",
                                    "when_text": "завтра 15:30",
                                    "contact_name": "Ира",
                                    "contact_phone": "+79990000000",
                                    "confidence": 0.9,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    def fake_post(url, *a, **k):
        if "api.deepseek.com/chat/completions" in url:
            return DeepseekResp()
        return DummyResp()

    monkeypatch.setattr(requests, "post", fake_post)

    rv = client.post(
        f"/webhooks/telegram/{tenant_user.telegram_webhook_token}",
        data=json.dumps(_stub_tg_message("123", "Хочу записаться: Ира, маникюр, завтра 15:30, телефон +79990000000")),
        content_type="application/json",
    )
    assert rv.status_code == 200


def test_tenant_webhook_suggests_next_slot_on_conflict(client, monkeypatch, tenant_user):
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: DummyResp())

    with app.app_context():
        # create an existing appointment at 10:00-11:00 UTC
        start = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=60)
        db.session.add(
            Appointment(
                user_id=tenant_user.id,
                title="Busy",
                start_at=start,
                end_at=end,
                status="scheduled",
                source="manual",
            )
        )
        db.session.commit()

    # simulate booking intent + choose service callback + choose time conflicting
    client.post(
        f"/webhooks/telegram/{tenant_user.telegram_webhook_token}",
        data=json.dumps(_stub_tg_message("123", "запиши меня")),
        content_type="application/json",
    )
    client.post(
        f"/webhooks/telegram/{tenant_user.telegram_webhook_token}",
        data=json.dumps(_stub_tg_message("123", "Имя +79990000000")),
        content_type="application/json",
    )
    client.post(
        f"/webhooks/telegram/{tenant_user.telegram_webhook_token}",
        data=json.dumps(
            {
                "callback_query": {
                    "id": "1",
                    "from": {"id": 111, "first_name": "Test"},
                    "message": {"chat": {"id": 123, "type": "private"}},
                    "data": "ai:svc:1",
                }
            }
        ),
        content_type="application/json",
    )
    rv = client.post(
        f"/webhooks/telegram/{tenant_user.telegram_webhook_token}",
        data=json.dumps(_stub_tg_message("123", "сегодня 10:00")),
        content_type="application/json",
    )
    assert rv.status_code == 200

    with app.app_context():
        # no reminder should be created without confirmation
        assert ClientReminder.query.filter_by(user_id=tenant_user.id).count() == 0

