"""Unit tests: i18n, phone, appointment helpers, migrate row prep."""

from __future__ import annotations

from datetime import datetime

import pytest

from appointment_helpers import build_recurrence_starts, recurrence_label
from i18n import (
    detect_lang_from_accept_language,
    get_calendar_locale,
    html_lang_code,
    normalize_lang,
    resolve_lang,
    translate,
    translate_named,
    translate_outbound_message,
    translate_payment_label,
    translate_stored_note,
)
from phone_utils import normalize_phone_digits, phones_match
from scripts.migrate_sqlite_to_postgres import _prepare_row


@pytest.mark.unit
def test_normalize_lang():
    assert normalize_lang("cs") == "cz"
    assert normalize_lang("en") == "en"
    assert normalize_lang(None) == "ru"


@pytest.mark.unit
def test_html_lang_code():
    assert html_lang_code("ru") == "ru"
    assert html_lang_code("cz") == "cs"
    assert html_lang_code("cs") == "cs"


@pytest.mark.unit
def test_resolve_lang():
    assert resolve_lang("en", "cs-CZ") == "en"
    assert resolve_lang(None, "cs-CZ,cs") == "cz"
    assert resolve_lang(None, "en-US,en;q=0.9") == "en"
    assert resolve_lang(None, "de-DE") == "ru"
    assert resolve_lang("", "en") == "en"


@pytest.mark.unit
def test_parse_date_only():
    from app import _parse_date_only

    assert _parse_date_only("2026-06-02").isoformat() == "2026-06-02"
    assert _parse_date_only("02.06.2026").isoformat() == "2026-06-02"
    assert _parse_date_only("02/06/2026").isoformat() == "2026-06-02"
    assert _parse_date_only("bad") is None


@pytest.mark.unit
def test_translate_outbound_message():
    assert "Telegram" in translate_outbound_message("en", "Сообщение отправлено в Telegram")
    assert translate_outbound_message("en", "WhatsApp API: err").startswith("WhatsApp API:")


@pytest.mark.unit
def test_translate_en():
    assert translate("en", "Клиенты") == "Clients"
    assert translate("ru", "Клиенты") == "Клиенты"
    assert translate_payment_label("en", "Оплачен") == "Paid"


@pytest.mark.unit
def test_translate_cz_reports_and_notes():
    assert translate("cz", "Чистый результат за месяц") == "Čistý výsledek za měsíc"
    assert translate("cz", "Текущий период") == "Aktuální období"
    assert translate("cz", "Описание") == "Popis"
    assert translate_stored_note("cz", "Стоимость: 100 ₽.") == "Cena: 100 ₽."
    assert "Telegramu" in translate_stored_note(
        "cz", "Создан автоматически из Telegram"
    )


@pytest.mark.unit
def test_calendar_locale_cz():
    loc = get_calendar_locale("cz")
    assert loc.month_nom[1] == "Leden"


@pytest.mark.unit
@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("+7 (999) 111-22-33", "89991112233", True),
        ("9991112233", "+79991112233", True),
        ("", "123", False),
        ("111", "222", False),
    ],
)
def test_phones_match(a, b, expected):
    assert phones_match(a, b) is expected


@pytest.mark.unit
def test_normalize_phone_digits():
    assert normalize_phone_digits("+7 (999) 000-00-00") == "79990000000"


@pytest.mark.unit
def test_recurrence_starts_weekly():
    start = datetime(2025, 1, 6, 10, 0)
    starts = build_recurrence_starts(start, "weekly", count=3)
    assert len(starts) == 3
    assert (starts[1] - starts[0]).days == 7
    assert recurrence_label("weekly")


@pytest.mark.unit
def test_migrate_prepare_row_defaults():
    from sqlalchemy import MetaData, Table, Column, Integer, String
    from app import app

    with app.app_context():
        meta = MetaData()
        t = Table(
            "user",
            meta,
            Column("id", Integer, primary_key=True),
            Column("email", String),
            Column("role", String, nullable=False),
            Column("telegram_ai_slot_minutes", Integer, nullable=False),
        )
        row = _prepare_row({"id": 1, "email": "a@b.c"}, t)
        assert row["role"] == "owner"
        assert row["telegram_ai_slot_minutes"] == 30
