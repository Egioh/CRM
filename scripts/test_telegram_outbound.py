"""Проверка исходящего доступа к api.telegram.org (ответы бота)."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from app import app  # noqa: E402
from messaging_outbound import check_telegram_api, telegram_https_proxy  # noqa: E402
from models import User  # noqa: E402


def main() -> None:
    proxy = telegram_https_proxy()
    print("TELEGRAM_HTTPS_PROXY / HTTPS_PROXY:", proxy or "(not set)")
    with app.app_context():
        users = User.query.filter(
            User.telegram_bot_token.isnot(None),
            User.telegram_ai_enabled.is_(True),
        ).all()
        if not users:
            print("No tenant with telegram_ai_enabled and bot token.")
            return
        for u in users:
            print(f"\n--- {u.email or u.id} ---")
            ok, detail = check_telegram_api(u.telegram_bot_token)
            print("OK" if ok else "FAIL", detail)


if __name__ == "__main__":
    main()
