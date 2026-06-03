"""Вспомогательные расчёты по клиенту для таблицы и карточки."""

from __future__ import annotations

from models import Client, ClientStatus, ClientReminder, ClientStatusHistory, db
from status_defaults import DEFAULT_CLIENT_STATUSES


def seed_default_statuses(user_id: int) -> ClientStatus | None:
    """Создаёт набор статусов по умолчанию; возвращает статус «Новый»."""
    first = None
    for name, color, position in DEFAULT_CLIENT_STATUSES:
        st = ClientStatus(
            user_id=user_id,
            name=name,
            color=color,
            position=position,
        )
        db.session.add(st)
        if position == 0:
            first = st
    db.session.flush()
    return first


def ensure_user_statuses(user_id: int) -> None:
    if ClientStatus.query.filter_by(user_id=user_id).count() == 0:
        seed_default_statuses(user_id)
        db.session.commit()


def default_status_for_user(user_id: int) -> ClientStatus | None:
    ensure_user_statuses(user_id)
    return (
        ClientStatus.query.filter_by(user_id=user_id)
        .order_by(ClientStatus.position.asc())
        .first()
    )


def orders_total(client: Client) -> float:
    return sum(o.price for o in client.orders)


def payments_total(client: Client) -> float:
    return sum(p.amount for p in client.payments)


def client_debt(client: Client) -> float:
    """Сколько клиент ещё должен (заказы минус платежи), не меньше 0."""
    return max(0.0, orders_total(client) - payments_total(client))


def has_unpaid_debt(client: Client) -> bool:
    return orders_total(client) > 0 and client_debt(client) > 0.01


def payment_summary(client: Client) -> str:
    owed = orders_total(client)
    paid = payments_total(client)
    if owed <= 0:
        return "—"
    if paid >= owed - 0.01:
        return "Оплачен"
    if paid > 0:
        return f"Частично ({paid:.0f}/{owed:.0f} ₽)"
    return "Не оплачен"


def payment_kind(label: str) -> str:
    if label == "Оплачен":
        return "paid"
    if label == "Не оплачен":
        return "unpaid"
    if label.startswith("Частично"):
        return "partial"
    return "none"


def record_status_change(client: Client, new_status_id: int | None) -> None:
    """Пишет в историю, если статус реально меняется."""
    old_id = client.status_id
    if old_id == new_status_id:
        return
    db.session.add(
        ClientStatusHistory(
            client_id=client.id,
            old_status_id=old_id,
            new_status_id=new_status_id,
        )
    )


def reminders_due_today(user_id: int) -> list[ClientReminder]:
    from datetime import datetime, timedelta

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    return (
        ClientReminder.query.filter(
            ClientReminder.user_id == user_id,
            ClientReminder.done.is_(False),
            ClientReminder.due_at >= today_start,
            ClientReminder.due_at < today_end,
        )
        .order_by(ClientReminder.due_at.asc())
        .all()
    )


def reminders_overdue(user_id: int) -> list[ClientReminder]:
    from datetime import datetime

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        ClientReminder.query.filter(
            ClientReminder.user_id == user_id,
            ClientReminder.done.is_(False),
            ClientReminder.due_at < today_start,
        )
        .order_by(ClientReminder.due_at.asc())
        .limit(20)
        .all()
    )


def build_dashboard_stats(user_id: int, clients: list[Client]) -> dict:
    """Сводка для главной страницы."""
    from datetime import datetime, timedelta

    from models import Appointment, ClientStatus

    total_debt = sum(client_debt(c) for c in clients)
    unpaid_count = sum(1 for c in clients if has_unpaid_debt(c))

    waiting_status = ClientStatus.query.filter_by(
        user_id=user_id, name="Ожидает клиента"
    ).first()
    waiting_count = 0
    if waiting_status:
        waiting_count = sum(1 for c in clients if c.status_id == waiting_status.id)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    appointments_today = Appointment.query.filter(
        Appointment.user_id == user_id,
        Appointment.status == "scheduled",
        Appointment.start_at >= today_start,
        Appointment.start_at < today_end,
    ).count()

    due_today = reminders_due_today(user_id)
    overdue = reminders_overdue(user_id)

    status_counts = []
    for st in (
        ClientStatus.query.filter_by(user_id=user_id)
        .order_by(ClientStatus.position.asc(), ClientStatus.id.asc())
        .all()
    ):
        status_counts.append(
            {
                "id": st.id,
                "name": st.name,
                "color": st.color,
                "count": sum(1 for c in clients if c.status_id == st.id),
            }
        )

    return {
        "total_clients": len(clients),
        "unpaid_count": unpaid_count,
        "total_debt": total_debt,
        "waiting_count": waiting_count,
        "appointments_today": appointments_today,
        "reminders_today": len(due_today),
        "reminders_overdue": len(overdue),
        "status_counts": status_counts,
    }
