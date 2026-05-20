"""
Integration tests for CRM Flask app: auth, clients, orders, payments, AI stub, CSRF.
"""

from __future__ import annotations

import re
import pytest

from app import _parse_positive_float, app
from models import Client, Order, Payment, User


def _csrf_from_html(html: str) -> str:
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html, re.I)
    if not m:
        m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html, re.I)
    assert m, f"csrf token not found in HTML snippet: {html[:400]!r}"
    return m.group(1)


def register(client, email="a@example.com", password="secret123", follow=True):
    return client.post(
        "/register",
        data={
            "email": email,
            "password": password,
            "business_name": "Test Biz",
            "business_type": "Другое",
            "business_description": "Test description",
        },
        follow_redirects=follow,
    )


def login(client, email="a@example.com", password="secret123", follow=True):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=follow,
    )


def logout(client, follow=True):
    return client.post("/logout", follow_redirects=follow)


class TestAuthAndGuards:
    def test_index_redirects_when_anonymous(self, client):
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers.get("Location", "")

    def test_register_get(self, client):
        r = client.get("/register")
        assert r.status_code == 200

    def test_register_post_creates_user_and_redirects(self, client):
        r = register(client)
        assert r.status_code == 200
        assert b"Test Biz" in r.data or b"\xd0\x9a\xd0\xbb\xd0\xb8\xd0\xb5\xd0\xbd\xd1\x82" in r.data

        with app.app_context():
            u = User.query.filter_by(email="a@example.com").one()
            assert u.check_password("secret123")

    def test_register_duplicate_email(self, client):
        register(client)
        r = client.post(
            "/register",
            data={
                "email": "a@example.com",
                "password": "x",
                "business_name": "B2",
                "business_type": "Другое",
                "business_description": "",
            },
        )
        assert r.status_code == 200
        assert "уже существует".encode("utf-8") in r.data

    def test_login_get(self, client):
        assert client.get("/login").status_code == 200

    def test_login_wrong_password(self, client):
        register(client)
        r = login(client, password="wrong", follow=False)
        assert r.status_code == 200
        assert "Неверный".encode("utf-8") in r.data

    def test_login_success(self, client):
        register(client)
        r = login(client, follow=False)
        assert r.status_code == 302
        assert r.headers.get("Location", "").endswith("/")

    def test_logout_requires_post(self, client):
        register(client)
        assert client.get("/logout").status_code == 405

    def test_logout_anonymous_redirects(self, client):
        r = client.post("/logout", follow_redirects=False)
        assert r.status_code == 302

    def test_logout_success(self, client):
        register(client)
        r = logout(client, follow=False)
        assert r.status_code == 302
        assert "/login" in r.headers.get("Location", "")


class TestClientsOrdersPayments:
    @pytest.fixture
    def logged_in(self, client):
        register(client)
        return client

    def test_add_client_get_post(self, logged_in):
        r = logged_in.get("/add_client")
        assert r.status_code == 200
        r2 = logged_in.post(
            "/add_client",
            data={
                "name": "Иван",
                "phone": "+7999",
                "email": "ivan@test.com",
                "notes": "note",
            },
            follow_redirects=True,
        )
        assert r2.status_code == 200
        with app.app_context():
            c = Client.query.filter_by(name="Иван").one()
            assert c.phone == "+7999"

    def test_client_detail_and_404(self, logged_in):
        logged_in.post(
            "/add_client",
            data={"name": "P", "phone": "", "email": "", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.one().id
        assert logged_in.get(f"/client/{cid}").status_code == 200
        assert logged_in.get("/client/99999").status_code == 404

    def test_edit_client(self, logged_in):
        logged_in.post(
            "/add_client",
            data={"name": "Old", "phone": "1", "email": "e@e.com", "notes": "n"},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.one().id
        r = logged_in.get(f"/edit_client/{cid}")
        assert r.status_code == 200
        logged_in.post(
            f"/edit_client/{cid}",
            data={
                "name": "New",
                "phone": "2",
                "email": "e2@e.com",
                "notes": "n2",
            },
            follow_redirects=True,
        )
        with app.app_context():
            c = Client.query.get(cid)
            assert c.name == "New"
            assert c.phone == "2"

    def test_add_order_and_invalid_price(self, logged_in):
        logged_in.post(
            "/add_client",
            data={"name": "C", "phone": "", "email": "", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.one().id
        r_ok = logged_in.post(
            f"/add_order/{cid}",
            data={"service": "Cut", "price": "100.5", "notes": "x"},
            follow_redirects=False,
        )
        assert r_ok.status_code == 302
        with app.app_context():
            assert Order.query.count() == 1

        r_bad = logged_in.post(
            f"/add_order/{cid}",
            data={"service": "Bad", "price": "not-a-number", "notes": ""},
            follow_redirects=False,
        )
        assert r_bad.status_code == 302
        with app.app_context():
            assert Order.query.count() == 1

    def test_edit_delete_order(self, logged_in):
        logged_in.post(
            "/add_client",
            data={"name": "C", "phone": "", "email": "", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.one().id
        logged_in.post(
            f"/add_order/{cid}",
            data={"service": "S", "price": "10", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            oid = Order.query.one().id
            od = Order.query.get(oid)
            date_str = od.date.strftime("%Y-%m-%dT%H:%M")

        assert logged_in.get(f"/edit_order/{oid}").status_code == 200
        logged_in.post(
            f"/edit_order/{oid}",
            data={
                "service": "S2",
                "price": "20",
                "notes": "nn",
                "date": date_str,
            },
            follow_redirects=True,
        )
        with app.app_context():
            assert Order.query.get(oid).service == "S2"
            assert Order.query.get(oid).price == 20.0

        logged_in.post(f"/delete_order/{oid}", follow_redirects=True)
        with app.app_context():
            assert Order.query.count() == 0

    def test_add_payment_invalid_amount(self, logged_in):
        logged_in.post(
            "/add_client",
            data={"name": "C", "phone": "", "email": "", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.one().id
        logged_in.post(
            f"/add_payment/{cid}",
            data={"amount": "50", "method": "cash", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            assert Payment.query.count() == 1

        logged_in.post(
            f"/add_payment/{cid}",
            data={"amount": "-1", "method": "cash", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            assert Payment.query.count() == 1

    def test_edit_delete_payment(self, logged_in):
        logged_in.post(
            "/add_client",
            data={"name": "C", "phone": "", "email": "", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.one().id
        logged_in.post(
            f"/add_payment/{cid}",
            data={"amount": "100", "method": "card", "notes": "p"},
            follow_redirects=True,
        )
        with app.app_context():
            pid = Payment.query.one().id
            p = Payment.query.get(pid)
            date_str = p.date.strftime("%Y-%m-%dT%H:%M")

        assert logged_in.get(f"/edit_payment/{pid}").status_code == 200
        logged_in.post(
            f"/edit_payment/{pid}",
            data={
                "amount": "200",
                "method": "transfer",
                "notes": "p2",
                "date": date_str,
            },
            follow_redirects=True,
        )
        with app.app_context():
            assert Payment.query.get(pid).amount == 200.0

        logged_in.post(f"/delete_payment/{pid}", follow_redirects=True)
        with app.app_context():
            assert Payment.query.count() == 0

    def test_delete_client(self, logged_in):
        logged_in.post(
            "/add_client",
            data={"name": "X", "phone": "", "email": "", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.one().id
        logged_in.post(f"/delete_client/{cid}", follow_redirects=True)
        with app.app_context():
            assert Client.query.count() == 0

    def test_delete_routes_reject_get(self, logged_in):
        logged_in.post(
            "/add_client",
            data={"name": "Y", "phone": "", "email": "", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.one().id
        logged_in.post(
            f"/add_order/{cid}",
            data={"service": "S", "price": "1", "notes": ""},
            follow_redirects=True,
        )
        logged_in.post(
            f"/add_payment/{cid}",
            data={"amount": "1", "method": "cash", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            oid = Order.query.one().id
            pid = Payment.query.one().id

        assert logged_in.get(f"/delete_order/{oid}").status_code == 405
        assert logged_in.get(f"/delete_payment/{pid}").status_code == 405
        assert logged_in.get(f"/delete_client/{cid}").status_code == 405


class TestIsolationTwoUsers:
    def test_other_user_cannot_access_client(self, client):
        register(client, email="u1@test.com", password="p1")
        client.post(
            "/add_client",
            data={"name": "Secret", "phone": "", "email": "", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            cid = Client.query.filter_by(name="Secret").one().id
        client.post(
            f"/add_order/{cid}",
            data={"service": "S", "price": "10", "notes": ""},
            follow_redirects=True,
        )
        client.post(
            f"/add_payment/{cid}",
            data={"amount": "5", "method": "cash", "notes": ""},
            follow_redirects=True,
        )
        with app.app_context():
            oid = Order.query.filter_by(client_id=cid).one().id
            pid = Payment.query.filter_by(client_id=cid).one().id

        logout(client)
        register(client, email="u2@test.com", password="p2")

        assert client.get(f"/client/{cid}").status_code == 404
        assert client.post(f"/add_order/{cid}", data={"service": "x", "price": "1"}).status_code == 404
        assert client.post(f"/delete_client/{cid}").status_code == 404
        assert client.get(f"/edit_client/{cid}").status_code == 404
        assert client.get(f"/edit_order/{oid}").status_code == 404
        assert client.get(f"/edit_payment/{pid}").status_code == 404
        assert client.post(
            f"/add_payment/{cid}",
            data={"amount": "1", "method": "cash"},
        ).status_code == 404

class TestHelpers:
    def test_parse_positive_float(self):
        with app.test_request_context("/"):
            assert _parse_positive_float("10.5", "x") == 10.5
            assert _parse_positive_float("-1", "x") is None
            assert _parse_positive_float("bad", "x") is None


class TestCsrf:
    def test_post_register_without_token_fails(self, client_csrf):
        r = client_csrf.post(
            "/register",
            data={
                "email": "csrf@test.com",
                "password": "p",
                "business_name": "B",
                "business_type": "Другое",
                "business_description": "",
            },
        )
        assert r.status_code == 400

    def test_post_register_with_token_succeeds(self, client_csrf):
        page = client_csrf.get("/register")
        token = _csrf_from_html(page.get_data(as_text=True))
        r = client_csrf.post(
            "/register",
            data={
                "csrf_token": token,
                "email": "csrfok@test.com",
                "password": "p",
                "business_name": "B",
                "business_type": "Другое",
                "business_description": "",
            },
            follow_redirects=False,
        )
        assert r.status_code == 302
