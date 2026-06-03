#!/usr/bin/env python3
"""Проверка подключения к БД из .env / DATABASE_URL."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

url = os.getenv("DATABASE_URL", "")
if not url:
    print("DATABASE_URL не задан в .env", file=sys.stderr)
    sys.exit(1)

os.environ["DATABASE_URL"] = url

from app import app, db  # noqa: E402
from models import Client, User  # noqa: E402

with app.app_context():
    users = User.query.count()
    clients = Client.query.count()
    engine = db.engine.url.drivername
    print(f"OK  driver={engine}")
    print(f"    users={users}  clients={clients}")
    if url.lower().startswith("postgresql") and users == 0:
        print("WARN: PostgreSQL подключён, но пользователей 0 — проверьте миграцию.", file=sys.stderr)
        sys.exit(2)
