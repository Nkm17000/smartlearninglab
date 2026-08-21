"""Provider-agnostic AI service for Smart Learning Lab.
Uses an OpenAI-compatible chat-completions endpoint when AI_API_KEY is set.
Falls back to deterministic, context-grounded responses so the app remains usable.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error
from typing import Any


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def configured() -> bool:
    return bool(_env("AI_API_KEY") or _env("OPENAI_API_KEY") or _env("GROQ_API_KEY"))


def _config():
    key = _env("AI_API_KEY") or _env("OPENAI_API_KEY") or _env("GROQ_API_KEY")
    base = _env("AI_BASE_URL")
    if not base:
        base = "https://api.groq.com/openai/v1" if _env("GROQ_API_KEY") and not _env("OPENAI_API_KEY") else "https://api.openai.com/v1"
    model = _env("AI_MODEL") or (_env("GROQ_MODEL", "llama-3.3-70b-versatile") if _env("GROQ_API_KEY") and not _env("OPENAI_API_KEY") else _env("OPENAI_MODEL", "gpt-4o-mini"))
    return key, base.rstrip("/"), model


def chat(system: str, user: str, history: list[dict[str, str]] | None = None, temperature: float = 0.2) -> str | None:
    key, base, model = _config()
    if not key:
        return None
    messages = [{"role": "system", "content": system}]
    for item in (history or [])[-8:]:
        role = item.get("role")
        content = item.get("content") or item.get("message")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": str(content)[:4000]})
    messages.append({"role": "user", "content": user})
    payload = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode("utf-8")
    req = urllib.request.Request(f"{base}/chat/completions", data=payload, headers={"Content-Type":"application/json", "Authorization":f"Bearer {key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            data = json.loads(response.read().decode("utf-8"))
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
    except Exception:
        return None
