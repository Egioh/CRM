"""
Pytest configuration: in-memory DB and test-friendly Flask settings.

DATABASE_URL and SECRET_KEY must be set before `app` is imported.
"""

from __future__ import annotations

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "pytest-secret-key"

from app import app, db  # noqa: E402

pytest_plugins: tuple[str, ...] = ()


@pytest.fixture(autouse=True)
def _fresh_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        from schema_migrations import apply_all_sqlite_migrations

        apply_all_sqlite_migrations(app)
    yield
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


@pytest.fixture
def client_csrf():
    """Client with CSRF enabled (default app behaviour)."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    with app.test_client() as c:
        yield c
