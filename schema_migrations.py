"""Одноразовые правки схемы SQLite (новые колонки без Alembic)."""

from __future__ import annotations

from sqlalchemy import inspect, text

from models import Appointment, Client, InboundMessage, User, db


def _sqlite_add_column_if_missing(app, table: str, column: str, ddl: str) -> None:
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    if not uri.startswith("sqlite:"):
        return
    try:
        insp = inspect(db.engine)
        existing = {c["name"] for c in insp.get_columns(table)}
        if column in existing:
            return
        with db.engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    except Exception:
        app.logger.exception("sqlite migration failed: %s.%s", table, column)


def apply_sqlite_user_whatsapp_column(app) -> None:
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").lower()
    if not uri.startswith("sqlite:"):
        return
    try:
        insp = inspect(db.engine)
        t = User.__table__.name
        existing = {c["name"] for c in insp.get_columns(t)}
        if "whatsapp_phone_number_id" in existing:
            return
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"ALTER TABLE {t} ADD COLUMN whatsapp_phone_number_id VARCHAR(64)"
                )
            )
    except Exception:
        app.logger.exception("apply_sqlite_user_whatsapp_column failed")


def apply_sqlite_client_status_id(app) -> None:
    _sqlite_add_column_if_missing(
        app,
        Client.__table__.name,
        "status_id",
        "status_id INTEGER",
    )


def apply_sqlite_client_telegram_chat_id(app) -> None:
    _sqlite_add_column_if_missing(
        app,
        Client.__table__.name,
        "telegram_chat_id",
        "telegram_chat_id VARCHAR(64)",
    )


def apply_sqlite_inbound_client_id(app) -> None:
    _sqlite_add_column_if_missing(
        app,
        InboundMessage.__table__.name,
        "client_id",
        "client_id INTEGER",
    )


def apply_sqlite_appointment_catalog_columns(app) -> None:
    t = Appointment.__table__.name
    _sqlite_add_column_if_missing(app, t, "catalog_service_id", "catalog_service_id INTEGER")
    _sqlite_add_column_if_missing(app, t, "price", "price FLOAT")
    _sqlite_add_column_if_missing(
        app, t, "recurrence_series_id", "recurrence_series_id VARCHAR(36)"
    )
    _sqlite_add_column_if_missing(app, t, "recurrence_rule", "recurrence_rule VARCHAR(20)")


def apply_all_sqlite_migrations(app) -> None:
    apply_sqlite_user_whatsapp_column(app)
    apply_sqlite_client_status_id(app)
    apply_sqlite_client_telegram_chat_id(app)
    apply_sqlite_inbound_client_id(app)
    apply_sqlite_appointment_catalog_columns(app)
