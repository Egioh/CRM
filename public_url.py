"""Публичный базовый URL для вебхуков и ссылок за reverse proxy (ngrok, Cloudflare Tunnel)."""

from __future__ import annotations

import os

from flask import has_request_context, request


def public_base_url_from_env() -> str:
    return os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")


def public_url_configured() -> bool:
    return bool(public_base_url_from_env())


def resolve_public_url_root() -> str:
    """Корень сайта с завершающим слэшем — для вебхуков и интеграций."""
    base = public_base_url_from_env()
    if base:
        return f"{base}/"
    if has_request_context():
        return request.url_root
    return "http://127.0.0.1:5000/"


def configure_proxy_and_cookies(app) -> None:
    """HTTPS cookies и доверие X-Forwarded-* за туннелем."""
    public = public_base_url_from_env()
    if public.startswith("https://"):
        if not os.getenv("SESSION_COOKIE_SECURE", "").strip():
            app.config["SESSION_COOKIE_SECURE"] = True

    trust = os.getenv("TRUST_PROXY", "").strip().lower()
    auto_trust = bool(public)
    if trust in {"1", "true", "yes"} or (auto_trust and trust not in {"0", "false", "no"}):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
