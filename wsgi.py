"""Точка входа для Waitress / других WSGI-серверов (публичный тест)."""

from app import app, bootstrap_database

bootstrap_database()
