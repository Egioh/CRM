"""Агрегаты для страницы отчётов: клиенты, приход, расходы, сравнение периодов."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func

from models import BusinessExpense, Client, OrderExpense, Payment, db


def _utc_now() -> datetime:
    return datetime.utcnow()


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week(dt: datetime) -> datetime:
    """Понедельник 00:00 UTC."""
    d = _start_of_day(dt)
    return d - timedelta(days=d.weekday())


def _start_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _start_of_year(dt: datetime) -> datetime:
    return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _end_of_month(start: datetime) -> datetime:
    last = monthrange(start.year, start.month)[1]
    return start.replace(day=last, hour=23, minute=59, second=59, microsecond=999999)


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return round((current - previous) / previous * 100.0, 1)


def _sum_payments(user_id: int, start: datetime, end: datetime) -> float:
    row = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0.0))
        .join(Client)
        .filter(
            Client.user_id == user_id,
            Payment.date >= start,
            Payment.date <= end,
        )
        .scalar()
    )
    return float(row or 0.0)


def _count_clients(user_id: int, start: datetime | None = None, end: datetime | None = None) -> int:
    q = Client.query.filter_by(user_id=user_id)
    if start is not None:
        q = q.filter(Client.created_at >= start)
    if end is not None:
        q = q.filter(Client.created_at <= end)
    return q.count()


def _sum_business_expenses(user_id: int, start: datetime, end: datetime) -> float:
    row = (
        db.session.query(func.coalesce(func.sum(BusinessExpense.amount), 0.0))
        .filter(
            BusinessExpense.user_id == user_id,
            BusinessExpense.expense_date >= start,
            BusinessExpense.expense_date <= end,
        )
        .scalar()
    )
    return float(row or 0.0)


def _sum_order_expenses(user_id: int, start: datetime, end: datetime) -> float:
    from models import Order

    row = (
        db.session.query(func.coalesce(func.sum(OrderExpense.amount), 0.0))
        .join(Order)
        .join(Client)
        .filter(
            Client.user_id == user_id,
            OrderExpense.expense_date >= start,
            OrderExpense.expense_date <= end,
        )
        .scalar()
    )
    return float(row or 0.0)


def total_expenses(user_id: int, start: datetime, end: datetime) -> float:
    return _sum_business_expenses(user_id, start, end) + _sum_order_expenses(user_id, start, end)


def period_comparison(user_id: int, kind: str) -> dict[str, Any]:
    """kind: week | month | year — текущий период vs предыдущий."""
    now = _utc_now()
    if kind == 'week':
        cur_start = _start_of_week(now)
        cur_end = now
        prev_start = cur_start - timedelta(days=7)
        prev_end = cur_start - timedelta(microseconds=1)
    elif kind == 'month':
        cur_start = _start_of_month(now)
        cur_end = now
        prev_month_end = cur_start - timedelta(microseconds=1)
        prev_start = _start_of_month(prev_month_end)
        prev_end = prev_month_end
    elif kind == 'year':
        cur_start = _start_of_year(now)
        cur_end = now
        prev_start = cur_start.replace(year=cur_start.year - 1)
        prev_end = cur_start - timedelta(microseconds=1)
    else:
        raise ValueError(kind)

    cur_income = _sum_payments(user_id, cur_start, cur_end)
    prev_income = _sum_payments(user_id, prev_start, prev_end)
    cur_clients = _count_clients(user_id, cur_start, cur_end)
    prev_clients = _count_clients(user_id, prev_start, prev_end)
    cur_exp = total_expenses(user_id, cur_start, cur_end)
    prev_exp = total_expenses(user_id, prev_start, prev_end)

    return {
        'kind': kind,
        'current': {
            'income': cur_income,
            'clients_new': cur_clients,
            'expenses': cur_exp,
            'net': cur_income - cur_exp,
        },
        'previous': {
            'income': prev_income,
            'clients_new': prev_clients,
            'expenses': prev_exp,
            'net': prev_income - prev_exp,
        },
        'change_pct': {
            'income': _pct_change(cur_income, prev_income),
            'clients_new': _pct_change(float(cur_clients), float(prev_clients)),
            'expenses': _pct_change(cur_exp, prev_exp),
            'net': _pct_change(cur_income - cur_exp, prev_income - prev_exp),
        },
    }


def _prev_month_start(dt: datetime) -> datetime:
    if dt.month == 1:
        return dt.replace(year=dt.year - 1, month=12, day=1)
    return dt.replace(month=dt.month - 1, day=1)


def monthly_chart_series(user_id: int, months: int = 12) -> list[dict[str, Any]]:
    """Последние N календарных месяцев для графика."""
    now = _utc_now()
    cur = _start_of_month(now)
    out: list[dict[str, Any]] = []
    for _ in range(months):
        if cur.year == now.year and cur.month == now.month:
            end = now
        else:
            end = _end_of_month(cur)
        income = _sum_payments(user_id, cur, end)
        expenses = total_expenses(user_id, cur, end)
        out.append(
            {
                'label': f'{cur.month:02d}.{cur.year}',
                'income': round(income, 2),
                'expenses': round(expenses, 2),
                'net': round(income - expenses, 2),
                'clients_new': _count_clients(user_id, cur, end),
            }
        )
        cur = _prev_month_start(cur)
    out.reverse()
    return out


def build_reports_dashboard(user_id: int) -> dict[str, Any]:
    now = _utc_now()
    all_clients = _count_clients(user_id)
    month_start = _start_of_month(now)
    month_income = _sum_payments(user_id, month_start, now)
    month_expenses = total_expenses(user_id, month_start, now)
    chart_series = monthly_chart_series(user_id, 12)

    return {
        'all_clients': all_clients,
        'month_income': month_income,
        'month_expenses': month_expenses,
        'month_net': month_income - month_expenses,
        'chart_series': chart_series,
        'comparisons': [
            period_comparison(user_id, 'week'),
            period_comparison(user_id, 'month'),
            period_comparison(user_id, 'year'),
        ],
    }


def build_reports_csv(user_id: int) -> str:
    """CSV: сводка, помесячная динамика, сравнения периодов."""
    import csv
    import io

    data = build_reports_dashboard(user_id)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=';')
    w.writerow(['Показатель', 'Значение'])
    w.writerow(['Всего клиентов', data['all_clients']])
    w.writerow(['Приход за текущий месяц', f"{data['month_income']:.2f}"])
    w.writerow(['Расходы за текущий месяц', f"{data['month_expenses']:.2f}"])
    w.writerow(['Чистый результат за месяц', f"{data['month_net']:.2f}"])
    w.writerow([])
    w.writerow(['Месяц', 'Приход', 'Расходы', 'Чистый результат', 'Новых клиентов'])
    for row in data['chart_series']:
        w.writerow(
            [
                row['label'],
                f"{row['income']:.2f}",
                f"{row['expenses']:.2f}",
                f"{row['net']:.2f}",
                row['clients_new'],
            ]
        )
    w.writerow([])
    period_titles = {'week': 'Неделя к неделе', 'month': 'Месяц к месяцу', 'year': 'Год к году'}
    for block in data['comparisons']:
        title = period_titles.get(block['kind'], block['kind'])
        w.writerow([title])
        w.writerow(['', 'Текущий', 'Предыдущий', 'Изменение %'])
        w.writerow(
            [
                'Приход',
                f"{block['current']['income']:.2f}",
                f"{block['previous']['income']:.2f}",
                block['change_pct']['income'] if block['change_pct']['income'] is not None else '',
            ]
        )
        w.writerow(
            [
                'Новых клиентов',
                block['current']['clients_new'],
                block['previous']['clients_new'],
                block['change_pct']['clients_new'] if block['change_pct']['clients_new'] is not None else '',
            ]
        )
        w.writerow(
            [
                'Расходы',
                f"{block['current']['expenses']:.2f}",
                f"{block['previous']['expenses']:.2f}",
                block['change_pct']['expenses'] if block['change_pct']['expenses'] is not None else '',
            ]
        )
        w.writerow(
            [
                'Чистый результат',
                f"{block['current']['net']:.2f}",
                f"{block['previous']['net']:.2f}",
                block['change_pct']['net'] if block['change_pct']['net'] is not None else '',
            ]
        )
        w.writerow([])
    return buf.getvalue()
