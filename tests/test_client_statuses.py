"""Статусы клиентов, комментарии, таблица на главной."""

from __future__ import annotations

from app import app
from models import Client, ClientComment, ClientStatus, User


def _register(client, email="st@test.com"):
    client.post(
        "/register",
        data={
            "email": email,
            "password": "pw",
            "business_name": "B",
            "business_type": "Другое",
            "business_description": "",
        },
        follow_redirects=True,
    )


def test_register_seeds_default_statuses(client):
    _register(client)
    with app.app_context():
        statuses = ClientStatus.query.join(User).filter(User.email == "st@test.com").all()
        assert len(statuses) >= 8
        names = {s.name for s in statuses}
        assert "Новый" in names
        assert "Оплачен" in names


def test_index_shows_table(client):
    _register(client)
    client.post(
        "/add_client",
        data={"name": "Таблица", "phone": "123", "email": "", "notes": ""},
        follow_redirects=True,
    )
    r = client.get("/")
    assert r.status_code == 200
    assert b"table" in r.data
    assert "Таблица".encode("utf-8") in r.data


def test_custom_status_and_comment(client):
    _register(client)
    client.post(
        "/statuses",
        data={"name": "На согласовании", "color": "info"},
        follow_redirects=True,
    )
    with app.app_context():
        st = ClientStatus.query.filter_by(name="На согласовании").one()
        sid = st.id
    client.post(
        "/add_client",
        data={
            "name": "Клиент",
            "phone": "",
            "email": "",
            "notes": "",
            "status_id": sid,
        },
        follow_redirects=True,
    )
    with app.app_context():
        c = Client.query.filter_by(name="Клиент").one()
        cid = c.id
        assert c.status_id == sid

    client.post(
        f"/client/{cid}/comment",
        data={"body": "Позвонил, ждёт смету"},
        follow_redirects=True,
    )
    with app.app_context():
        assert ClientComment.query.filter_by(client_id=cid).count() == 1
