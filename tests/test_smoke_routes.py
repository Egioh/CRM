"""Smoke: main routes respond for anonymous and authenticated users."""

from __future__ import annotations

import pytest

from tests.conftest_helpers import register_user

# (method, path, anonymous_expected, auth_min_expected)
_ROUTE_CASES = [
    ("GET", "/", 302, 200),
    ("GET", "/login", 200, 200),
    ("GET", "/register", 200, 200),
    ("GET", "/calendar", 302, 200),
    ("GET", "/statuses", 302, 200),
    ("GET", "/services", 302, 200),
    ("GET", "/inbox", 302, 200),
    ("GET", "/reports", 302, 200),
    ("GET", "/staff", 302, 200),
    ("GET", "/expenses", 302, 200),
    ("GET", "/integrations", 302, 200),  # owner: 200
    ("GET", "/admins", 302, 200),  # owner: 200
    ("GET", "/appointment/new", 302, 200),
    ("GET", "/add_client", 302, 200),
    ("GET", "/reports/export.csv", 302, 200),
    ("GET", "/help", 302, 200),
]


@pytest.mark.smoke
@pytest.mark.parametrize("method,path,anon_code,auth_code", _ROUTE_CASES)
def test_route_smoke(client, method, path, anon_code, auth_code):
    r = client.open(path, method=method, follow_redirects=False)
    assert r.status_code == anon_code

    safe = path.strip("/").replace("/", "_") or "root"
    register_user(client, email=f"smoke_{safe}@test.com")
    r2 = client.open(path, method=method, follow_redirects=False)
    assert r2.status_code == auth_code


@pytest.mark.smoke
def test_lang_switch_sets_cookie(client):
    r = client.get("/lang/en", headers={"Referer": "http://localhost/login"})
    assert r.status_code == 302
    assert r.headers.get("Set-Cookie", "").find("lang=en") >= 0


@pytest.mark.smoke
def test_browser_lang_default_czech(client):
    r = client.get("/login", headers={"Accept-Language": "cs-CZ,cs;q=0.9"})
    assert r.status_code == 200
    assert "Přihlášení".encode() in r.data


@pytest.mark.smoke
def test_browser_lang_cookie_overrides(client):
    client.set_cookie("lang", "en")
    r = client.get("/login", headers={"Accept-Language": "cs-CZ"})
    assert r.status_code == 200
    assert b"Sign in" in r.data or b"Log in" in r.data


@pytest.mark.smoke
def test_logout_post_only(client):
    register_user(client, email="smoke_logout@test.com")
    assert client.get("/logout").status_code == 405
