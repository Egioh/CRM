"""Отчёты, сотрудники, админы, расходы."""

from app import app
from models import BusinessExpense, Client, Order, OrderExpense, Payment, Staff, User, db


def _register(client, email: str, password: str = "secret123"):
    client.post(
        "/register",
        data={
            "email": email,
            "password": password,
            "business_name": "Biz",
            "business_type": "salon",
            "business_description": "",
        },
        follow_redirects=True,
    )


def test_staff_and_order_assignee(client):
    _register(client, "owner1@test.com")
    r = client.post(
        "/staff",
        data={"name": "Anna", "role_title": "Master"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        owner = User.query.filter_by(email="owner1@test.com").first()
        st = Staff.query.filter_by(user_id=owner.id, name="Anna").first()
        assert st is not None
        staff_id = st.id
        c = Client(user_id=owner.id, name="C1")
        db.session.add(c)
        db.session.flush()
        order = Order(client_id=c.id, service="Cut", price=100.0)
        db.session.add(order)
        db.session.commit()
        oid = order.id

    client.post(
        f"/edit_order/{oid}",
        data={
            "service": "Cut",
            "price": "100",
            "date": "2025-06-01T10:00",
            "staff_id": str(staff_id),
            "notes": "",
        },
        follow_redirects=True,
    )
    with app.app_context():
        order = Order.query.get(oid)
        assert order.staff_id == staff_id


def test_admin_sees_owner_clients(client):
    _register(client, "owner2@test.com")
    with app.app_context():
        owner = User.query.filter_by(email="owner2@test.com").first()
        db.session.add(Client(user_id=owner.id, name="Shared"))
        db.session.commit()
        owner_id = owner.id

    client.post("/logout", follow_redirects=True)
    with app.app_context():
        owner = User.query.get(owner_id)
        admin = User(
            email="admin2@test.com",
            business_name=owner.business_name,
            business_type=owner.business_type,
            role="admin",
            owner_id=owner.id,
        )
        admin.set_password("adminpass")
        db.session.add(admin)
        db.session.commit()

    client.post(
        "/login",
        data={"email": "admin2@test.com", "password": "adminpass"},
        follow_redirects=True,
    )
    r = client.get("/")
    assert b"Shared" in r.data


def test_reports_page(client):
    _register(client, "owner3@test.com")
    with app.app_context():
        owner = User.query.filter_by(email="owner3@test.com").first()
        c = Client(user_id=owner.id, name="Pay")
        db.session.add(c)
        db.session.flush()
        db.session.add(Payment(client_id=c.id, amount=500.0, method="cash"))
        db.session.commit()

    r = client.get("/reports")
    assert r.status_code == 200
    assert b"500" in r.data or b"500.00" in r.data


def test_business_expense(client):
    _register(client, "owner4@test.com")
    client.post(
        "/expenses",
        data={"amount": "50", "description": "Rent"},
        follow_redirects=True,
    )
    with app.app_context():
        owner = User.query.filter_by(email="owner4@test.com").first()
        assert BusinessExpense.query.filter_by(user_id=owner.id).count() == 1


def test_reports_csv_export(client):
    _register(client, "owner_csv@test.com")
    r = client.get("/reports/export.csv")
    assert r.status_code == 200
    assert "text/csv" in r.content_type
    assert b"\xef\xbb\xbf" in r.data or b";" in r.data


def test_appointment_staff(client):
    _register(client, "owner_appt@test.com")
    client.post(
        "/staff",
        data={"name": "Master"},
        follow_redirects=True,
    )
    with app.app_context():
        from models import Appointment

        owner = User.query.filter_by(email="owner_appt@test.com").first()
        staff_id = Staff.query.filter_by(user_id=owner.id).first().id
        tenant_id = owner.id
        c = Client(user_id=owner.id, name="C")
        db.session.add(c)
        db.session.commit()
        cid = c.id

    client.post(
        "/appointment/new",
        data={
            "title": "Visit",
            "start_at": "2025-07-01T10:00",
            "end_at": "2025-07-01T11:00",
            "staff_id": str(staff_id),
            "client_id": str(cid),
        },
        follow_redirects=True,
    )
    with app.app_context():
        from models import Appointment

        ap = Appointment.query.filter_by(user_id=tenant_id).first()
        assert ap is not None
        assert ap.staff_id == staff_id


def test_order_expense(client):
    _register(client, "owner5@test.com")
    with app.app_context():
        owner = User.query.filter_by(email="owner5@test.com").first()
        c = Client(user_id=owner.id, name="X")
        db.session.add(c)
        db.session.flush()
        o = Order(client_id=c.id, service="S", price=10.0)
        db.session.add(o)
        db.session.commit()
        oid = o.id

    client.post(
        f"/order/{oid}/expense",
        data={"amount": "5", "description": "Materials"},
        follow_redirects=True,
    )
    with app.app_context():
        assert OrderExpense.query.filter_by(order_id=oid).count() == 1
