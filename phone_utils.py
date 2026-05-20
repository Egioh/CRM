"""Нормализация телефонов для поиска клиента."""

from __future__ import annotations

import re


def normalize_phone_digits(phone: str | None) -> str:
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


def phones_match(a: str | None, b: str | None) -> bool:
    da = normalize_phone_digits(a)
    db = normalize_phone_digits(b)
    if not da or not db:
        return False
    if da == db:
        return True
    # Последние 10 цифр (РФ без кода страны)
    if len(da) >= 10 and len(db) >= 10 and da[-10:] == db[-10:]:
        return True
    return False
