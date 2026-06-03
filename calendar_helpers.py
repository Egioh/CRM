"""Построение календаря: месяц, неделя, день (как в Google Calendar)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import Any

from i18n import get_calendar_locale
from models import Appointment

MONTH_NAMES_RU = (
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)

MONTH_NAMES_GENITIVE = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

WEEKDAY_HEADERS_RU = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
WEEKDAY_FULL_RU = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

GRID_START_HOUR = 7
GRID_END_HOUR = 22
PX_PER_HOUR = 48
CALENDAR_VIEWS = ("month", "week", "day")


def _today() -> date:
    return datetime.utcnow().date()


def format_date_short(d: date, *, lang: str = "ru") -> str:
    loc = get_calendar_locale(lang)
    return f"{d.day} {loc.month_gen[d.month]}"


def parse_cal_view(raw: str | None) -> str:
    if raw in CALENDAR_VIEWS:
        return raw
    return "month"


def parse_cal_date(raw: str | None, default: date | None = None) -> date:
    if default is None:
        default = _today()
    if not raw:
        return default
    try:
        return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return default


def parse_calendar_month(
    cal_year: int | None,
    cal_month: int | None,
) -> tuple[int, int]:
    now = datetime.utcnow()
    year = cal_year if cal_year else now.year
    month = cal_month if cal_month else now.month
    if month < 1 or month > 12:
        month = now.month
    if year < 1970 or year > 2100:
        year = now.year
    return year, month


def week_start_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month + delta
    y = year
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


def _appointments_in_range(
    user_id: int, range_start: datetime, range_end: datetime
) -> list[Appointment]:
    return (
        Appointment.query.filter(
            Appointment.user_id == user_id,
            Appointment.start_at < range_end,
            Appointment.end_at >= range_start,
        )
        .order_by(Appointment.start_at.asc())
        .all()
    )


def _appointments_for_month(user_id: int, year: int, month: int) -> list[Appointment]:
    month_start, month_end = _month_bounds(year, month)
    return _appointments_in_range(user_id, month_start, month_end)


def _appointment_event(ap: Appointment) -> dict[str, Any]:
    label = ap.title
    if ap.client:
        label = f"{ap.client.name}: {ap.title}"
    if ap.price is not None and ap.price > 0:
        label = f"{label} ({ap.price:.0f} ₽)"
    if ap.recurrence_series_id:
        label = f"↻ {label}"
    return {
        "id": ap.id,
        "title": ap.title,
        "label": label[:80],
        "client_id": ap.client_id,
        "client_name": ap.client.name if ap.client else None,
        "start_at": ap.start_at,
        "end_at": ap.end_at,
        "start_time": ap.start_at.strftime("%H:%M"),
        "end_time": ap.end_at.strftime("%H:%M"),
        "status": ap.status,
        "cancelled": ap.status == "cancelled",
    }


def _grid_times() -> dict[str, Any]:
    hours = list(range(GRID_START_HOUR, GRID_END_HOUR))
    height = (GRID_END_HOUR - GRID_START_HOUR) * PX_PER_HOUR
    return {
        "hours": hours,
        "hour_labels": [f"{h:02d}:00" for h in hours],
        "px_per_hour": PX_PER_HOUR,
        "grid_height_px": height,
        "grid_start_hour": GRID_START_HOUR,
        "grid_end_hour": GRID_END_HOUR,
    }


def _layout_timed_event(ap: Appointment, day: date) -> dict[str, Any]:
    """Позиция блока записи внутри дневной колонки (px от верха сетки)."""
    ev = _appointment_event(ap)
    grid_start = datetime.combine(day, time(GRID_START_HOUR, 0))
    grid_end = datetime.combine(day, time(GRID_END_HOUR, 0))
    start = max(ap.start_at, grid_start)
    end = min(ap.end_at, grid_end)
    if end <= start:
        end = min(ap.end_at, grid_end)
        if end <= start:
            start = ap.start_at
            end = ap.end_at if ap.end_at > ap.start_at else ap.start_at + timedelta(minutes=30)

    top_min = (start - grid_start).total_seconds() / 60
    dur_min = max(15, (end - start).total_seconds() / 60)
    max_min = (GRID_END_HOUR - GRID_START_HOUR) * 60
    top_px = int(top_min / 60 * PX_PER_HOUR)
    height_px = max(22, int(dur_min / 60 * PX_PER_HOUR))
    if top_px + height_px > max_min / 60 * PX_PER_HOUR:
        height_px = max(22, int(max_min / 60 * PX_PER_HOUR) - top_px)

    ev["top_px"] = top_px
    ev["height_px"] = height_px
    ev["date_iso"] = day.isoformat()
    return ev


def _day_column(
    user_id: int,
    day: date,
    apps: list[Appointment],
    today: date,
    *,
    lang: str = "ru",
) -> dict[str, Any]:
    loc = get_calendar_locale(lang)
    day_apps = [ap for ap in apps if ap.start_at.date() == day]
    return {
        "date": day,
        "date_iso": day.isoformat(),
        "day": day.day,
        "weekday_short": loc.weekday_short[day.weekday()],
        "weekday_full": loc.weekday_full[day.weekday()],
        "is_today": day == today,
        "is_weekend": day.weekday() >= 5,
        "timed_events": [_layout_timed_event(ap, day) for ap in day_apps],
        "appointment_count": len(day_apps),
    }


def build_month_calendar(
    user_id: int,
    year: int,
    month: int,
    *,
    today: date | None = None,
    lang: str = "ru",
) -> dict[str, Any]:
    if today is None:
        today = _today()

    year = max(1970, min(2100, year))
    month = max(1, min(12, month))

    apps = _appointments_for_month(user_id, year, month)
    by_day: dict[date, list[dict[str, Any]]] = {}
    for ap in apps:
        d = ap.start_at.date()
        by_day.setdefault(d, []).append(_appointment_event(ap))

    first_weekday, _days_in_month = monthrange(year, month)
    grid_start = date(year, month, 1) - timedelta(days=first_weekday)
    prev_y, prev_m = _shift_month(year, month, -1)
    next_y, next_m = _shift_month(year, month, 1)

    weeks: list[list[dict[str, Any]]] = []
    cursor = grid_start
    for _ in range(6):
        week: list[dict[str, Any]] = []
        for _ in range(7):
            in_month = cursor.month == month and cursor.year == year
            events = by_day.get(cursor, []) if in_month else []
            week.append(
                {
                    "date": cursor,
                    "day": cursor.day,
                    "in_month": in_month,
                    "is_today": cursor == today,
                    "is_weekend": cursor.weekday() >= 5,
                    "appointments": events,
                    "appointment_count": len(events),
                }
            )
            cursor += timedelta(days=1)
        weeks.append(week)

    loc = get_calendar_locale(lang)
    month_label = f"{loc.month_nom[month]} {year}"
    return {
        "view": "month",
        "header_label": month_label,
        "month_label": month_label,
        "year": year,
        "month": month,
        "weekday_headers": loc.weekday_short,
        "weeks": weeks,
        "prev_year": prev_y,
        "prev_month": prev_m,
        "next_year": next_y,
        "next_month": next_m,
        "today_year": today.year,
        "today_month": today.month,
        "anchor_date": date(year, month, 1),
    }


def build_week_calendar(
    user_id: int,
    anchor: date,
    *,
    today: date | None = None,
    lang: str = "ru",
) -> dict[str, Any]:
    if today is None:
        today = _today()

    week_start = week_start_monday(anchor)
    week_end = week_start + timedelta(days=6)
    range_start = datetime.combine(week_start, time.min)
    range_end = datetime.combine(week_end + timedelta(days=1), time.min)
    apps = _appointments_in_range(user_id, range_start, range_end)

    loc = get_calendar_locale(lang)
    days = [
        _day_column(user_id, week_start + timedelta(days=i), apps, today, lang=lang)
        for i in range(7)
    ]

    if week_start.month == week_end.month:
        header = (
            f"{week_start.day} – {week_end.day} {loc.month_gen[week_end.month]} {week_end.year}"
        )
    else:
        header = (
            f"{format_date_short(week_start, lang=lang)} – "
            f"{format_date_short(week_end, lang=lang)} {week_end.year}"
        )

    result = {
        "view": "week",
        "header_label": header,
        "week_start": week_start,
        "week_end": week_end,
        "days": days,
        "prev_date": week_start - timedelta(days=7),
        "next_date": week_start + timedelta(days=7),
        "today_date": today,
        "anchor_date": anchor,
    }
    result.update(_grid_times())
    return result


def build_day_calendar(
    user_id: int,
    day: date,
    *,
    today: date | None = None,
    lang: str = "ru",
) -> dict[str, Any]:
    if today is None:
        today = _today()

    range_start = datetime.combine(day, time.min)
    range_end = range_start + timedelta(days=1)
    apps = _appointments_in_range(user_id, range_start, range_end)
    col = _day_column(user_id, day, apps, today, lang=lang)
    loc = get_calendar_locale(lang)
    header = (
        f"{loc.weekday_full[day.weekday()]}, {day.day} "
        f"{loc.month_gen[day.month]} {day.year}"
    )

    result = {
        "view": "day",
        "header_label": header,
        "day": col,
        "day_date": day,
        "prev_date": day - timedelta(days=1),
        "next_date": day + timedelta(days=1),
        "today_date": today,
        "anchor_date": day,
    }
    result.update(_grid_times())
    return result


def build_calendar_view(
    user_id: int,
    cal_view: str,
    *,
    cal_year: int | None = None,
    cal_month: int | None = None,
    cal_date: date | None = None,
    today: date | None = None,
    lang: str = "ru",
) -> dict[str, Any]:
    if today is None:
        today = _today()
    anchor = cal_date or today

    if cal_view == "week":
        return build_week_calendar(user_id, anchor, today=today, lang=lang)
    if cal_view == "day":
        return build_day_calendar(user_id, anchor, today=today, lang=lang)

    year, month = parse_calendar_month(cal_year, cal_month)
    return build_month_calendar(user_id, year, month, today=today, lang=lang)


def appointments_for_calendar_view(
    user_id: int, calendar_view: dict[str, Any]
) -> list[Appointment]:
    view = calendar_view.get("view", "month")
    if view == "week":
        start = datetime.combine(calendar_view["week_start"], time.min)
        end = datetime.combine(calendar_view["week_end"] + timedelta(days=1), time.min)
    elif view == "day":
        d = calendar_view["day_date"]
        start = datetime.combine(d, time.min)
        end = start + timedelta(days=1)
    else:
        year, month = calendar_view["year"], calendar_view["month"]
        start, end = _month_bounds(year, month)
    return _appointments_in_range(user_id, start, end)
