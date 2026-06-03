"""Unit tests: client_helpers."""

from __future__ import annotations

import pytest

from app import app
from client_helpers import (
    client_debt,
    has_unpaid_debt,
    payment_kind,
    payment_summary,
    payments_total,
    orders_total,
)
from models import Client, Order, Payment, db


@pytest.fixture
def client_with_orders():
    with app.app_context():
        from models import User

        u = User(
            email="ch@test.com",
            password_hash="x",
            business_name="B",
            business_type="T",
        )
        u.set_password("x")
        db.session.add(u)
        db.session.flush()
        c = Client(user_id=u.id, name="T")
        db.session.add(c)
        db.session.flush()
        db.session.add(Order(client_id=c.id, service="A", price=100.0))
        db.session.add(Order(client_id=c.id, service="B", price=50.0))
        db.session.add(Payment(client_id=c.id, amount=40.0, method="cash"))
        db.session.commit()
        yield c.id


@pytest.mark.unit
def test_orders_and_payments_totals(client_with_orders):
    with app.app_context():
        c = db.session.get(Client, client_with_orders)
        assert orders_total(c) == 150.0
        assert payments_total(c) == 40.0
        assert client_debt(c) == 110.0
        assert has_unpaid_debt(c) is True


@pytest.mark.unit
def test_payment_summary_states(client_with_orders):
    with app.app_context():
        c = db.session.get(Client, client_with_orders)
        assert payment_summary(c).startswith("Частично")
        assert payment_kind(payment_summary(c)) == "partial"

        c.payments[0].amount = 150.0
        assert payment_summary(c) == "Оплачен"
        assert payment_kind("Оплачен") == "paid"

        c.payments[0].amount = 0
        assert payment_summary(c) == "Не оплачен"
        assert payment_kind("Не оплачен") == "unpaid"

        c.orders = []
        assert payment_summary(c) == "—"
        assert payment_kind("—") == "none"
