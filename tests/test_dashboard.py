"""Дашборд, долг и фильтр «только с долгом»."""

from __future__ import annotations

from app import app
from models import Client


def _register(client, email="dash@test.com"):
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


def test_dashboard_shows_stats(client):
    _register(client)
    r = client.get("/")
    assert r.status_code == 200
    assert "Всего клиентов".encode("utf-8") in r.data
    assert "С долгом".encode("utf-8") in r.data


def test_unpaid_filter_shows_only_debtors(client):
    _register(client)
    client.post(
        "/add_client",
        data={"name": "Должник", "phone": "", "email": "", "notes": ""},
        follow_redirects=True,
    )
    with app.app_context():
        cid = Client.query.filter_by(name="Должник").one().id
    client.post(
        f"/add_order/{cid}",
        data={"service": "Услуга", "price": "1000", "notes": ""},
        follow_redirects=True,
    )
    client.post(
        "/add_client",
        data={"name": "Без долга", "phone": "", "email": "", "notes": ""},
        follow_redirects=True,
    )

    r = client.get("/?unpaid=1")
    assert r.status_code == 200
    assert "Должник".encode("utf-8") in r.data
    assert "Без долга".encode("utf-8") not in r.data
    assert b"1000" in r.data or "\u20bd".encode("utf-8") in r.data


def test_appointment_from_client_card(client):
    _register(client)
    client.post(
        "/add_client",
        data={"name": "Запись", "phone": "", "email": "", "notes": ""},
        follow_redirects=True,
    )
    with app.app_context():
        cid = Client.query.filter_by(name="Запись").one().id
    r = client.get(f"/appointment/new?client_id={cid}")
    assert r.status_code == 200
    assert b'value="' + str(cid).encode() + b'"' in r.data or str(cid).encode() in r.data
