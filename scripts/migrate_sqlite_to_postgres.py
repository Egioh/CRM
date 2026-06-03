#!/usr/bin/env python3
"""
Перенос данных из SQLite в PostgreSQL.

Порядок:
  python scripts/bootstrap_postgres.py
  python scripts/migrate_sqlite_to_postgres.py

Переменные:
  SQLITE_URL   — по умолчанию sqlite:///instance/crm.db
  POSTGRES_URL — postgresql+psycopg2://user:pass@localhost:5432/crm
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import MetaData, create_engine, func, inspect, select, text

_TABLE_COPY_ORDER: list[str] = [
    "user",
    "client_status",
    "staff",
    "catalog_service",
    "client",
    "client_comment",
    "client_reminder",
    "client_status_history",
    "order",
    "order_expense",
    "payment",
    "appointment",
    "business_expense",
    "inbound_message",
    "telegram_conversation_state",
]


def _ordered_tables(src_meta: MetaData, dst_names: set[str]) -> list:
    by_name = {t.name: t for t in src_meta.tables.values() if t.name in dst_names}
    ordered = [by_name[n] for n in _TABLE_COPY_ORDER if n in by_name]
    tail = [t for n, t in by_name.items() if n not in _TABLE_COPY_ORDER]
    return ordered + tail


_ROW_DEFAULTS: dict[str, dict[str, object]] = {
    "user": {
        "role": "owner",
        "telegram_ai_language": "auto",
        "telegram_ai_tone": "friendly",
        "telegram_ai_timezone": "UTC",
        "telegram_ai_slot_minutes": 30,
        "telegram_ai_min_duration_minutes": 30,
        "telegram_ai_enabled": False,
        "telegram_ai_require_name": True,
        "telegram_ai_require_phone": True,
    },
}


def _sqlalchemy_column_default(col) -> object | None:
    if col.default is None:
        return None
    arg = getattr(col.default, "arg", None)
    if arg is None:
        return None
    return arg() if callable(arg) else arg


def _prepare_row(row: dict, dst_table) -> dict:
    dst_columns = {c.name for c in dst_table.columns}
    out = {k: row[k] for k in row.keys() if k in dst_columns}
    table_name = dst_table.name
    for key, default in _ROW_DEFAULTS.get(table_name, {}).items():
        if key in dst_columns and (key not in out or out[key] is None):
            out[key] = default
    for col in dst_table.columns:
        if col.name not in dst_columns:
            continue
        if not col.nullable and (col.name not in out or out[col.name] is None):
            default = _sqlalchemy_column_default(col)
            if default is not None:
                out[col.name] = default
    return out


def _reset_pg_sequences(conn, table_name: str, pk_column: str) -> None:
    conn.execute(
        text(
            f"""
            SELECT setval(
                pg_get_serial_sequence(:tbl, :col),
                COALESCE((SELECT MAX({pk_column}) FROM {table_name}), 1),
                true
            )
            """
        ),
        {"tbl": table_name, "col": pk_column},
    )


def migrate(sqlite_url: str, postgres_url: str, dry_run: bool = False) -> None:
    src_engine = create_engine(sqlite_url)
    dst_engine = None if dry_run else create_engine(postgres_url)

    if not inspect(src_engine).get_table_names():
        print("SQLite: нет таблиц — нечего переносить.", file=sys.stderr)
        sys.exit(1)

    src_meta = MetaData()
    src_meta.reflect(bind=src_engine)

    if dry_run:
        with src_engine.connect() as src_conn:
            for table in src_meta.sorted_tables:
                n = src_conn.execute(
                    select(func.count()).select_from(table)
                ).scalar()
                print(f"would copy {table.name}: {n} rows")
        print("(dry-run: подключение к PostgreSQL не требуется)")
        return

    dst_meta = MetaData()
    dst_meta.reflect(bind=dst_engine)
    dst_names = set(inspect(dst_engine).get_table_names())
    if not dst_names:
        print(
            "PostgreSQL: нет таблиц. Сначала: python scripts/bootstrap_postgres.py",
            file=sys.stderr,
        )
        sys.exit(1)
    tables = _ordered_tables(src_meta, dst_names)
    for t in src_meta.tables.values():
        if t.name not in dst_names:
            print(f"skip: {t.name} (нет в PostgreSQL)")

    total = 0
    sequence_tables: list[tuple[str, str]] = []
    with src_engine.connect() as src_conn, dst_engine.begin() as dst_conn:
        tbl_list = ", ".join(f'"{t.name}"' for t in tables)
        dst_conn.execute(text(f"TRUNCATE TABLE {tbl_list} RESTART IDENTITY CASCADE"))

        for table in tables:
            raw_rows = src_conn.execute(table.select()).mappings().all()
            dst_table = dst_meta.tables[table.name]
            rows = [_prepare_row(dict(r), dst_table) for r in raw_rows]
            if rows:
                dst_conn.execute(dst_table.insert(), rows)
            pk_cols = list(table.primary_key.columns)
            if len(pk_cols) == 1 and rows:
                sequence_tables.append((table.name, pk_cols[0].name))
            print(f"{table.name}: {len(rows)} rows")
            total += len(rows)

    with dst_engine.begin() as dst_conn:
        for table_name, pk_column in sequence_tables:
            try:
                _reset_pg_sequences(dst_conn, table_name, pk_column)
            except Exception:
                pass

    print(f"Готово. Перенесено строк: {total}.")


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_sqlite = "sqlite:///" + os.path.join(root, "instance", "crm.db").replace(
        "\\", "/"
    )

    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL")
    parser.add_argument("--sqlite", default=os.environ.get("SQLITE_URL", default_sqlite))
    parser.add_argument("--postgres", default=os.environ.get("POSTGRES_URL", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    postgres_url = (args.postgres or "").strip()
    if not postgres_url:
        print("Задайте POSTGRES_URL или --postgres", file=sys.stderr)
        sys.exit(1)

    migrate(args.sqlite, postgres_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
