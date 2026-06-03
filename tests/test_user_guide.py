"""Страница инструкции и переводы."""

from tests.conftest_helpers import register_user


def test_user_guide_requires_login(client):
    r = client.get("/help", follow_redirects=False)
    assert r.status_code == 302


def test_user_guide_ru(client):
    register_user(client, email="guide_user@test.com")
    r = client.get("/help")
    assert r.status_code == 200
    assert "guide.intro.p1".encode() not in r.data
    assert "notebook".encode() in r.data or "запис".encode() in r.data


def test_user_guide_en_cookie(client):
    register_user(client, email="guide_en@test.com")
    client.get("/lang/en")
    r = client.get("/help")
    assert r.status_code == 200
    assert b"Getting started" in r.data or b"Clients section" in r.data


def test_user_guide_owner_section(client):
    register_user(client, email="guide_owner@test.com")
    r = client.get("/help")
    assert b"owner" in r.data.lower() or "владел".encode() in r.data.lower()
