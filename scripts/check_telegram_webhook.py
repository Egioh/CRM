"""Print Telegram getWebhookInfo and expected CRM webhook URL for each tenant with a bot."""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from app import app  # noqa: E402
from models import User  # noqa: E402
from public_url import public_base_url_from_env  # noqa: E402


def main() -> None:
    base = public_base_url_from_env()
    if not base:
        print("WARN: PUBLIC_BASE_URL is not set in .env")
    print(f"PUBLIC_BASE_URL: {base or '(not set)'}\n")

    with app.app_context():
        users = User.query.filter(User.telegram_bot_token.isnot(None)).all()
        if not users:
            print("No users with telegram_bot_token in database.")
            return

        tokens_seen: dict[str, list[str]] = {}
        for u in users:
            key = (u.telegram_bot_token or "")[:20]
            tokens_seen.setdefault(key, []).append(u.email or f"user#{u.id}")

        for key, emails in tokens_seen.items():
            if len(emails) > 1:
                print(
                    "WARN: Same bot token on multiple accounts:",
                    ", ".join(emails),
                    "\n      Only ONE webhook URL works per bot. Use one CRM account.\n",
                )

        for u in users:
            print("---", u.email or f"user#{u.id}")
            print("  AI enabled:", u.telegram_ai_enabled)
            print("  webhook path token:", u.telegram_webhook_token)
            expected = (
                f"{base}/webhooks/telegram/{u.telegram_webhook_token}"
                if base and u.telegram_webhook_token
                else "(set PUBLIC_BASE_URL and save integrations)"
            )
            print("  expected URL:", expected)
            if not u.telegram_bot_token:
                continue
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{u.telegram_bot_token}/getWebhookInfo",
                    timeout=20,
                )
                info = r.json().get("result") or {}
            except requests.RequestException as e:
                print("  getWebhookInfo ERROR:", e)
                print("  (Telegram API unreachable from this PC?)")
                continue
            print("  Telegram webhook_url:", info.get("url") or "(empty)")
            print("  pending updates:", info.get("pending_update_count"))
            err = info.get("last_error_message")
            if err:
                print("  last_error:", err)
            if expected and info.get("url") and info.get("url") != expected:
                print("  >>> MISMATCH: setWebhook must use expected URL exactly <<<")
            print()


if __name__ == "__main__":
    main()
