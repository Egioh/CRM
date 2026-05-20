"""Календарь: месяц, неделя, день."""

from __future__ import annotations

from datetime import datetime

from app import app
from calendar_helpers import (
    build_day_calendar,
    build_month_calendar,
    build_week_calendar,
)
from models import Appointment, Client, db


def _register(client, email="cal@test.com"):
    client.post(
        "/register",
        data={
            "email": email,
            "password": "pw",
            "business_name": "B",
            "business_type": "Другое",
            "business_description": "",
        },
        follow_redirects=True,
    )


def test_index_shows_month_calendar(client):
    _register(client)
    r = client.get("/")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "crm-calendar" in html
    assert "Месяц" in html and "Неделя" in html and "День" in html


def test_calendar_month_navigation(client):
    _register(client)
    r = client.get("/?cal_view=month&cal_year=2026&cal_month=3")
    assert r.status_code == 200
    assert "Март 2026" in r.data.decode("utf-8")


def test_week_view_shows_time_grid(client):
    _register(client)
    r = client.get("/?cal_view=week&cal_date=2026-05-19")
    html = r.data.decode("utf-8")
    assert r.status_code == 200
    assert "time-grid-week" in html
    assert "19" in html and "мая" in html


def test_day_view_shows_single_column(client):
    _register(client)
    r = client.get("/?cal_view=day&cal_date=2026-05-20")
    html = r.data.decode("utf-8")
    assert r.status_code == 200
    assert "time-grid-day" in html
    assert "20" in html


def test_appointment_appears_on_week_and_day(client):
    _register(client)
    client.post(
        "/add_client",
        data={"name": "Иван", "phone": "+79001112233", "email": "", "notes": ""},
        follow_redirects=True,
    )
    with app.app_context():
        cid = Client.query.filter_by(name="Иван").one().id
        uid = Client.query.get(cid).user_id
        start = datetime(2026, 5, 15, 14, 0)
        end = datetime(2026, 5, 15, 15, 30)
        db.session.add(
            Appointment(
                user_id=uid,
                client_id=cid,
                title="Стрижка",
                start_at=start,
                end_at=end,
                status="scheduled",
            )
        )
        db.session.commit()

    r_month = client.get("/?cal_view=month&cal_year=2026&cal_month=5")
    html_m = r_month.data.decode("utf-8")
    assert "Иван" in html_m and "14:00" in html_m

    r_week = client.get("/?cal_view=week&cal_date=2026-05-15")
    html_w = r_week.data.decode("utf-8")
    assert "time-grid-event" in html_w
    assert "Стрижка" in html_w

    r_day = client.get("/?cal_view=day&cal_date=2026-05-15")
    html_d = r_day.data.decode("utf-8")
    assert "14:00" in html_d and "15:30" in html_d


def test_build_calendar_structures():
    with app.app_context():
        month = build_month_calendar(1, 2026, 5, today=datetime(2026, 5, 20).date())
        week = build_week_calendar(1, datetime(2026, 5, 20).date(), today=datetime(2026, 5, 20).date())
        day = build_day_calendar(1, datetime(2026, 5, 20).date(), today=datetime(2026, 5, 20).date())
    assert month["view"] == "month"
    assert len(month["weeks"]) == 6
    assert week["view"] == "week"
    assert len(week["days"]) == 7
    assert week["grid_height_px"] == (22 - 7) * 48
    assert day["view"] == "day"
    assert day["day"]["weekday_full"] == "Среда"
