"""RBAC: owner vs admin, owner-only routes."""

from __future__ import annotations

import pytest

from app import app
from models import Client, User, db
from tests.conftest_helpers import login_user, logout_user, register_user


@pytest.mark.security
def test_register_creates_owner_role(client):
    register_user(client, email="owner_rbac@test.com")
    with app.app_context():
        u = User.query.filter_by(email="owner_rbac@test.com").one()
        assert u.role == "owner"
        assert u.is_business_owner()
        assert u.tenant_id == u.id


@pytest.mark.security
def test_admin_tenant_id_points_to_owner(client):
    register_user(client, email="owner_t@test.com")
    with app.app_context():
        owner = User.query.filter_by(email="owner_t@test.com").one()
        admin = User(
            email="admin_t@test.com",
            business_name=owner.business_name,
            business_type=owner.business_type,
            role="admin",
            owner_id=owner.id,
        )
        admin.set_password("adminpass")
        db.session.add(admin)
        db.session.commit()
        assert admin.tenant_id == owner.id
        assert not admin.is_business_owner()

    logout_user(client, follow=True)
    login_user(client, "admin_t@test.com", "adminpass")
    with app.app_context():
        admin = User.query.filter_by(email="admin_t@test.com").one()
        assert admin.tenant_id == owner.id


@pytest.mark.security
def test_admin_blocked_from_integrations(client):
    register_user(client, email="own_int@test.com")
    with app.app_context():
        owner = User.query.filter_by(email="own_int@test.com").one()
        admin = User(
            email="adm_int@test.com",
            business_name=owner.business_name,
            business_type=owner.business_type,
            role="admin",
            owner_id=owner.id,
        )
        admin.set_password("ap")
        db.session.add(admin)
        db.session.commit()

    logout_user(client, follow=True)
    login_user(client, "adm_int@test.com", "ap")
    r = client.get("/integrations", follow_redirects=False)
    assert r.status_code == 302
    r2 = client.get("/integrations", follow_redirects=True)
    assert b"telegram" not in r2.data.lower() or r2.status_code != 200


@pytest.mark.security
def test_admin_blocked_from_admins_page(client):
    register_user(client, email="own_adm@test.com")
    with app.app_context():
        owner = User.query.filter_by(email="own_adm@test.com").one()
        admin = User(
            email="sub_adm@test.com",
            business_name=owner.business_name,
            business_type=owner.business_type,
            role="admin",
            owner_id=owner.id,
        )
        admin.set_password("ap")
        db.session.add(admin)
        db.session.commit()

    logout_user(client, follow=True)
    login_user(client, "sub_adm@test.com", "ap")
    r = client.get("/admins", follow_redirects=False)
    assert r.status_code == 302


@pytest.mark.security
def test_owner_can_create_sub_admin(client):
    register_user(client, email="boss@test.com")
    r = client.post(
        "/admins",
        data={"email": "worker@test.com", "password": "worker12"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        w = User.query.filter_by(email="worker@test.com").one()
        assert w.role == "admin"
        assert w.owner_id == User.query.filter_by(email="boss@test.com").one().id


@pytest.mark.security
def test_admin_password_change_by_owner(client):
    register_user(client, email="boss2@test.com")
    client.post(
        "/admins",
        data={"email": "worker2@test.com", "password": "oldpass1"},
        follow_redirects=True,
    )
    with app.app_context():
        aid = User.query.filter_by(email="worker2@test.com").one().id

    client.post(
        f"/admins/{aid}/password",
        data={"password": "newpass9"},
        follow_redirects=True,
    )
    logout_user(client, follow=True)
    login_user(client, "worker2@test.com", "newpass9")
    assert client.get("/").status_code == 200
