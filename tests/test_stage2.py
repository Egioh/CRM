"""Этап 2: привязка inbox, напоминания, история статусов."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from models import Client, ClientReminder, ClientStatusHistory, InboundMessage, User, db


def _register(client, email="u@t.com"):
    client.post(
        "/register",
        data={
            "email": email,
            "password": "pass12345",
            "business_name": "Biz",
            "business_type": "salon",
            "business_description": "",
        },
        follow_redirects=True,
    )


def test_whatsapp_creates_and_links_client(client):
    _register(client, "wa@t.com")
    with client.application.app_context():
        u = User.query.filter_by(email="wa@t.com").first()
        u.whatsapp_phone_number_id = "pn-123"
        user_id = u.id
        db.session.commit()

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "pn-123"},
                            "messages": [
                                {
                                    "from": "79001234567",
                                    "text": {"body": "Привет"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    r = client.post(
        "/webhooks/whatsapp",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert r.status_code == 200

    with client.application.app_context():
        msg = InboundMessage.query.filter_by(channel="whatsapp").first()
        assert msg is not None
        assert msg.client_id is not None
        c = Client.query.get(msg.client_id)
        assert c.user_id == user_id
        assert "79001234567" in (c.phone or "")


def test_status_change_writes_history(client):
    _register(client, "hist@t.com")
    client.post(
        "/add_client",
        data={"name": "A", "phone": "", "email": "", "notes": ""},
        follow_redirects=True,
    )
    with client.application.app_context():
        c = Client.query.filter_by(name="A").first()
        statuses = list(c.user.client_statuses)
        new_id = statuses[1].id if len(statuses) > 1 else statuses[0].id

    client.post(
        f"/client/{c.id}/status",
        data={"status_id": new_id},
        follow_redirects=True,
    )

    with client.application.app_context():
        hist = ClientStatusHistory.query.filter_by(client_id=c.id).all()
        assert len(hist) >= 1
        assert hist[0].new_status_id == new_id


def test_reminder_on_dashboard(client):
    _register(client, "rem@t.com")
    client.post(
        "/add_client",
        data={"name": "B", "phone": "", "email": "", "notes": ""},
        follow_redirects=True,
    )
    with client.application.app_context():
        c = Client.query.filter_by(name="B").first()
        today = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
        db.session.add(
            ClientReminder(
                user_id=c.user_id,
                client_id=c.id,
                due_at=today,
                body="Перезвонить",
            )
        )
        db.session.commit()
        cid = c.id

    r = client.get("/")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "home-stats-panel" in html
    assert "B" in html

    client.post(f"/reminder/{ClientReminder.query.first().id}/done", follow_redirects=True)
    with client.application.app_context():
        rem = ClientReminder.query.filter_by(client_id=cid).first()
        assert rem.done is True
