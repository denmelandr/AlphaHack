"""Радар контрагентов: оценка надёжности должников по дебиторке.

Дебиторка — это деньги, которые бизнесу должны его покупатели за уже
поставленное. Если крупный должник сам в беде (ликвидация, блокировка счёта),
эти деньги вряд ли придут вовремя, и рассчитывать на них в прогнозе нельзя.
"""

from app.services import integrations


def assess(invoices: list[dict]) -> list[dict]:
    """Размечает счета риском должника и причиной."""
    result = []
    for inv in invoices or []:
        inn = inv.get("inn")
        risky = False
        reason = ""
        if inn:
            cp = integrations.fetch_counterparty(inn)
            status = (cp.get("egrul") or {}).get("status")
            blocked = (cp.get("fns") or {}).get("account_blocked")
            if status and status != "active":
                risky = True
                reason = "должник ликвидируется"
            elif blocked:
                risky = True
                reason = "у должника заблокирован счёт"
        result.append({**inv, "risky": risky, "risk_reason": reason})
    return result


def collectable_overdue(assessed: list[dict]) -> int:
    """Просроченная дебиторка, которую реально собрать (без рисковых должников)."""
    return sum(
        inv["amount"] for inv in assessed
        if inv.get("days_overdue", 0) > 0 and not inv.get("risky")
    )
