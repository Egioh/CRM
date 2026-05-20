from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    business_name = db.Column(db.String(100), nullable=False)
    business_type = db.Column(db.String(100), nullable=False)
    business_description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # WhatsApp Cloud API: metadata.phone_number_id в вебхуке — сопоставление с владельцем CRM
    whatsapp_phone_number_id = db.Column(db.String(64), nullable=True, unique=True)

    clients = db.relationship('Client', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ClientStatus(db.Model):
    """Статус воронки клиента; владелец может добавлять свои."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    color = db.Column(db.String(20), nullable=False, default='secondary')
    position = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship('User', backref=db.backref('client_statuses', lazy='dynamic'))
    clients = db.relationship('Client', backref='status', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_client_status_user_name'),
    )


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status_id = db.Column(db.Integer, db.ForeignKey('client_status.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    telegram_chat_id = db.Column(db.String(64), nullable=True, index=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='client', lazy=True, cascade="all, delete-orphan")
    payments = db.relationship('Payment', backref='client', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship(
        'ClientComment',
        backref='client',
        lazy=True,
        cascade='all, delete-orphan',
    )
    reminders = db.relationship(
        'ClientReminder',
        backref='client',
        lazy=True,
        cascade='all, delete-orphan',
    )
    status_history = db.relationship(
        'ClientStatusHistory',
        backref='client',
        lazy=True,
        cascade='all, delete-orphan',
    )


class ClientComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    service = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    method = db.Column(db.String(50))
    notes = db.Column(db.Text)


class InboundMessage(db.Model):
    """Сообщение из внешнего канала (WhatsApp / Telegram), привязка к владельцу CRM по правилам в messaging.py."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    channel = db.Column(db.String(20), nullable=False)
    external_sender_id = db.Column(db.String(64), nullable=False, index=True)
    external_chat_id = db.Column(db.String(64), nullable=True)
    wa_phone_number_id = db.Column(db.String(64), nullable=True)
    body = db.Column(db.Text, default='')
    raw_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('inbound_messages', lazy='dynamic'))
    client = db.relationship('Client', backref=db.backref('inbound_messages', lazy='dynamic'))


class ClientReminder(db.Model):
    """Напоминание перезвонить / связаться с клиентом."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    due_at = db.Column(db.DateTime, nullable=False)
    body = db.Column(db.String(500), nullable=False, default='')
    done = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('client_reminders', lazy='dynamic'))


class CatalogService(db.Model):
    """Услуга из прайса владельца: название, цена, длительность."""

    __tablename__ = "catalog_service"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("catalog_services", lazy="dynamic"))


class ClientStatusHistory(db.Model):
    """История смены статуса клиента."""

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    old_status_id = db.Column(db.Integer, db.ForeignKey('client_status.id'), nullable=True)
    new_status_id = db.Column(db.Integer, db.ForeignKey('client_status.id'), nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    old_status = db.relationship('ClientStatus', foreign_keys=[old_status_id])
    new_status = db.relationship('ClientStatus', foreign_keys=[new_status_id])


class Appointment(db.Model):
    """Запись на приём / слот в календаре владельца CRM."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    catalog_service_id = db.Column(
        db.Integer, db.ForeignKey('catalog_service.id'), nullable=True
    )
    title = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=True)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='scheduled')
    source = db.Column(db.String(20), nullable=False, default='manual')
    notes = db.Column(db.Text)
    recurrence_series_id = db.Column(db.String(36), nullable=True, index=True)
    recurrence_rule = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('appointments', lazy='dynamic'))
    client = db.relationship('Client', backref=db.backref('appointments', lazy='dynamic'))
    catalog_service = db.relationship('CatalogService', backref='appointments')