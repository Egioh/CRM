#!/usr/bin/env python3
"""Создать таблицы и применить миграции колонок в PostgreSQL (пустая БД)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

POSTGRES_URL = os.environ.get("POSTGRES_URL", "").strip() or os.environ.get(
    "DATABASE_URL", ""
).strip()
if not POSTGRES_URL or not POSTGRES_URL.lower().startswith("postgresql"):
    print("Задайте POSTGRES_URL=postgresql+psycopg2://...", file=sys.stderr)
    sys.exit(1)

os.environ["DATABASE_URL"] = POSTGRES_URL

from app import app, bootstrap_database  # noqa: E402

if __name__ == "__main__":
    print(f"Bootstrap: {POSTGRES_URL.split('@')[-1]}")
    bootstrap_database()
    print("Таблицы и миграции применены.")
