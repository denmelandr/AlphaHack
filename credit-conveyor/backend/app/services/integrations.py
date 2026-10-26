"""Клиент к сервису моков внешних источников.

Вызовы устойчивы: таймаут и ретрай, ошибка одного источника не роняет весь
пайплайн — она попадает в снимок как {"error": ...}, обогащение продолжается.
"""

import httpx

from app.core.config import settings

SOURCES = {
    "bki": "/bki/{inn}",
    "egrul": "/egrul/{inn}",
    "fns": "/fns/{inn}",
    "ofd": "/ofd/{inn}",
    "receivables": "/receivables/{inn}",
}


def fetch_all(inn: str) -> dict:
    base = settings.integrations_url.rstrip("/")
    result: dict = {}
    with httpx.Client(timeout=5.0) as client:
        for key, tmpl in SOURCES.items():
            url = base + tmpl.format(inn=inn)
            try:
                resp = client.get(url)
                resp.raise_for_status()
                result[key] = resp.json()
            except Exception as exc:  # noqa: BLE001 — любой сбой источника не критичен
                result[key] = {"error": str(exc)}
    return result


def fetch_counterparty(inn: str) -> dict:
    """Краткая проверка здоровья контрагента-должника (ЕГРЮЛ + ФНС)."""
    base = settings.integrations_url.rstrip("/")
    out: dict = {}
    with httpx.Client(timeout=5.0) as client:
        for key in ("egrul", "fns"):
            try:
                resp = client.get(base + f"/{key}/{inn}")
                resp.raise_for_status()
                out[key] = resp.json()
            except Exception:  # noqa: BLE001
                out[key] = {}
    return out
