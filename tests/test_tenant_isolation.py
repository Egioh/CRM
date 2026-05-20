"""Изоляция данных: у каждого User свой набор клиентов и статусов."""

from __future__ import annotations

from app import app
from models import Client, ClientStatus, User


def _register(client, email, password="pw"):
    client.post(
        "/register",
        data={
            "email": email,
            "password": password,
            "business_name": f"Biz {email}",
            "business_type": "Другое",
            "business_description": "",
        },
        follow_redirects=True,
    )


def _logout(client):
    client.post("/logout", follow_redirects=False)


def test_each_user_gets_own_status_set_with_separate_ids(client):
    _register(client, "owner1@test.com")
    with app.app_context():
        u1 = User.query.filter_by(email="owner1@test.com").one()
        ids1 = {s.id for s in ClientStatus.query.filter_by(user_id=u1.id).all()}
        assert len(ids1) >= 8

    _logout(client)
    _register(client, "owner2@test.com")
    with app.app_context():
        u2 = User.query.filter_by(email="owner2@test.com").one()
        ids2 = {s.id for s in ClientStatus.query.filter_by(user_id=u2.id).all()}
        assert len(ids2) >= 8
        assert ids1.isdisjoint(ids2), "статусы разных пользователей не должны пересекаться по id"


def test_clients_and_statuses_isolated_between_users(client):
    _register(client, "a@test.com")
    with app.app_context():
        u_a = User.query.filter_by(email="a@test.com").one()
        st_a = ClientStatus.query.filter_by(user_id=u_a.id, name="Новый").one()
        sid_a = st_a.id

    client.post(
        "/add_client",
        data={
            "name": "Клиент A",
            "phone": "111",
            "email": "",
            "notes": "",
            "status_id": sid_a,
        },
        follow_redirects=True,
    )
    with app.app_context():
        cid_a = Client.query.filter_by(name="Клиент A").one().id

    _logout(client)
    _register(client, "b@test.com")
    with app.app_context():
        u_b = User.query.filter_by(email="b@test.com").one()
        st_b = ClientStatus.query.filter_by(user_id=u_b.id, name="Новый").one()
        sid_b = st_b.id
        assert sid_b != sid_a

    # Нельзя назначить чужой статус новому клиенту
    r = client.post(
        "/add_client",
        data={
            "name": "Клиент B",
            "phone": "222",
            "email": "",
            "notes": "",
            "status_id": sid_a,
        },
        follow_redirects=False,
    )
    assert r.status_code == 404

    client.post(
        "/add_client",
        data={
            "name": "Клиент B",
            "phone": "222",
            "email": "",
            "notes": "",
            "status_id": sid_b,
        },
        follow_redirects=True,
    )

    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "Клиент B".encode("utf-8") in r_index.data
    assert "Клиент A".encode("utf-8") not in r_index.data

    r_foreign = client.get(f"/client/{cid_a}")
    assert r_foreign.status_code == 404

    r_set = client.post(
        f"/client/{cid_a}/status",
        data={"status_id": sid_b},
        follow_redirects=False,
    )
    assert r_set.status_code == 404


def test_cannot_delete_other_users_status(client):
    _register(client, "x@test.com")
    with app.app_context():
        u_x = User.query.filter_by(email="x@test.com").one()
        sid_x = ClientStatus.query.filter_by(user_id=u_x.id).first().id

    _logout(client)
    _register(client, "y@test.com")

    assert client.post(f"/statuses/{sid_x}/delete", follow_redirects=False).status_code == 404


def test_status_filter_only_own_statuses(client):
    _register(client, "f1@test.com")
    with app.app_context():
        u1 = User.query.filter_by(email="f1@test.com").one()
        sid1 = ClientStatus.query.filter_by(user_id=u1.id).first().id

    _logout(client)
    _register(client, "f2@test.com")
    client.post(
        "/add_client",
        data={"name": "Only F2", "phone": "", "email": "", "notes": ""},
        follow_redirects=True,
    )

    r = client.get(f"/?status={sid1}")
    assert r.status_code == 200
    assert "Only F2".encode("utf-8") in r.data
