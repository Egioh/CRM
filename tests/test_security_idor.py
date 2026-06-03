"""IDOR: users cannot access another tenant's resources."""

from __future__ import annotations

import pytest

from app import app
from models import Client, Order, Payment, Staff, User, db
from tests.conftest_helpers import logout_user, register_user


def _setup_tenant_a(client) -> dict[str, int]:
    register_user(client, email="tenant_a@test.com", business_name="A")
    with app.app_context():
        user_a = User.query.filter_by(email="tenant_a@test.com").one()
        ca = Client(user_id=user_a.id, name="ClientA")
        db.session.add(ca)
        db.session.flush()
        oa = Order(client_id=ca.id, service="S", price=10.0)
        pa = Payment(client_id=ca.id, amount=5.0, method="c")
        sa = Staff(user_id=user_a.id, name="StA")
        db.session.add_all([oa, pa, sa])
        db.session.flush()
        ids = {"client": ca.id, "order": oa.id, "payment": pa.id, "staff": sa.id}
        db.session.commit()
        return ids


@pytest.mark.security
def test_cannot_view_other_tenant_client(client):
    ids_a = _setup_tenant_a(client)
    logout_user(client, follow=True)
    register_user(client, email="tenant_b@test.com", business_name="B")
    assert client.get(f"/client/{ids_a['client']}").status_code == 404


@pytest.mark.security
def test_cannot_edit_other_tenant_order(client):
    ids_a = _setup_tenant_a(client)
    logout_user(client, follow=True)
    register_user(client, email="tenant_b2@test.com", business_name="B")
    assert client.get(f"/edit_order/{ids_a['order']}").status_code == 404


@pytest.mark.security
def test_cannot_delete_other_tenant_staff(client):
    ids_a = _setup_tenant_a(client)
    logout_user(client, follow=True)
    register_user(client, email="tenant_b3@test.com", business_name="B")
    r = client.post(f"/staff/{ids_a['staff']}/delete", follow_redirects=False)
    assert r.status_code in (302, 404)


@pytest.mark.security
def test_cannot_add_order_to_other_tenant_client(client):
    ids_a = _setup_tenant_a(client)
    logout_user(client, follow=True)
    register_user(client, email="tenant_b4@test.com", business_name="B")
    client.post(
        f"/add_order/{ids_a['client']}",
        data={"service": "Hack", "price": "1", "notes": ""},
        follow_redirects=True,
    )
    with app.app_context():
        b = User.query.filter_by(email="tenant_b4@test.com").one()
        assert Order.query.join(Client).filter(Client.user_id == b.id).count() == 0
