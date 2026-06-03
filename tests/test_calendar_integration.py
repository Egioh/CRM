"""Календарь, входящие, интеграции и сохранение WhatsApp в InboundMessage."""

from __future__ import annotations

import json

from app import app, db
from models import Appointment, InboundMessage, User


def _register(client, email="cal@test.com", password="pw"):
    client.post(
        "/register",
        data={
            "email": email,
            "password": password,
            "business_name": "B",
            "business_type": "Другое",
            "business_description": "",
        },
        follow_redirects=True,
    )


def test_integrations_saves_whatsapp_phone_number_id(client):
    _register(client)
    client.post(
        "/integrations",
        data={"whatsapp_phone_number_id": "PN123"},
        follow_redirects=True,
    )
    with app.app_context():
        assert User.query.filter_by(email="cal@test.com").one().whatsapp_phone_number_id == "PN123"


def test_whatsapp_webhook_persists_inbound_for_owner(client, monkeypatch):
    monkeypatch.delenv("WA_APP_SECRET", raising=False)
    _register(client)
    client.post(
        "/integrations",
        data={"whatsapp_phone_number_id": "PN999"},
        follow_redirects=True,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "PN999"},
                            "messages": [
                                {
                                    "from": "79991234567",
                                    "type": "text",
                                    "text": {"body": "Здравствуйте"},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    r = client.post(
        "/webhooks/whatsapp",
        data=body,
        content_type="application/json",
    )
    assert r.status_code == 200
    with app.app_context():
        m = InboundMessage.query.one()
        assert m.channel == "whatsapp"
        assert m.body == "Здравствуйте"
        assert m.user_id == User.query.filter_by(email="cal@test.com").one().id


def test_appointment_create_and_overlap(client):
    _register(client)
    client.post(
        "/appointment/new",
        data={
            "title": "Визит",
            "client_id": "",
            "start_at": "2030-01-15T10:00",
            "end_at": "2030-01-15T11:00",
            "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        assert Appointment.query.count() == 1

    r = client.post(
        "/appointment/new",
        data={
            "title": "Другой",
            "client_id": "",
            "start_at": "2030-01-15T10:30",
            "end_at": "2030-01-15T11:30",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "уже есть".encode("utf-8") in r.data
    with app.app_context():
        assert Appointment.query.count() == 1


def test_appointment_edit(client):
    _register(client, email="edit@test.com")
    client.post(
        "/appointment/new",
        data={
            "title": "Стрижка",
            "client_id": "",
            "start_at": "2030-05-10T14:00",
            "end_at": "2030-05-10T15:00",
            "notes": "было",
        },
        follow_redirects=True,
    )
    with app.app_context():
        ap = Appointment.query.one()
        aid = ap.id
        cid = ap.client_id

    r = client.post(
        f"/appointment/{aid}/edit",
        data={
            "title": "Стрижка + укладка",
            "client_id": cid or "",
            "start_at": "2030-05-10T16:00",
            "end_at": "2030-05-10T17:00",
            "notes": "стало",
            "status": "scheduled",
            "return_to": "calendar",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        updated = Appointment.query.get(aid)
        assert updated.title == "Стрижка + укладка"
        assert updated.notes == "стало"
        assert updated.start_at.hour == 16


def test_appointment_cancel(client):
    _register(client, email="c2@test.com")
    client.post(
        "/appointment/new",
        data={
            "title": "X",
            "client_id": "",
            "start_at": "2030-02-01T09:00",
            "end_at": "2030-02-01T10:00",
            "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        aid = Appointment.query.one().id
    client.post(f"/appointment/{aid}/cancel", follow_redirects=True)
    with app.app_context():
        assert Appointment.query.get(aid).status == "cancelled"


def test_appointment_delete(client):
    _register(client, email="del@test.com")
    client.post(
        "/appointment/new",
        data={
            "title": "Удалить",
            "client_id": "",
            "start_at": "2030-03-01T09:00",
            "end_at": "2030-03-01T10:00",
            "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        aid = Appointment.query.one().id
    r = client.post(f"/appointment/{aid}/delete", follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert Appointment.query.get(aid) is None


def test_appointment_delete_rejects_get(client):
    _register(client, email="del2@test.com")
    client.post(
        "/appointment/new",
        data={
            "title": "T",
            "client_id": "",
            "start_at": "2030-04-01T09:00",
            "end_at": "2030-04-01T10:00",
            "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        aid = Appointment.query.one().id
    assert client.get(f"/appointment/{aid}/delete").status_code == 405


def test_inbox_requires_login(client):
    assert client.get("/inbox", follow_redirects=False).status_code == 302
