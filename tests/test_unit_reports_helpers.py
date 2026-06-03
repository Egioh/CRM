"""Unit tests: reports_helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import app
from models import Client, Payment, BusinessExpense, db
from reports_helpers import (
    build_reports_csv,
    build_reports_dashboard,
    monthly_chart_series,
    period_comparison,
    total_expenses,
)


@pytest.mark.unit
def test_period_comparison_empty_tenant():
    with app.app_context():
        block = period_comparison(user_id=99999, kind="week")
        assert block["kind"] == "week"
        assert block["current"]["income"] == 0.0
        assert block["previous"]["income"] == 0.0


@pytest.mark.unit
def test_dashboard_with_payment():
    with app.app_context():
        from models import User

        u = User(
            email="rep@test.com",
            password_hash="x",
            business_name="B",
            business_type="T",
        )
        u.set_password("x")
        db.session.add(u)
        db.session.flush()
        uid = u.id
        c = Client(user_id=uid, name="P")
        db.session.add(c)
        db.session.flush()
        now = datetime.utcnow()
        db.session.add(
            Payment(
                client_id=c.id,
                amount=300.0,
                method="card",
                date=now,
            )
        )
        db.session.add(
            BusinessExpense(
                user_id=uid,
                amount=50.0,
                description="rent",
                expense_date=now,
            )
        )
        db.session.commit()

        dash = build_reports_dashboard(uid)
        assert dash["month_income"] >= 300.0
        assert dash["month_expenses"] >= 50.0
        assert dash["month_net"] == dash["month_income"] - dash["month_expenses"]
        assert len(dash["chart_series"]) == 12
        assert len(dash["comparisons"]) == 3

        csv_text = build_reports_csv(uid)
        assert "Приход" in csv_text or "300" in csv_text
        assert ";" in csv_text


@pytest.mark.unit
def test_monthly_chart_series_length():
    with app.app_context():
        series = monthly_chart_series(99999, months=6)
        assert len(series) == 6
        assert "label" in series[0]
        assert "income" in series[0]
