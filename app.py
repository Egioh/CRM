from flask import Flask, render_template, request, redirect, url_for, flash, make_response, abort
from functools import wraps
from models import (
    db,
    User,
    Client,
    ClientStatus,
    ClientComment,
    ClientReminder,
    ClientStatusHistory,
    Order,
    OrderExpense,
    BusinessExpense,
    Payment,
    InboundMessage,
    Appointment,
    CatalogService,
    Staff,
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from client_helpers import (
    build_dashboard_stats,
    client_debt,
    default_status_for_user,
    ensure_user_statuses,
    has_unpaid_debt,
    payment_kind,
    payment_summary,
    record_status_change,
    reminders_due_today,
    reminders_overdue,
    seed_default_statuses,
)
from messaging_outbound import check_telegram_api, send_telegram_message, send_whatsapp_message
from urllib.parse import urlencode

from appointment_helpers import (
    RECURRENCE_CHOICES,
    build_recurrence_starts,
    catalog_service_for_user,
    recurrence_label,
)
from calendar_helpers import (
    appointments_for_calendar_view,
    build_calendar_view,
    parse_cal_date,
    parse_cal_view,
    week_start_monday,
)
import os
import uuid
from datetime import date, datetime, time, timedelta
from typing import Optional

from dotenv import load_dotenv
from public_url import configure_proxy_and_cookies, public_url_configured, resolve_public_url_root
from reports_helpers import build_reports_csv, build_reports_dashboard

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'sqlite:///instance/crm.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-insecure-change-me')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
configure_proxy_and_cookies(app)

db.init_app(app)
csrf = CSRFProtect(app)

from messaging import MESSAGING_CSRF_EXEMPT_ENDPOINTS, bp as messaging_bp  # noqa: E402

app.register_blueprint(messaging_bp)
for _endpoint in MESSAGING_CSRF_EXEMPT_ENDPOINTS:
    _view = app.view_functions.get(_endpoint)
    if _view is not None:
        csrf.exempt(_view)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None

from i18n import (  # noqa: E402
    html_lang_code,
    normalize_lang,
    resolve_lang,
    translate,
    translate_named,
    translate_outbound_message,
    translate_payment_label,
    translate_stored_note,
)


def _current_lang() -> str:
    return resolve_lang(
        request.cookies.get("lang"),
        request.headers.get("Accept-Language"),
    )


def _tr(text: str) -> str:
    """Translate server-side messages (flash, etc.) according to current language."""
    return translate(_current_lang(), text)


def _tr_msg(text: str) -> str:
    return translate_outbound_message(_current_lang(), text)


def owner_required(f):
    """Только собственник бизнеса (не дочерний admin)."""

    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_business_owner():
            flash(_tr('Доступ только для владельца бизнеса'), 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return wrapped


@login_manager.unauthorized_handler
def _unauthorized():
    flash(_tr('Пожалуйста, войдите в систему'), 'info')
    return redirect(url_for('login', next=request.url))


@app.context_processor
def _inject_i18n():
    lang = _current_lang()

    def _(text: str) -> str:
        return translate(lang, text)

    def tr_note(text: str | None) -> str:
        return translate_stored_note(lang, text)

    return {
        "_": _,
        "tr_note": tr_note,
        "current_lang": lang,
        "html_lang": html_lang_code(lang),
        "public_url_root": resolve_public_url_root(),
        "public_url_configured": public_url_configured(),
    }


@app.route("/lang/<lang>", methods=["GET"])
def set_lang(lang: str):
    lang = normalize_lang(lang)
    ref = request.referrer or url_for("index")
    resp = make_response(redirect(ref))
    resp.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def _parse_positive_float(value: str, field_name: str) -> Optional[float]:
    lang = _current_lang()
    try:
        num = float(value)
    except (TypeError, ValueError):
        flash(
            translate_named(lang, "Поле «{name}» должно быть числом.", name=field_name),
            "error",
        )
        return None

    if num < 0:
        flash(
            translate_named(
                lang, "Поле «{name}» не может быть отрицательным.", name=field_name
            ),
            "error",
        )
        return None

    return num


def _parse_date_only(raw: str) -> Optional[date]:
    """Дата из поля формы: Y-m-d (flatpickr) или d.m.Y / d/m/Y."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _staff_id_from_form(raw: str | None, tenant_id: int) -> int | None:
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        pk = int(raw)
    except ValueError:
        return None
    st = Staff.query.filter_by(id=pk, user_id=tenant_id, active=True).first()
    return st.id if st else None


def _active_staff_for_tenant(tenant_id: int):
    return (
        Staff.query.filter_by(user_id=tenant_id, active=True)
        .order_by(Staff.name)
        .all()
    )


def _statuses_for_user(user_id: int):
    ensure_user_statuses(user_id)
    return (
        ClientStatus.query.filter_by(user_id=user_id)
        .order_by(ClientStatus.position.asc(), ClientStatus.id.asc())
        .all()
    )


def _client_status_or_404(status_id: int):
    return ClientStatus.query.filter_by(
        id=status_id, user_id=current_user.tenant_id
    ).first_or_404()


def _index_list_filter_args(q: str, status_filter: int | None, unpaid_only: bool) -> dict:
    args: dict = {}
    if q:
        args['q'] = q
    if status_filter:
        args['status'] = status_filter
    if unpaid_only:
        args['unpaid'] = '1'
    return args


def _prepare_calendar(
    user_id: int,
    endpoint: str,
    extra_query: dict | None,
) -> dict:
    """Контекст календаря: вид month/week/day, навигация и сетка."""
    cal_view = parse_cal_view(request.args.get('cal_view'))
    today = datetime.utcnow().date()
    cal_date_raw = request.args.get('cal_date', '').strip()
    anchor = parse_cal_date(cal_date_raw or None, today)
    extra = extra_query or {}

    calendar_view = build_calendar_view(
        user_id,
        cal_view,
        cal_year=request.args.get('cal_year', type=int),
        cal_month=request.args.get('cal_month', type=int),
        cal_date=anchor,
        today=today,
        lang=_current_lang(),
    )
    anchor = calendar_view.get('anchor_date', today)

    def nav(view_name: str, **params):
        return url_for(endpoint, cal_view=view_name, **params, **extra)

    if cal_view == 'month':
        calendar_prev_url = nav(
            'month',
            cal_year=calendar_view['prev_year'],
            cal_month=calendar_view['prev_month'],
        )
        calendar_next_url = nav(
            'month',
            cal_year=calendar_view['next_year'],
            cal_month=calendar_view['next_month'],
        )
        calendar_today_url = nav(
            'month',
            cal_year=calendar_view['today_year'],
            cal_month=calendar_view['today_month'],
        )
    elif cal_view == 'week':
        calendar_prev_url = nav('week', cal_date=calendar_view['prev_date'].isoformat())
        calendar_next_url = nav('week', cal_date=calendar_view['next_date'].isoformat())
        calendar_today_url = nav('week', cal_date=today.isoformat())
    else:
        calendar_prev_url = nav('day', cal_date=calendar_view['prev_date'].isoformat())
        calendar_next_url = nav('day', cal_date=calendar_view['next_date'].isoformat())
        calendar_today_url = nav('day', cal_date=today.isoformat())

    return {
        'cal_view': cal_view,
        'cal_date': anchor.isoformat(),
        'calendar_view': calendar_view,
        'calendar_prev_url': calendar_prev_url,
        'calendar_next_url': calendar_next_url,
        'calendar_today_url': calendar_today_url,
        'calendar_url_month': nav(
            'month', cal_year=anchor.year, cal_month=anchor.month
        ),
        'calendar_url_week': nav(
            'week', cal_date=week_start_monday(anchor).isoformat()
        ),
        'calendar_url_day': nav('day', cal_date=anchor.isoformat()),
        'calendar_url_day_base': url_for(endpoint),
        'calendar_extra_qs': urlencode(extra) if extra else '',
        'calendar_appointments': appointments_for_calendar_view(
            user_id, calendar_view
        ),
    }


# Маршруты аутентификации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        business_name = request.form['business_name']
        business_type = request.form['business_type']
        business_description = request.form['business_description']
        
        if User.query.filter_by(email=email).first():
            flash(_tr('Пользователь с таким email уже существует'), 'error')
            return render_template('register.html')
        
        user = User(
            email=email,
            business_name=business_name,
            business_type=business_type,
            business_description=business_description,
            role='owner',
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()
        seed_default_statuses(user.id)
        db.session.commit()

        login_user(user)
        flash(_tr('Регистрация успешна!'), 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash(_tr('Вход выполнен успешно!'), 'success')
            return redirect(url_for('index'))
        else:
            flash(_tr('Неверный email или пароль'), 'error')
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash(_tr('Вы вышли из системы'), 'info')
    return redirect(url_for('login'))

# Основные маршруты
@app.route('/')
@login_required
def index():
    ensure_user_statuses(current_user.tenant_id)
    status_filter = request.args.get('status', type=int)
    unpaid_only = request.args.get('unpaid') == '1'
    q = request.args.get('q', '').strip()

    all_clients = Client.query.filter_by(user_id=current_user.tenant_id).all()
    dashboard = build_dashboard_stats(current_user.tenant_id, all_clients)

    query = Client.query.filter_by(user_id=current_user.tenant_id)
    if status_filter:
        if ClientStatus.query.filter_by(
            id=status_filter, user_id=current_user.tenant_id
        ).first():
            query = query.filter(Client.status_id == status_filter)
        else:
            flash(_tr('Статус не найден'), 'error')
            status_filter = None
    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(Client.name.ilike(like), Client.phone.ilike(like))
        )
    clients = query.order_by(Client.created_at.desc()).all()
    if unpaid_only:
        clients = [c for c in clients if has_unpaid_debt(c)]

    statuses = _statuses_for_user(current_user.tenant_id)
    lang = _current_lang()
    rows = []
    for c in clients:
        pl = payment_summary(c)
        rows.append(
            {
                'client': c,
                'payment_label': pl,
                'payment_display': translate_payment_label(lang, pl),
                'payment_kind': payment_kind(pl),
                'debt': client_debt(c),
            }
        )

    list_filters = _index_list_filter_args(q, status_filter, unpaid_only)
    calendar_ctx = _prepare_calendar(current_user.tenant_id, 'index', list_filters)

    return render_template(
        'clients.html',
        rows=rows,
        statuses=statuses,
        status_filter=status_filter,
        search_q=q,
        unpaid_only=unpaid_only,
        dashboard=dashboard,
        reminders_today=reminders_due_today(current_user.tenant_id),
        reminders_overdue_list=reminders_overdue(current_user.tenant_id),
        calendar_compact=True,
        **calendar_ctx,
    )

@app.route('/client/<int:client_id>')
@login_required
def client_detail(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    statuses = _statuses_for_user(current_user.tenant_id)
    history = (
        ClientStatusHistory.query.filter_by(client_id=client.id)
        .order_by(ClientStatusHistory.changed_at.desc())
        .limit(30)
        .all()
    )
    open_reminders = (
        ClientReminder.query.filter_by(
            client_id=client.id, user_id=current_user.tenant_id, done=False
        )
        .order_by(ClientReminder.due_at.asc())
        .all()
    )
    recent_messages = (
        InboundMessage.query.filter_by(client_id=client.id, user_id=current_user.tenant_id)
        .order_by(InboundMessage.created_at.desc())
        .limit(10)
        .all()
    )
    can_whatsapp = bool(client.phone and current_user.whatsapp_phone_number_id)
    can_telegram = bool(client.telegram_chat_id)
    pl = payment_summary(client)
    client_appointments = (
        Appointment.query.filter_by(client_id=client.id, user_id=current_user.tenant_id)
        .order_by(Appointment.start_at.desc())
        .all()
    )
    return render_template(
        'client_detail.html',
        client=client,
        statuses=statuses,
        payment_label=pl,
        payment_display=translate_payment_label(_current_lang(), pl),
        payment_kind=payment_kind(pl),
        client_debt_amount=client_debt(client),
        status_history=history,
        open_reminders=open_reminders,
        recent_messages=recent_messages,
        can_whatsapp=can_whatsapp,
        can_telegram=can_telegram,
        client_appointments=client_appointments,
        list_collapse_threshold=4,
    )

# Добавление и редактирование клиентов
@app.route('/add_client', methods=['GET', 'POST'])
@login_required
def add_client():
    statuses = _statuses_for_user(current_user.tenant_id)
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        notes = request.form['notes']
        status_id = request.form.get('status_id', type=int)
        if status_id:
            _client_status_or_404(status_id)
        else:
            default_st = default_status_for_user(current_user.tenant_id)
            status_id = default_st.id if default_st else None

        client = Client(
            user_id=current_user.tenant_id,
            status_id=status_id,
            name=name,
            phone=phone,
            email=email,
            notes=notes,
        )
        db.session.add(client)
        db.session.flush()
        if status_id:
            record_status_change(client, status_id)
        db.session.commit()

        flash(_tr('Клиент успешно добавлен'), 'success')
        return redirect(url_for('index'))

    return render_template('edit_client.html', client=None, statuses=statuses)

@app.route('/edit_client/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    statuses = _statuses_for_user(current_user.tenant_id)

    if request.method == 'POST':
        client.name = request.form['name']
        client.phone = request.form['phone']
        client.email = request.form['email']
        client.notes = request.form['notes']
        sid = request.form.get('status_id', type=int)
        if sid:
            new_st = _client_status_or_404(sid)
            record_status_change(client, new_st.id)
            client.status_id = new_st.id

        db.session.commit()
        flash(_tr('Данные клиента обновлены'), 'success')
        return redirect(url_for('client_detail', client_id=client.id))

    return render_template('edit_client.html', client=client, statuses=statuses)


@app.route('/client/<int:client_id>/status', methods=['POST'])
@login_required
def client_set_status(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    sid = request.form.get('status_id', type=int)
    if not sid:
        flash(_tr('Выберите статус'), 'error')
        return redirect(request.referrer or url_for('index'))
    new_st = _client_status_or_404(sid)
    record_status_change(client, new_st.id)
    client.status_id = new_st.id
    db.session.commit()
    flash(_tr('Статус обновлён'), 'success')
    return redirect(request.referrer or url_for('client_detail', client_id=client_id))


@app.route('/client/<int:client_id>/comment', methods=['POST'])
@login_required
def client_add_comment(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    body = (request.form.get('body') or '').strip()
    if not body:
        flash(_tr('Введите текст комментария'), 'error')
        return redirect(url_for('client_detail', client_id=client_id))
    db.session.add(ClientComment(client_id=client.id, body=body))
    db.session.commit()
    flash(_tr('Комментарий добавлен'), 'success')
    return redirect(url_for('client_detail', client_id=client_id))


@app.route('/client/<int:client_id>/reminder', methods=['POST'])
@login_required
def client_add_reminder(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    body = (request.form.get('body') or 'Перезвонить').strip()
    due_raw = request.form.get('due_at', '').strip()
    due_date = _parse_date_only(due_raw)
    if not due_date:
        flash(_tr('Укажите дату напоминания'), 'error')
        return redirect(url_for('client_detail', client_id=client_id))
    due_at = datetime.combine(due_date, time(9, 0))
    db.session.add(
        ClientReminder(
            user_id=current_user.tenant_id,
            client_id=client.id,
            due_at=due_at,
            body=body[:500],
        )
    )
    db.session.commit()
    flash(_tr('Напоминание создано'), 'success')
    return redirect(url_for('client_detail', client_id=client_id))


@app.route('/reminder/<int:reminder_id>/done', methods=['POST'])
@login_required
def reminder_done(reminder_id):
    rem = ClientReminder.query.filter_by(
        id=reminder_id, user_id=current_user.tenant_id
    ).first_or_404()
    rem.done = True
    db.session.commit()
    flash(_tr('Напоминание выполнено'), 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/client/<int:client_id>/message', methods=['POST'])
@login_required
def client_send_message(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    channel = (request.form.get('channel') or '').strip().lower()
    text = (request.form.get('body') or '').strip()
    if not text:
        flash(_tr('Введите текст сообщения'), 'error')
        return redirect(url_for('client_detail', client_id=client_id))
    if channel == 'telegram':
        ok, msg = send_telegram_message(client, text)
    elif channel == 'whatsapp':
        ok, msg = send_whatsapp_message(current_user, client, text)
    else:
        flash(_tr('Выберите канал отправки'), 'error')
        return redirect(url_for('client_detail', client_id=client_id))
    flash(_tr_msg(msg), 'success' if ok else 'error')
    if ok:
        label = 'WhatsApp' if channel == 'whatsapp' else 'Telegram'
        db.session.add(
            ClientComment(
                client_id=client.id,
                body=f"[{label}] {text}",
            )
        )
        db.session.commit()
    return redirect(url_for('client_detail', client_id=client_id))


@app.route('/statuses', methods=['GET', 'POST'])
@login_required
def manage_statuses():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        color = request.form.get('color') or 'secondary'
        if not name:
            flash(_tr('Введите название статуса'), 'error')
            return redirect(url_for('manage_statuses'))
        if ClientStatus.query.filter_by(user_id=current_user.tenant_id, name=name).first():
            flash(_tr('Такой статус уже есть'), 'error')
            return redirect(url_for('manage_statuses'))
        max_pos = (
            db.session.query(db.func.max(ClientStatus.position))
            .filter_by(user_id=current_user.tenant_id)
            .scalar()
        ) or 0
        db.session.add(
            ClientStatus(
                user_id=current_user.tenant_id,
                name=name,
                color=color,
                position=max_pos + 1,
            )
        )
        db.session.commit()
        flash(_tr('Статус создан'), 'success')
        return redirect(url_for('manage_statuses'))

    statuses = _statuses_for_user(current_user.tenant_id)
    return render_template('statuses.html', statuses=statuses)


@app.route('/statuses/<int:status_id>/delete', methods=['POST'])
@login_required
def delete_status(status_id):
    st = _client_status_or_404(status_id)
    in_use = Client.query.filter_by(
        status_id=st.id, user_id=current_user.tenant_id
    ).count()
    if in_use:
        flash(
            translate_named(
                _current_lang(),
                "Статус используется у {count} клиент(ов). Сначала смените статус у них.",
                count=str(in_use),
            ),
            'error',
        )
        return redirect(url_for('manage_statuses'))
    db.session.delete(st)
    db.session.commit()
    flash(_tr('Статус удалён'), 'success')
    return redirect(url_for('manage_statuses'))

@app.route('/delete_client/<int:client_id>', methods=['POST'])
@login_required
def delete_client(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    db.session.delete(client)
    db.session.commit()
    flash(_tr('Клиент удален'), 'success')
    return redirect(url_for('index'))

# Управление заказами
@app.route('/add_order/<int:client_id>', methods=['POST'])
@login_required
def add_order(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    
    service = request.form['service']
    price = _parse_positive_float(request.form.get("price"), "Цена")
    if price is None:
        return redirect(url_for('client_detail', client_id=client_id))
    notes = request.form.get('notes', '')
    
    order = Order(client_id=client_id, service=service, price=price, notes=notes)
    db.session.add(order)
    db.session.commit()
    
    flash(_tr('Заказ добавлен'), 'success')
    return redirect(url_for('client_detail', client_id=client_id))

@app.route('/edit_order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
    order = Order.query.join(Client).filter(
        Order.id == order_id, 
        Client.user_id == current_user.tenant_id
    ).first_or_404()
    
    if request.method == 'POST':
        order.service = request.form['service']
        price = _parse_positive_float(request.form.get("price"), "Цена")
        if price is None:
            return redirect(url_for('edit_order', order_id=order_id))
        order.price = price
        order.notes = request.form.get('notes', '')
        order.date = datetime.strptime(request.form['date'], '%Y-%m-%dT%H:%M')
        order.staff_id = _staff_id_from_form(
            request.form.get('staff_id'), current_user.tenant_id
        )

        db.session.commit()
        flash(_tr('Заказ обновлен'), 'success')
        return redirect(url_for('client_detail', client_id=order.client_id))

    staff_list = _active_staff_for_tenant(current_user.tenant_id)
    order_expenses = (
        OrderExpense.query.filter_by(order_id=order.id)
        .order_by(OrderExpense.expense_date.desc())
        .all()
    )
    return render_template(
        'edit_order.html',
        order=order,
        staff_list=staff_list,
        order_expenses=order_expenses,
    )

@app.route('/delete_order/<int:order_id>', methods=['POST'])
@login_required
def delete_order(order_id):
    order = Order.query.join(Client).filter(
        Order.id == order_id, 
        Client.user_id == current_user.tenant_id
    ).first_or_404()
    
    client_id = order.client_id
    db.session.delete(order)
    db.session.commit()
    flash(_tr('Заказ удален'), 'success')
    return redirect(url_for('client_detail', client_id=client_id))

# Управление платежами
@app.route('/add_payment/<int:client_id>', methods=['POST'])
@login_required
def add_payment(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first_or_404()
    
    amount = _parse_positive_float(request.form.get("amount"), "Сумма")
    if amount is None:
        return redirect(url_for('client_detail', client_id=client_id))
    method = request.form['method']
    notes = request.form.get('notes', '')
    
    payment = Payment(client_id=client_id, amount=amount, method=method, notes=notes)
    db.session.add(payment)
    db.session.commit()
    
    flash(_tr('Платеж добавлен'), 'success')
    return redirect(url_for('client_detail', client_id=client_id))

@app.route('/edit_payment/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def edit_payment(payment_id):
    payment = Payment.query.join(Client).filter(
        Payment.id == payment_id, 
        Client.user_id == current_user.tenant_id
    ).first_or_404()
    
    if request.method == 'POST':
        amount = _parse_positive_float(request.form.get("amount"), "Сумма")
        if amount is None:
            return redirect(url_for('edit_payment', payment_id=payment_id))
        payment.amount = amount
        payment.method = request.form['method']
        payment.notes = request.form.get('notes', '')
        payment.date = datetime.strptime(request.form['date'], '%Y-%m-%dT%H:%M')
        
        db.session.commit()
        flash(_tr('Платеж обновлен'), 'success')
        return redirect(url_for('client_detail', client_id=payment.client_id))
    
    return render_template('edit_payment.html', payment=payment)

@app.route('/delete_payment/<int:payment_id>', methods=['POST'])
@login_required
def delete_payment(payment_id):
    payment = Payment.query.join(Client).filter(
        Payment.id == payment_id, 
        Client.user_id == current_user.tenant_id
    ).first_or_404()
    
    client_id = payment.client_id
    db.session.delete(payment)
    db.session.commit()
    flash(_tr('Платеж удален'), 'success')
    return redirect(url_for('client_detail', client_id=client_id))

def _appointment_overlaps(user_id, start_at, end_at, exclude_id=None):
    q = Appointment.query.filter(
        Appointment.user_id == user_id,
        Appointment.status == 'scheduled',
        Appointment.start_at < end_at,
        Appointment.end_at > start_at,
    )
    if exclude_id is not None:
        q = q.filter(Appointment.id != exclude_id)
    return q.first() is not None

@app.route('/integrations', methods=['GET', 'POST'])
@owner_required
def integrations():
    if request.method == 'POST':
        wa_pid = (request.form.get('whatsapp_phone_number_id') or '').strip()
        if wa_pid:
            taken = User.query.filter(
                User.whatsapp_phone_number_id == wa_pid,
                User.id != current_user.id,
            ).first()
            if taken:
                flash(_tr('Этот Phone number ID уже привязан к другому аккаунту'), 'error')
                return redirect(url_for('integrations'))
            current_user.whatsapp_phone_number_id = wa_pid
        else:
            current_user.whatsapp_phone_number_id = None
        # Telegram AI bot settings (per tenant)
        tg_enabled = (request.form.get("telegram_ai_enabled") or "").lower() in {"1", "true", "yes", "on"}
        tg_token = (request.form.get("telegram_bot_token") or "").strip()
        current_user.telegram_ai_enabled = bool(tg_enabled and tg_token)
        current_user.telegram_bot_token = tg_token or None
        if current_user.telegram_ai_enabled:
            current_user.ensure_telegram_webhook_token()
        lang = (request.form.get("telegram_ai_language") or "auto").strip()[:16]
        tone = (request.form.get("telegram_ai_tone") or "friendly").strip()[:32]
        tz = (request.form.get("telegram_ai_timezone") or "UTC").strip()[:64]
        current_user.telegram_ai_language = lang or "auto"
        current_user.telegram_ai_tone = tone or "friendly"
        current_user.telegram_ai_timezone = tz or "UTC"
        current_user.telegram_ai_display_name = (request.form.get("telegram_ai_display_name") or "").strip()[:120] or None
        current_user.telegram_ai_require_name = (request.form.get("telegram_ai_require_name") or "").lower() in {"1", "true", "yes", "on"}
        current_user.telegram_ai_require_phone = (request.form.get("telegram_ai_require_phone") or "").lower() in {"1", "true", "yes", "on"}
        wh = (request.form.get("telegram_ai_working_hours_json") or "").strip()
        current_user.telegram_ai_working_hours_json = wh or None
        slot_minutes = request.form.get("telegram_ai_slot_minutes", type=int)
        if slot_minutes and 5 <= slot_minutes <= 120:
            current_user.telegram_ai_slot_minutes = slot_minutes
        min_dur = request.form.get("telegram_ai_min_duration_minutes", type=int)
        if min_dur and 5 <= min_dur <= 24 * 60:
            current_user.telegram_ai_min_duration_minutes = min_dur
        aliases = (request.form.get("telegram_ai_service_aliases_json") or "").strip()
        current_user.telegram_ai_service_aliases_json = aliases or None
        current_user.telegram_ai_handoff_triggers = (request.form.get("telegram_ai_handoff_triggers") or "").strip() or None
        current_user.telegram_ai_handoff_sla_text = (request.form.get("telegram_ai_handoff_sla_text") or "").strip()[:200] or None
        current_user.telegram_ai_gdpr_text = (request.form.get("telegram_ai_gdpr_text") or "").strip()[:400] or None

        db.session.commit()
        flash(_tr('Настройки интеграций сохранены'), 'success')
        if current_user.telegram_ai_enabled and current_user.telegram_bot_token:
            ok, detail = check_telegram_api(current_user.telegram_bot_token)
            if not ok:
                flash(
                    _tr('Входящие из Telegram работают, но ответы бота с этого ПК не отправляются: ')
                    + _tr_msg(detail),
                    'warning',
                )
        return redirect(url_for('integrations'))
    tg_api_ok = None
    tg_api_detail = None
    if current_user.telegram_bot_token:
        tg_api_ok, raw_detail = check_telegram_api(current_user.telegram_bot_token)
        if raw_detail and raw_detail.startswith("@"):
            tg_api_detail = raw_detail
        else:
            tg_api_detail = _tr_msg(raw_detail) if raw_detail else None
    return render_template(
        'integrations.html',
        telegram_api_ok=tg_api_ok,
        telegram_api_detail=tg_api_detail,
    )

@app.route('/inbox')
@login_required
def inbox():
    msgs = (
        InboundMessage.query.filter_by(user_id=current_user.tenant_id)
        .order_by(InboundMessage.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template('inbox.html', messages=msgs)

@app.route('/calendar')
@login_required
def calendar():
    calendar_ctx = _prepare_calendar(current_user.tenant_id, 'calendar', None)
    return render_template(
        'calendar.html',
        **calendar_ctx,
    )

@app.route('/services', methods=['GET', 'POST'])
@login_required
def manage_services():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            flash(_tr('Введите название услуги'), 'error')
            return redirect(url_for('manage_services'))
        price = _parse_positive_float(request.form.get('price', '0'), 'Цена')
        if price is None:
            return redirect(url_for('manage_services'))
        duration = request.form.get('duration_minutes', type=int)
        if not duration or duration < 5 or duration > 24 * 60:
            flash(_tr('Длительность: от 5 до 1440 минут'), 'error')
            return redirect(url_for('manage_services'))
        max_pos = (
            db.session.query(db.func.max(CatalogService.position))
            .filter_by(user_id=current_user.tenant_id)
            .scalar()
        ) or 0
        db.session.add(
            CatalogService(
                user_id=current_user.tenant_id,
                name=name[:200],
                price=price,
                duration_minutes=duration,
                position=max_pos + 1,
            )
        )
        db.session.commit()
        flash(_tr('Услуга добавлена в каталог'), 'success')
        return redirect(url_for('manage_services'))

    services = (
        CatalogService.query.filter_by(user_id=current_user.tenant_id)
        .order_by(CatalogService.position.asc(), CatalogService.id.asc())
        .all()
    )
    return render_template('services.html', services=services)


@app.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
def delete_catalog_service(service_id):
    svc = CatalogService.query.filter_by(
        id=service_id, user_id=current_user.tenant_id
    ).first_or_404()
    db.session.delete(svc)
    db.session.commit()
    flash(_tr('Услуга удалена из каталога'), 'info')
    return redirect(url_for('manage_services'))


@app.route('/appointment/new', methods=['GET', 'POST'])
@login_required
def appointment_new():
    clients = Client.query.filter_by(user_id=current_user.tenant_id).order_by(Client.name).all()
    catalog_services = (
        CatalogService.query.filter_by(user_id=current_user.tenant_id)
        .order_by(CatalogService.position.asc(), CatalogService.id.asc())
        .all()
    )
    preselect_client_id = request.args.get('client_id', type=int)
    preselect_service_id = request.args.get('service_id', type=int)
    default_start = ''
    default_end = ''
    date_arg = request.args.get('date', '').strip()
    if date_arg:
        try:
            d = datetime.strptime(date_arg, '%Y-%m-%d')
            default_start = d.replace(hour=10, minute=0).strftime('%Y-%m-%dT%H:%M')
            default_end = d.replace(hour=11, minute=0).strftime('%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    if preselect_client_id:
        ok = Client.query.filter_by(
            id=preselect_client_id, user_id=current_user.tenant_id
        ).first()
        if not ok:
            preselect_client_id = None

    if preselect_service_id:
        ok_svc = catalog_service_for_user(current_user.tenant_id, preselect_service_id)
        if not ok_svc:
            preselect_service_id = None

    def _back_to_form(cid=None):
        if cid:
            return redirect(url_for('appointment_new', client_id=cid))
        return redirect(url_for('appointment_new'))

    if request.method == 'POST':
        form_cid = request.form.get('client_id', type=int) or preselect_client_id
        catalog_service_id = request.form.get('catalog_service_id', type=int)
        catalog = catalog_service_for_user(current_user.tenant_id, catalog_service_id)

        title = (request.form.get('title') or '').strip()
        if catalog and not title:
            title = catalog.name
        if not title:
            flash(_tr('Укажите услугу или выберите из каталога'), 'error')
            return _back_to_form(form_cid)

        try:
            start_at = datetime.strptime(request.form['start_at'], '%Y-%m-%dT%H:%M')
            end_at = datetime.strptime(request.form['end_at'], '%Y-%m-%dT%H:%M')
        except (KeyError, ValueError):
            flash(_tr('Некорректная дата или время'), 'error')
            return _back_to_form(form_cid)

        if catalog:
            expected_end = start_at + timedelta(minutes=catalog.duration_minutes)
            if request.form.get('use_catalog_duration') == '1':
                end_at = expected_end

        if end_at <= start_at:
            flash(_tr('Окончание должно быть позже начала'), 'error')
            return _back_to_form(form_cid)

        price = None
        if catalog:
            price = catalog.price
        else:
            raw_price = (request.form.get('price') or '').strip()
            if raw_price:
                price = _parse_positive_float(raw_price, 'Стоимость')
                if price is None:
                    return _back_to_form(form_cid)

        repeat = (request.form.get('repeat') or '').strip()
        if repeat and repeat not in {c[0] for c in RECURRENCE_CHOICES if c[0]}:
            flash(_tr('Некорректный тип повторения'), 'error')
            return _back_to_form(form_cid)

        repeat_until_date = None
        repeat_count = request.form.get('repeat_count', type=int) or 12
        if repeat:
            if request.form.get('repeat_end_type') == 'date':
                raw_until = (request.form.get('repeat_until') or '').strip()
                if not raw_until:
                    flash(_tr('Укажите дату окончания повторений'), 'error')
                    return _back_to_form(form_cid)
                repeat_until_date = _parse_date_only(raw_until)
                if not repeat_until_date:
                    flash(_tr('Некорректная дата окончания'), 'error')
                    return _back_to_form(form_cid)
                if repeat_until_date < start_at.date():
                    flash(_tr('Дата окончания не может быть раньше начала'), 'error')
                    return _back_to_form(form_cid)
            else:
                repeat_count = max(2, min(repeat_count, 52))

        duration = end_at - start_at
        starts = build_recurrence_starts(
            start_at,
            repeat,
            until_date=repeat_until_date,
            count=repeat_count if repeat else 1,
        )
        series_id = uuid.uuid4().hex if repeat else None

        cid = request.form.get('client_id')
        client_id = int(cid) if cid else None
        if client_id:
            ok = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first()
            if not ok:
                flash(_tr('Клиент не найден'), 'error')
                return redirect(url_for('appointment_new'))

        notes = (request.form.get('notes') or '').strip()
        if price is not None and price > 0 and '₽' not in notes:
            notes = f"Стоимость: {price:.0f} ₽. {notes}".strip()

        staff_id = _staff_id_from_form(
            request.form.get('staff_id'), current_user.tenant_id
        )
        created = 0
        for occ_start in starts:
            occ_end = occ_start + duration
            if _appointment_overlaps(current_user.tenant_id, occ_start, occ_end):
                flash(
                    translate_named(
                        _current_lang(),
                        "Конфликт: на {datetime} уже есть запись",
                        datetime=occ_start.strftime("%d.%m.%Y %H:%M"),
                    ),
                    'error',
                )
                return _back_to_form(form_cid)
            db.session.add(
                Appointment(
                    user_id=current_user.tenant_id,
                    client_id=client_id,
                    catalog_service_id=catalog.id if catalog else None,
                    title=title,
                    price=price,
                    start_at=occ_start,
                    end_at=occ_end,
                    status='scheduled',
                    source='manual',
                    notes=notes,
                    staff_id=staff_id,
                    recurrence_series_id=series_id,
                    recurrence_rule=repeat if series_id else None,
                )
            )
            created += 1

        db.session.commit()
        if created == 1:
            flash(_tr('Запись создана'), 'success')
        else:
            flash(
                translate_named(
                    _current_lang(),
                    "Создано записей: {count} ({repeat})",
                    count=str(created),
                    repeat=_tr(recurrence_label(repeat)),
                ),
                'success',
            )
        if client_id:
            return redirect(url_for('client_detail', client_id=client_id))
        return redirect(url_for('calendar'))

    return render_template(
        'appointment_new.html',
        clients=clients,
        catalog_services=catalog_services,
        staff_list=_active_staff_for_tenant(current_user.tenant_id),
        recurrence_choices=RECURRENCE_CHOICES,
        preselect_client_id=preselect_client_id,
        preselect_service_id=preselect_service_id,
        default_start=default_start,
        default_end=default_end,
    )

def _redirect_after_appointment_action():
    return redirect(request.referrer or url_for('calendar'))


def _appointment_edit_redirect(ap: Appointment, return_to: str | None = None) -> str:
    if return_to == 'client' and ap.client_id:
        return url_for('client_detail', client_id=ap.client_id)
    return url_for('calendar')


@app.route('/appointment/<int:appointment_id>/edit', methods=['GET', 'POST'])
@login_required
def appointment_edit(appointment_id: int):
    ap = Appointment.query.filter_by(
        id=appointment_id, user_id=current_user.tenant_id
    ).first_or_404()
    clients = Client.query.filter_by(user_id=current_user.tenant_id).order_by(Client.name).all()
    catalog_services = (
        CatalogService.query.filter_by(user_id=current_user.tenant_id)
        .order_by(CatalogService.position.asc(), CatalogService.id.asc())
        .all()
    )
    return_to = request.args.get('ref', '').strip()
    if return_to not in ('client', 'calendar'):
        return_to = 'client' if ap.client_id else 'calendar'

    def _edit_url() -> str:
        return url_for('appointment_edit', appointment_id=ap.id, ref=return_to)

    if request.method == 'POST':
        return_to = (request.form.get('return_to') or return_to).strip()
        if return_to not in ('client', 'calendar'):
            return_to = 'client' if ap.client_id else 'calendar'

        catalog_service_id = request.form.get('catalog_service_id', type=int)
        catalog = catalog_service_for_user(current_user.tenant_id, catalog_service_id)

        title = (request.form.get('title') or '').strip()
        if catalog and not title:
            title = catalog.name
        if not title:
            flash(_tr('Укажите услугу или выберите из каталога'), 'error')
            return redirect(_edit_url())

        try:
            start_at = datetime.strptime(request.form['start_at'], '%Y-%m-%dT%H:%M')
            end_at = datetime.strptime(request.form['end_at'], '%Y-%m-%dT%H:%M')
        except (KeyError, ValueError):
            flash(_tr('Некорректная дата или время'), 'error')
            return redirect(_edit_url())

        if catalog and request.form.get('use_catalog_duration') == '1':
            end_at = start_at + timedelta(minutes=catalog.duration_minutes)

        if end_at <= start_at:
            flash(_tr('Окончание должно быть позже начала'), 'error')
            return redirect(_edit_url())

        status = (request.form.get('status') or 'scheduled').strip()
        if status not in ('scheduled', 'cancelled'):
            status = 'scheduled'

        if status == 'scheduled' and _appointment_overlaps(
            current_user.tenant_id, start_at, end_at, exclude_id=ap.id
        ):
            flash(
                translate_named(
                    _current_lang(),
                    "Конфликт: на {datetime} уже есть запись",
                    datetime=start_at.strftime("%d.%m.%Y %H:%M"),
                ),
                'error',
            )
            return redirect(_edit_url())

        price = None
        if catalog:
            price = catalog.price
        else:
            raw_price = (request.form.get('price') or '').strip()
            if raw_price:
                price = _parse_positive_float(raw_price, 'Стоимость')
                if price is None:
                    return redirect(_edit_url())

        cid = request.form.get('client_id')
        client_id = int(cid) if cid else None
        if client_id:
            ok = Client.query.filter_by(id=client_id, user_id=current_user.tenant_id).first()
            if not ok:
                flash(_tr('Клиент не найден'), 'error')
                return redirect(_edit_url())

        ap.title = title
        ap.client_id = client_id
        ap.catalog_service_id = catalog.id if catalog else None
        ap.price = price
        ap.start_at = start_at
        ap.end_at = end_at
        ap.status = status
        ap.notes = (request.form.get('notes') or '').strip() or None
        ap.staff_id = _staff_id_from_form(
            request.form.get('staff_id'), current_user.tenant_id
        )
        db.session.commit()
        flash(_tr('Запись обновлена'), 'success')
        return redirect(_appointment_edit_redirect(ap, return_to))

    return render_template(
        'edit_appointment.html',
        appointment=ap,
        clients=clients,
        catalog_services=catalog_services,
        staff_list=_active_staff_for_tenant(current_user.tenant_id),
        return_to=return_to,
    )


@app.route('/appointment/<int:appointment_id>/cancel', methods=['POST'])
@login_required
def appointment_cancel(appointment_id):
    ap = Appointment.query.filter_by(
        id=appointment_id, user_id=current_user.tenant_id
    ).first_or_404()
    if ap.status != 'cancelled':
        ap.status = 'cancelled'
        db.session.commit()
        flash(_tr('Запись отменена'), 'info')
    return _redirect_after_appointment_action()


@app.route('/appointment/<int:appointment_id>/delete', methods=['POST'])
@login_required
def appointment_delete(appointment_id):
    ap = Appointment.query.filter_by(
        id=appointment_id, user_id=current_user.tenant_id
    ).first_or_404()
    db.session.delete(ap)
    db.session.commit()
    flash(_tr('Запись удалена'), 'success')
    return _redirect_after_appointment_action()

@app.route('/staff', methods=['GET', 'POST'])
@login_required
def manage_staff():
    tid = current_user.tenant_id
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            flash(_tr('Укажите имя сотрудника'), 'error')
            return redirect(url_for('manage_staff'))
        staff = Staff(
            user_id=tid,
            name=name,
            role_title=(request.form.get('role_title') or '').strip() or None,
            phone=(request.form.get('phone') or '').strip() or None,
        )
        db.session.add(staff)
        db.session.commit()
        flash(_tr('Сотрудник добавлен'), 'success')
        return redirect(url_for('manage_staff'))

    staff_list = Staff.query.filter_by(user_id=tid).order_by(Staff.name).all()
    return render_template('staff.html', staff_list=staff_list)


@app.route('/staff/<int:staff_id>/toggle', methods=['POST'])
@login_required
def staff_toggle(staff_id):
    st = Staff.query.filter_by(id=staff_id, user_id=current_user.tenant_id).first_or_404()
    st.active = not st.active
    db.session.commit()
    flash(_tr('Статус сотрудника обновлён'), 'success')
    return redirect(url_for('manage_staff'))


@app.route('/staff/<int:staff_id>/delete', methods=['POST'])
@login_required
def staff_delete(staff_id):
    st = Staff.query.filter_by(id=staff_id, user_id=current_user.tenant_id).first_or_404()
    Order.query.filter_by(staff_id=st.id).update({'staff_id': None})
    Appointment.query.filter_by(staff_id=st.id).update({'staff_id': None})
    db.session.delete(st)
    db.session.commit()
    flash(_tr('Сотрудник удалён'), 'success')
    return redirect(url_for('manage_staff'))


@app.route('/admins', methods=['GET', 'POST'])
@owner_required
def manage_admins():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        if not email or len(password) < 6:
            flash(_tr('Email и пароль (мин. 6 символов) обязательны'), 'error')
            return redirect(url_for('manage_admins'))
        if User.query.filter_by(email=email).first():
            flash(_tr('Пользователь с таким email уже существует'), 'error')
            return redirect(url_for('manage_admins'))
        admin = User(
            email=email,
            business_name=current_user.business_name,
            business_type=current_user.business_type,
            business_description=current_user.business_description,
            role='admin',
            owner_id=current_user.id,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        flash(_tr('Администратор создан'), 'success')
        return redirect(url_for('manage_admins'))

    admins = User.query.filter_by(owner_id=current_user.id, role='admin').order_by(User.email).all()
    return render_template('admins.html', admins=admins)


@app.route('/admins/<int:admin_id>/password', methods=['POST'])
@owner_required
def admin_set_password(admin_id):
    admin = User.query.filter_by(
        id=admin_id, owner_id=current_user.id, role='admin'
    ).first_or_404()
    password = request.form.get('password') or ''
    if len(password) < 6:
        flash(_tr('Пароль должен быть не короче 6 символов'), 'error')
        return redirect(url_for('manage_admins'))
    admin.set_password(password)
    db.session.commit()
    flash(_tr('Пароль администратора обновлён'), 'success')
    return redirect(url_for('manage_admins'))


@app.route('/admins/<int:admin_id>/delete', methods=['POST'])
@owner_required
def admin_delete(admin_id):
    admin = User.query.filter_by(
        id=admin_id, owner_id=current_user.id, role='admin'
    ).first_or_404()
    db.session.delete(admin)
    db.session.commit()
    flash(_tr('Администратор удалён'), 'success')
    return redirect(url_for('manage_admins'))


@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def manage_expenses():
    tid = current_user.tenant_id
    if request.method == 'POST':
        amount = _parse_positive_float(request.form.get('amount'), 'Сумма')
        if amount is None:
            return redirect(url_for('manage_expenses'))
        desc = (request.form.get('description') or '').strip() or _tr('Расход')
        category = (request.form.get('category') or '').strip() or None
        date_raw = (request.form.get('expense_date') or '').strip()
        expense_date = datetime.utcnow()
        if date_raw:
            parsed = _parse_date_only(date_raw)
            if parsed:
                expense_date = datetime.combine(parsed, time.min)
        db.session.add(
            BusinessExpense(
                user_id=tid,
                amount=amount,
                description=desc,
                category=category,
                expense_date=expense_date,
            )
        )
        db.session.commit()
        flash(_tr('Расход добавлен'), 'success')
        return redirect(url_for('manage_expenses'))

    expenses = (
        BusinessExpense.query.filter_by(user_id=tid)
        .order_by(BusinessExpense.expense_date.desc())
        .all()
    )
    return render_template('expenses.html', expenses=expenses)


@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
def expense_delete(expense_id):
    exp = BusinessExpense.query.filter_by(
        id=expense_id, user_id=current_user.tenant_id
    ).first_or_404()
    db.session.delete(exp)
    db.session.commit()
    flash(_tr('Расход удалён'), 'success')
    return redirect(url_for('manage_expenses'))


@app.route('/order/<int:order_id>/expense', methods=['POST'])
@login_required
def add_order_expense(order_id):
    order = Order.query.join(Client).filter(
        Order.id == order_id,
        Client.user_id == current_user.tenant_id,
    ).first_or_404()
    amount = _parse_positive_float(request.form.get('amount'), 'Сумма')
    if amount is None:
        return redirect(url_for('edit_order', order_id=order_id))
    desc = (request.form.get('description') or '').strip() or _tr('Расход по заказу')
    db.session.add(
        OrderExpense(order_id=order.id, amount=amount, description=desc)
    )
    db.session.commit()
    flash(_tr('Расход по заказу добавлен'), 'success')
    return redirect(url_for('edit_order', order_id=order_id))


@app.route('/order-expense/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_order_expense(expense_id):
    exp = (
        OrderExpense.query.join(Order)
        .join(Client)
        .filter(
            OrderExpense.id == expense_id,
            Client.user_id == current_user.tenant_id,
        )
        .first_or_404()
    )
    order_id = exp.order_id
    db.session.delete(exp)
    db.session.commit()
    flash(_tr('Расход удалён'), 'success')
    return redirect(url_for('edit_order', order_id=order_id))


@app.route('/help')
@login_required
def user_guide():
    return render_template('user_guide.html')


@app.route('/reports')
@login_required
def reports():
    data = build_reports_dashboard(current_user.tenant_id)
    return render_template('reports.html', report=data)


@app.route('/reports/export.csv')
@login_required
def reports_export():
    csv_text = build_reports_csv(current_user.tenant_id)
    resp = make_response('\ufeff' + csv_text)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename=crm_reports.csv'
    return resp


def bootstrap_database() -> None:
    with app.app_context():
        from schema_migrations import apply_all_sqlite_migrations

        db.create_all()
        apply_all_sqlite_migrations(app)
        seen_tenants: set[int] = set()
        for user in User.query.all():
            tid = user.tenant_id
            if tid in seen_tenants:
                continue
            seen_tenants.add(tid)
            ensure_user_statuses(tid)
            default_st = default_status_for_user(tid)
            if default_st:
                Client.query.filter_by(user_id=tid, status_id=None).update(
                    {'status_id': default_st.id}
                )
        db.session.commit()


if __name__ == '__main__':
    bootstrap_database()
    host = os.getenv("FLASK_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    if host == "0.0.0.0":
        print(f"CRM: http://127.0.0.1:{port}  (LAN: http://<ваш-IP>:{port})")
        if public_url_configured():
            print(f"Публичный URL: {os.getenv('PUBLIC_BASE_URL', '').strip()}")
        else:
            print("Публичный тест: docs/PUBLIC_TEST_RU.md  (ngrok + PUBLIC_BASE_URL в .env)")
    app.run(host=host, port=port, debug=debug)