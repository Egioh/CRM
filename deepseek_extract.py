from __future__ import annotations

import json
import os
from typing import Any, Optional

import requests


def _api_key() -> str:
    return (os.getenv("DEEPSEEK_API_KEY") or "").strip()


def extract_intent_and_entities(
    *,
    business_name: str,
    services: list[dict[str, Any]],
    user_timezone: str,
    text: str,
) -> Optional[dict[str, Any]]:
    """
    Uses DeepSeek Chat Completions API to extract structured intent/entities from a user message.

    Returns a dict like:
      {
        "intent": "services_list|book|handoff|unknown",
        "service_name": "...",
        "when_text": "...",   # e.g. "завтра 15:30" or "05.06 15:30"
        "contact_name": "...",
        "contact_phone": "...",
        "confidence": 0.0-1.0
      }
    or None when not configured / failed.
    """
    key = _api_key()
    if not key:
        return None

    model = (os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash").strip()
    url = "https://api.deepseek.com/chat/completions"

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent": {"type": "string"},
            "service_name": {"type": ["string", "null"]},
            "when_text": {"type": ["string", "null"]},
            "contact_name": {"type": ["string", "null"]},
            "contact_phone": {"type": ["string", "null"]},
            "confidence": {"type": "number"},
        },
        "required": ["intent", "confidence"],
    }

    system = (
        "Ты универсальный ассистент онлайн-записи. "
        "Твоя задача — понять намерение пользователя и извлечь поля строго в JSON. "
        "Никакого текста, только JSON."
    )
    user = {
        "business_name": business_name,
        "timezone": user_timezone,
        "services": services[:50],
        "message": text,
        "allowed_intents": ["services_list", "book", "handoff", "unknown"],
        "output_schema": schema,
    }

    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "stream": False,
        # avoid reasoning_content requirements by disabling thinking mode
        "thinking": {"type": "disabled"},
        # ask for strict JSON output (DeepSeek supports JSON output mode)
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 600,
    }

    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=15,
        )
    except requests.RequestException:
        return None

    if r.status_code != 200:
        return None
    try:
        data = r.json()
        content = (((data.get("choices") or [])[0] or {}).get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        out = json.loads(content)
        return out if isinstance(out, dict) else None
    except Exception:
        return None

