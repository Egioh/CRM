"""Создание записей: повторяемость и каталог услуг."""

from __future__ import annotations

import calendar as cal_mod
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from models import Appointment, CatalogService

RECURRENCE_CHOICES = (
    ("", "Не повторять"),
    ("daily", "Каждый день"),
    ("weekly", "Каждую неделю"),
    ("biweekly", "Каждые 2 недели"),
    ("monthly", "Каждый месяц"),
)

MAX_RECURRENCE_OCCURRENCES = 52


def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, cal_mod.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def next_recurrence_start(current: datetime, rule: str) -> datetime:
    if rule == "daily":
        return current + timedelta(days=1)
    if rule == "weekly":
        return current + timedelta(days=7)
    if rule == "biweekly":
        return current + timedelta(days=14)
    if rule == "monthly":
        return _add_months(current, 1)
    raise ValueError(f"Unknown recurrence rule: {rule}")


def build_recurrence_starts(
    start_at: datetime,
    rule: str,
    *,
    until_date: Optional[date] = None,
    count: Optional[int] = None,
) -> list[datetime]:
    if not rule:
        return [start_at]

    limit = min(count or MAX_RECURRENCE_OCCURRENCES, MAX_RECURRENCE_OCCURRENCES)
    starts = [start_at]
    current = start_at

    while len(starts) < limit:
        current = next_recurrence_start(current, rule)
        if until_date and current.date() > until_date:
            break
        starts.append(current)

    return starts


def catalog_service_for_user(user_id: int, service_id: int | None) -> CatalogService | None:
    if not service_id:
        return None
    return CatalogService.query.filter_by(id=service_id, user_id=user_id).first()


def recurrence_label(rule: str | None) -> str:
    if not rule:
        return ""
    for code, label in RECURRENCE_CHOICES:
        if code == rule:
            return label
    return rule
