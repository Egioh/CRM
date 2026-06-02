from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Optional

from models import (
    Appointment,
    CatalogService,
    Client,
    ClientReminder,
    TelegramConversationState,
    User,
    db,
)
from client_linking import find_client_by_telegram_chat
from phone_utils import normalize_phone_digits
from deepseek_extract import extract_intent_and_entities


@dataclass
class TgMessage:
    chat_id: str
    text: str
    from_display_name: Optional[str]


def _tz(user: User) -> ZoneInfo:
    name = (user.telegram_ai_timezone or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _now(user: User) -> datetime:
    return datetime.now(tz=_tz(user))


def _load_state(user_id: int, chat_id: str) -> TelegramConversationState:
    s = TelegramConversationState.query.filter_by(
        user_id=user_id, telegram_chat_id=str(chat_id)
    ).first()
    if s:
        return s
    s = TelegramConversationState(
        user_id=user_id,
        telegram_chat_id=str(chat_id),
        state="idle",
        payload_json=None,
        expires_at=None,
    )
    db.session.add(s)
    db.session.flush()
    return s


def _set_state(s: TelegramConversationState, state: str, payload: Optional[dict[str, Any]] = None) -> None:
    s.state = state
    s.payload_json = json.dumps(payload or {}, ensure_ascii=False)
    s.updated_at = datetime.utcnow()


def _payload(s: TelegramConversationState) -> dict[str, Any]:
    raw = (s.payload_json or "").strip()
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": data} for (text, data) in row] for row in rows
        ]
    }


def _parse_contact(text: str) -> tuple[Optional[str], Optional[str]]:
    t = (text or "").strip()
    if not t:
        return None, None
    phone = normalize_phone_digits(t)
    if phone:
        name = re.sub(r"\+?\d[\d\s\-\(\)]{7,}", "", t).strip()
        return (name or None), phone
    return t[:100], None


def _match_service(user: User, text: str) -> Optional[CatalogService]:
    t = (text or "").strip().lower()
    if not t:
        return None
    aliases = {k.lower().strip(): v for k, v in user.telegram_service_aliases().items()}
    if t in aliases:
        target = aliases[t].lower().strip()
    else:
        target = t
    services = CatalogService.query.filter_by(user_id=user.id).order_by(CatalogService.position.asc(), CatalogService.id.asc()).all()
    for s in services:
        if s.name.lower().strip() == target:
            return s
    for s in services:
        if target in s.name.lower():
            return s
    return None


def _parse_when(user: User, text: str) -> Optional[datetime]:
    t = (text or "").strip().lower()
    if not t:
        return None
    tz = _tz(user)
    base = _now(user)
    # tomorrow / today keywords (ru)
    if "завтра" in t:
        day = (base + timedelta(days=1)).date()
        m = re.search(r"(\d{1,2})[:\.](\d{2})", t)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2))
            return datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
    if "сегодня" in t:
        day = base.date()
        m = re.search(r"(\d{1,2})[:\.](\d{2})", t)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2))
            return datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
    # dd.mm hh:mm
    m = re.search(r"\b(\d{1,2})[\.\/](\d{1,2})(?:[\.\/](\d{2,4}))?\s+(\d{1,2})[:\.](\d{2})\b", t)
    if m:
        dd = int(m.group(1))
        mm_ = int(m.group(2))
        yy = m.group(3)
        hh = int(m.group(4))
        mi = int(m.group(5))
        year = int(yy) if yy else base.year
        if year < 100:
            year += 2000
        return datetime(year, mm_, dd, hh, mi, tzinfo=tz)
    # yyyy-mm-dd hh:mm
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2})[:\.](\d{2})\b", t)
    if m:
        return datetime(
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            int(m.group(4)),
            int(m.group(5)),
            tzinfo=tz,
        )
    return None


def _format_dt_local(user: User, dt: datetime) -> str:
    tz = _tz(user)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    else:
        dt = dt.astimezone(tz)
    return dt.strftime("%d.%m.%Y %H:%M")


def _working_windows_for_day(user: User, day: datetime) -> list[tuple[datetime, datetime]]:
    """Returns local-tz windows for the given day."""
    tz = _tz(user)
    local_day = day.astimezone(tz) if day.tzinfo else day.replace(tzinfo=tz)
    key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][local_day.weekday()]
    cfg = user.telegram_working_hours()
    ranges = cfg.get(key)
    if not ranges:
        # default: Mon-Fri 09:00-18:00, Sat 10:00-16:00, Sun closed
        if key in {"mon", "tue", "wed", "thu", "fri"}:
            ranges = [["09:00", "18:00"]]
        elif key == "sat":
            ranges = [["10:00", "16:00"]]
        else:
            ranges = []
    windows: list[tuple[datetime, datetime]] = []
    for r in ranges:
        if not isinstance(r, list) or len(r) != 2:
            continue
        start_s, end_s = str(r[0]), str(r[1])
        m1 = re.match(r"^(\d{1,2}):(\d{2})$", start_s)
        m2 = re.match(r"^(\d{1,2}):(\d{2})$", end_s)
        if not m1 or not m2:
            continue
        sh, sm = int(m1.group(1)), int(m1.group(2))
        eh, em = int(m2.group(1)), int(m2.group(2))
        start = datetime(local_day.year, local_day.month, local_day.day, sh, sm, tzinfo=tz)
        end = datetime(local_day.year, local_day.month, local_day.day, eh, em, tzinfo=tz)
        if end > start:
            windows.append((start, end))
    return windows


def _overlaps(user_id: int, start_at_utc_naive: datetime, end_at_utc_naive: datetime) -> bool:
    q = Appointment.query.filter(
        Appointment.user_id == user_id,
        Appointment.status == "scheduled",
        Appointment.start_at < end_at_utc_naive,
        Appointment.end_at > start_at_utc_naive,
    )
    return q.first() is not None


def _suggest_slots(
    user: User,
    desired_start_local: datetime,
    duration_minutes: int,
    *,
    limit: int = 4,
    horizon_days: int = 7,
) -> list[datetime]:
    """Return list of local datetimes suggested for booking."""
    tz = _tz(user)
    if desired_start_local.tzinfo is None:
        desired_start_local = desired_start_local.replace(tzinfo=tz)
    slot = max(5, min(int(user.telegram_ai_slot_minutes or 30), 120))
    duration = max(int(user.telegram_ai_min_duration_minutes or 30), int(duration_minutes))
    out: list[datetime] = []
    cur = desired_start_local
    end_horizon = desired_start_local + timedelta(days=horizon_days)

    def to_utc_naive(dt: datetime) -> datetime:
        return dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    while cur < end_horizon and len(out) < limit:
        day_windows = _working_windows_for_day(user, cur)
        for w_start, w_end in day_windows:
            # start from max(cur, w_start), rounded up to slot minutes
            cand = max(cur, w_start)
            mins = cand.hour * 60 + cand.minute
            mins_rounded = ((mins + slot - 1) // slot) * slot
            cand = cand.replace(hour=mins_rounded // 60, minute=mins_rounded % 60, second=0, microsecond=0)
            while cand + timedelta(minutes=duration) <= w_end and len(out) < limit:
                cand_end = cand + timedelta(minutes=duration)
                if not _overlaps(user.id, to_utc_naive(cand), to_utc_naive(cand_end)):
                    out.append(cand)
                cand = cand + timedelta(minutes=slot)
        # next day at 00:00
        next_day = (cur + timedelta(days=1)).astimezone(tz)
        cur = datetime(next_day.year, next_day.month, next_day.day, 0, 0, tzinfo=tz)
    return out


def handle_tenant_update(user: User, data: dict[str, Any]) -> tuple[str, str, Optional[dict[str, Any]]]:
    """
    Returns (chat_id, text, reply_markup) for Telegram sendMessage.
    Only handles:
      - /services (list services)
      - booking flow via state machine
      - callback_query buttons (ai:...)
    """
    cb = data.get("callback_query")
    if isinstance(cb, dict):
        chat_id = str(((cb.get("message") or {}).get("chat") or {}).get("id") or "")
        qdata = str(cb.get("data") or "")
        if not chat_id or not qdata.startswith("ai:"):
            return chat_id, "Не понимаю действие.", None
        return _handle_callback(user, chat_id, qdata)

    msg = data.get("message") or data.get("edited_message")
    if not isinstance(msg, dict):
        return "", "", None
    chat_id = str(((msg.get("chat") or {}).get("id")) or "")
    if not chat_id:
        return "", "", None
    text = msg.get("text") or msg.get("caption") or ""
    if not isinstance(text, str):
        text = str(text)
    from_data = msg.get("from") or {}
    display_name = (from_data.get("first_name") or "").strip()
    last = (from_data.get("last_name") or "").strip()
    if last:
        display_name = f"{display_name} {last}".strip()
    if not display_name:
        display_name = None
    m = TgMessage(chat_id=chat_id, text=text.strip(), from_display_name=display_name)
    return _handle_message(user, m)


def _handle_message(user: User, m: TgMessage) -> tuple[str, str, Optional[dict[str, Any]]]:
    s = _load_state(user.id, m.chat_id)
    p = _payload(s)
    txt = (m.text or "").strip()
    low = txt.lower()

    if low in {"/start", "start"}:
        _set_state(s, "idle", {})
        db.session.commit()
        dn = user.telegram_ai_display_name or user.business_name
        return m.chat_id, f"Здравствуйте! Я онлайн‑ассистент {dn}. Чем могу помочь?", None

    if low in {"/services", "услуги", "прайс", "цены", "цена"} or "услуг" in low:
        return _reply_services(user, m.chat_id)

    # LLM extraction (only when idle-ish to avoid messing with state machine)
    if s.state in {"idle", "choose_service"} and txt and not low.startswith("/"):
        services = (
            CatalogService.query.filter_by(user_id=user.id)
            .order_by(CatalogService.position.asc(), CatalogService.id.asc())
            .all()
        )
        extracted = extract_intent_and_entities(
            business_name=user.business_name,
            services=[{"name": ss.name, "price": ss.price, "duration_minutes": ss.duration_minutes} for ss in services],
            user_timezone=user.telegram_ai_timezone or "UTC",
            text=txt,
        )
        if isinstance(extracted, dict):
            intent = str(extracted.get("intent") or "").strip().lower()
            confidence = extracted.get("confidence")
            try:
                conf = float(confidence)
            except Exception:
                conf = 0.0

            if intent == "services_list" and conf >= 0.5:
                return _reply_services(user, m.chat_id)

            if intent == "handoff" and conf >= 0.5:
                _set_state(s, "handoff", {})
                db.session.commit()
                sla = user.telegram_ai_handoff_sla_text or "Передам администратору, он ответит в ближайшее время."
                return m.chat_id, sla, None

            if intent == "book" and conf >= 0.45:
                # prefill contact + service + time if possible
                p = p or {}
                if extracted.get("contact_name"):
                    p["contact_name"] = str(extracted["contact_name"])[:100]
                if extracted.get("contact_phone"):
                    p["contact_phone"] = str(extracted["contact_phone"])[:40]
                srv_name = extracted.get("service_name")
                if isinstance(srv_name, str) and srv_name.strip():
                    srv = _match_service(user, srv_name)
                    if srv:
                        p["service_id"] = srv.id
                        p["service_name"] = srv.name
                        p["duration_minutes"] = srv.duration_minutes
                        p["price"] = srv.price
                when_text = extracted.get("when_text")
                if isinstance(when_text, str) and when_text.strip():
                    when = _parse_when(user, when_text)
                    if when:
                        p["start_at_iso"] = when.isoformat()
                        duration = int(p.get("duration_minutes") or 60)
                        duration = max(int(user.telegram_ai_min_duration_minutes or 30), duration)
                        p["duration_minutes"] = duration
                        p["end_at_iso"] = (when + timedelta(minutes=duration)).isoformat()

                client = find_client_by_telegram_chat(user.id, m.chat_id)
                if not client and (user.telegram_ai_require_name or user.telegram_ai_require_phone):
                    _set_state(s, "collect_contact", p)
                    db.session.commit()
                    return m.chat_id, "Чтобы записать вас, напишите имя и телефон одним сообщением.", None

                if not p.get("service_id"):
                    _set_state(s, "choose_service", p)
                    db.session.commit()
                    return _reply_choose_service(user, m.chat_id)

                if not p.get("start_at_iso"):
                    _set_state(s, "choose_time", p)
                    db.session.commit()
                    return m.chat_id, f"Когда вас записать на «{p.get('service_name')}»? (например: `завтра 15:30`)", None

                # go to confirm; choose_time will validate working hours/conflicts when user sets time,
                # but if we already have time, we can reuse confirm and let commit handle overlaps later.
                _set_state(s, "confirm_appointment", p)
                db.session.commit()
                return _reply_confirm(user, m.chat_id, p)

    # handoff triggers (simple)
    triggers = [t.strip().lower() for t in (user.telegram_ai_handoff_triggers or "").splitlines() if t.strip()]
    if any(t in low for t in triggers) or "человек" in low or "админ" in low or "оператор" in low:
        _set_state(s, "handoff", {})
        db.session.commit()
        sla = user.telegram_ai_handoff_sla_text or "Мы скоро ответим."
        return m.chat_id, sla, None

    if s.state == "collect_contact":
        name, phone = _parse_contact(txt)
        if user.telegram_ai_require_name and not name:
            return m.chat_id, "Напишите, пожалуйста, ваше имя.", None
        if user.telegram_ai_require_phone and not phone:
            return m.chat_id, "Напишите, пожалуйста, ваш номер телефона (в любом формате).", None
        p["contact_name"] = name
        p["contact_phone"] = phone
        _set_state(s, "choose_service", p)
        db.session.commit()
        return _reply_choose_service(user, m.chat_id)

    if s.state == "choose_time":
        when = _parse_when(user, txt)
        if not when:
            return m.chat_id, "Напишите дату и время, например: `05.06 15:30` или `завтра 15:30`.", None
        p["start_at_iso"] = when.isoformat()
        # duration from service
        duration = int(p.get("duration_minutes") or 60)
        duration = max(int(user.telegram_ai_min_duration_minutes or 30), duration)
        p["duration_minutes"] = duration
        end_at = when + timedelta(minutes=duration)
        p["end_at_iso"] = end_at.isoformat()
        # check working hours and overlaps; if conflict, suggest slots
        slot = when
        if slot.tzinfo is None:
            slot = slot.replace(tzinfo=_tz(user))
        slot_end = end_at
        if slot_end.tzinfo is None:
            slot_end = slot_end.replace(tzinfo=_tz(user))
        start_utc_naive = slot.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        end_utc_naive = slot_end.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        windows = _working_windows_for_day(user, slot)
        in_hours = any(slot >= ws and slot_end <= we for ws, we in windows)
        if not in_hours or _overlaps(user.id, start_utc_naive, end_utc_naive):
            suggestions = _suggest_slots(user, slot, duration)
            if suggestions:
                rows = [[( _format_dt_local(user, dt), f"ai:time:{dt.isoformat()}")] for dt in suggestions]
                _set_state(s, "choose_time", p)
                db.session.commit()
                reason = "В это время мы не работаем." if not in_hours else "В это время уже занято."
                return m.chat_id, f"{reason} Выберите ближайшее время:", _inline_keyboard(rows)
            return m.chat_id, "Не могу подобрать свободное время рядом. Напишите другой день/время.", None

        _set_state(s, "confirm_appointment", p)
        db.session.commit()
        return _reply_confirm(user, m.chat_id, p)

    if s.state in {"idle", "choose_service", "confirm_appointment"}:
        # if user typed something that looks like service while waiting service choice
        if s.state == "choose_service":
            srv = _match_service(user, txt)
            if not srv:
                return _reply_choose_service(user, m.chat_id, note="Не нашла услугу. Выберите из списка ниже.")
            p["service_id"] = srv.id
            p["service_name"] = srv.name
            p["duration_minutes"] = srv.duration_minutes
            p["price"] = srv.price
            _set_state(s, "choose_time", p)
            db.session.commit()
            return m.chat_id, f"Отлично. Когда вас записать на «{srv.name}»? (например: `завтра 15:30`)", None

        # Start booking if message contains "запис"
        if "запис" in low or low.startswith("/book"):
            client = find_client_by_telegram_chat(user.id, m.chat_id)
            if not client:
                _set_state(s, "collect_contact", {})
                db.session.commit()
                gdpr = (user.telegram_ai_gdpr_text or "").strip()
                if gdpr:
                    return m.chat_id, f"{gdpr}\n\nКак вас зовут и какой номер телефона?", None
                return m.chat_id, "Как вас зовут и какой номер телефона?", None
            _set_state(s, "choose_service", {})
            db.session.commit()
            return _reply_choose_service(user, m.chat_id)

    return m.chat_id, "Я могу подсказать услуги (/services) и записать вас на услугу (напишите «запиши меня ...»).", None


def _handle_callback(user: User, chat_id: str, qdata: str) -> tuple[str, str, Optional[dict[str, Any]]]:
    s = _load_state(user.id, chat_id)
    p = _payload(s)
    parts = qdata.split(":")
    # ai:svc:<id>
    if len(parts) >= 3 and parts[1] == "svc":
        try:
            sid = int(parts[2])
        except ValueError:
            return chat_id, "Не понимаю выбранную услугу.", None
        srv = CatalogService.query.filter_by(user_id=user.id, id=sid).first()
        if not srv:
            return chat_id, "Эта услуга недоступна.", None
        p["service_id"] = srv.id
        p["service_name"] = srv.name
        p["duration_minutes"] = srv.duration_minutes
        p["price"] = srv.price
        _set_state(s, "choose_time", p)
        db.session.commit()
        return chat_id, f"Вы выбрали «{srv.name}». Когда вас записать? (например: `завтра 15:30`)", None

    # ai:confirm
    if parts[1] == "confirm":
        ok, msg = _commit_booking(user, chat_id, p)
        _set_state(s, "idle", {})
        db.session.commit()
        return chat_id, msg, None

    # ai:time:<iso>
    if len(parts) >= 3 and parts[1] == "time":
        iso = ":".join(parts[2:])  # keep potential colons in time
        try:
            when = datetime.fromisoformat(iso)
        except Exception:
            return chat_id, "Не понимаю выбранное время.", None
        duration = int(p.get("duration_minutes") or 60)
        duration = max(int(user.telegram_ai_min_duration_minutes or 30), duration)
        p["start_at_iso"] = when.isoformat()
        p["duration_minutes"] = duration
        p["end_at_iso"] = (when + timedelta(minutes=duration)).isoformat()
        _set_state(s, "confirm_appointment", p)
        db.session.commit()
        return _reply_confirm(user, chat_id, p)

    # ai:cancel
    if parts[1] == "cancel":
        _set_state(s, "idle", {})
        db.session.commit()
        return chat_id, "Ок, отменено. Если захотите — напишите «запиши меня».", None

    return chat_id, "Не понимаю действие.", None


def _reply_services(user: User, chat_id: str) -> tuple[str, str, Optional[dict[str, Any]]]:
    services = (
        CatalogService.query.filter_by(user_id=user.id)
        .order_by(CatalogService.position.asc(), CatalogService.id.asc())
        .all()
    )
    if not services:
        return chat_id, "Пока нет списка услуг. Напишите администратору — мы поможем.", None
    lines = []
    for s in services[:30]:
        price = f"{int(s.price)}" if s.price is not None and float(s.price).is_integer() else f"{s.price:g}"
        lines.append(f"- {s.name} — {price} (≈ {s.duration_minutes} мин)")
    text = "Наши услуги:\n" + "\n".join(lines)
    text += "\n\nЧтобы записаться — напишите: «запиши меня на <услуга> завтра 15:30»"
    return chat_id, text, None


def _reply_choose_service(
    user: User, chat_id: str, note: Optional[str] = None
) -> tuple[str, str, Optional[dict[str, Any]]]:
    services = (
        CatalogService.query.filter_by(user_id=user.id)
        .order_by(CatalogService.position.asc(), CatalogService.id.asc())
        .all()
    )
    if not services:
        return chat_id, "Не могу записать: у компании не настроены услуги в CRM.", None
    rows: list[list[tuple[str, str]]] = []
    row: list[tuple[str, str]] = []
    for s in services[:12]:
        row.append((s.name[:28], f"ai:svc:{s.id}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    text = note or "Выберите услугу:"
    return chat_id, text, _inline_keyboard(rows)


def _reply_confirm(user: User, chat_id: str, p: dict[str, Any]) -> tuple[str, str, Optional[dict[str, Any]]]:
    srv = p.get("service_name") or "услуга"
    start_iso = p.get("start_at_iso")
    if not start_iso:
        return chat_id, "Не вижу дату/время. Напишите ещё раз.", None
    start = datetime.fromisoformat(start_iso)
    duration = int(p.get("duration_minutes") or 60)
    price = p.get("price")
    price_txt = ""
    if price is not None:
        try:
            pf = float(price)
            price_txt = f", цена: {pf:g}"
        except Exception:
            price_txt = f", цена: {price}"
    when_txt = _format_dt_local(user, start)
    text = f"Подтвердите запись:\n- Услуга: {srv}\n- Время: {when_txt}\n- Длительность: {duration} мин{price_txt}"
    return chat_id, text, _inline_keyboard([[("Подтвердить", "ai:confirm"), ("Отмена", "ai:cancel")]])


def _commit_booking(user: User, chat_id: str, p: dict[str, Any]) -> tuple[bool, str]:
    # ensure client
    client = find_client_by_telegram_chat(user.id, chat_id)
    if not client:
        name = (p.get("contact_name") or "").strip() or f"Telegram {chat_id}"
        phone = (p.get("contact_phone") or "").strip() or None
        client = Client(
            user_id=user.id,
            name=name[:100],
            phone=phone,
            telegram_chat_id=chat_id,
            notes="Создан автоматически из Telegram (AI-запись)",
        )
        db.session.add(client)
        db.session.flush()
    else:
        # fill missing
        if not client.phone and p.get("contact_phone"):
            client.phone = str(p.get("contact_phone"))[:20]
        if (not client.name or client.name.startswith("Telegram ")) and p.get("contact_name"):
            client.name = str(p.get("contact_name"))[:100]

    service_id = p.get("service_id")
    service = None
    if service_id:
        try:
            service = CatalogService.query.filter_by(user_id=user.id, id=int(service_id)).first()
        except Exception:
            service = None
    start_iso = p.get("start_at_iso")
    end_iso = p.get("end_at_iso")
    if not start_iso or not end_iso:
        return False, "Не хватает даты/времени. Начните заново: напишите «запиши меня»."
    start_at = datetime.fromisoformat(start_iso)
    end_at = datetime.fromisoformat(end_iso)
    # store naive in DB as UTC-like (app currently uses naive datetimes); convert to naive UTC
    if start_at.tzinfo is not None:
        start_at = start_at.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    if end_at.tzinfo is not None:
        end_at = end_at.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    title = service.name if service else (p.get("service_name") or "Онлайн запись")
    appt = Appointment(
        user_id=user.id,
        client_id=client.id,
        catalog_service_id=service.id if service else None,
        title=str(title)[:200],
        price=(service.price if service else p.get("price")),
        start_at=start_at,
        end_at=end_at,
        status="scheduled",
        source="telegram_ai",
        notes="Создано через Telegram AI-бота",
    )
    db.session.add(appt)
    db.session.flush()

    rem = ClientReminder(
        user_id=user.id,
        client_id=client.id,
        due_at=datetime.utcnow(),
        body=f"Онлайн-запись через Telegram AI-бота: {appt.title} {_format_dt_local(user, datetime.fromisoformat(p['start_at_iso']))}",
        done=False,
    )
    db.session.add(rem)
    db.session.commit()
    when_txt = _format_dt_local(user, datetime.fromisoformat(p["start_at_iso"]))
    return True, f"Готово! Записала на «{title}» — {when_txt}."

