"""Shared auth helpers for tests."""

from __future__ import annotations

from app import app
from models import User


def register_user(
    client,
    email: str = "user@test.com",
    password: str = "secret123",
    business_name: str = "Test Biz",
    *,
    follow: bool = True,
):
    return client.post(
        "/register",
        data={
            "email": email,
            "password": password,
            "business_name": business_name,
            "business_type": "Другое",
            "business_description": "",
        },
        follow_redirects=follow,
    )


def login_user(
    client,
    email: str = "user@test.com",
    password: str = "secret123",
    *,
    follow: bool = True,
):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=follow,
    )


def logout_user(client, *, follow: bool = True):
    return client.post("/logout", follow_redirects=follow)


def user_by_email(email: str) -> User:
    with app.app_context():
        return User.query.filter_by(email=email).one()
