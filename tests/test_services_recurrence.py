"""Каталог услуг и повторяющиеся записи."""

from __future__ import annotations

from datetime import datetime

from app import app
from models import Appointment, CatalogService, db


def _register(client, email="svc@test.com"):
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


def test_manage_services_add_and_use(client):
    _register(client, "svc1@test.com")
    client.post(
        "/services",
        data={"name": "Урок", "price": "1500", "duration_minutes": "90"},
        follow_redirects=True,
    )
    with app.app_context():
        svc = CatalogService.query.filter_by(name="Урок").one()

    r = client.get(f"/appointment/new?service_id={svc.id}")
    assert r.status_code == 200
    assert b"1500" in r.data
    assert b"90" in r.data


def test_weekly_recurrence_creates_series(client):
    _register(client, "rep@test.com")
    r = client.post(
        "/appointment/new",
        data={
            "title": "Репетиторство",
            "client_id": "",
            "start_at": "2030-06-03T10:00",
            "end_at": "2030-06-03T11:00",
            "notes": "",
            "repeat": "weekly",
            "repeat_end_type": "count",
            "repeat_count": "4",
            "use_catalog_duration": "0",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        apps = Appointment.query.order_by(Appointment.start_at).all()
        assert len(apps) == 4
        series_id = apps[0].recurrence_series_id
        assert series_id is not None
        assert all(ap.recurrence_series_id == series_id for ap in apps)
        assert apps[0].recurrence_rule == "weekly"
        assert apps[1].start_at.date().isoformat() == "2030-06-10"


def test_appointment_with_catalog_service(client):
    _register(client, "cat@test.com")
    client.post(
        "/services",
        data={"name": "Стрижка", "price": "800", "duration_minutes": "45"},
        follow_redirects=True,
    )
    with app.app_context():
        sid = CatalogService.query.filter_by(name="Стрижка").one().id

    client.post(
        "/appointment/new",
        data={
            "catalog_service_id": str(sid),
            "title": "",
            "client_id": "",
            "start_at": "2030-07-01T14:00",
            "end_at": "2030-07-01T14:45",
            "notes": "",
            "repeat": "",
            "use_catalog_duration": "1",
        },
        follow_redirects=True,
    )
    with app.app_context():
        ap = Appointment.query.one()
        assert ap.catalog_service_id == sid
        assert ap.price == 800
        assert ap.title == "Стрижка"
