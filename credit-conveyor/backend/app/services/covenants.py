"""Ковенанты сопровождения: условия по выданному кредиту, заданные в policy-as-code.
Нарушение поднимает раннее предупреждение в портфельной очереди банка."""

from app.services import forecast


def _check(op: str, actual, value) -> bool:
    if actual is None:
        return False
    if op == "equals":
        return actual == value
    if op == "not_equals":
        return actual != value
    if op == "gte":
        return actual >= value
    if op == "lte":
        return actual <= value
    if op == "gt":
        return actual > value
    if op == "lt":
        return actual < value
    return False


def metrics_for(profile: dict, account, radar: dict, resilience_pct: int) -> dict:
    rev = profile.get("avg_monthly_revenue") or 0
    pay = float(account.monthly_payment)
    mr = profile.get("monthly_revenue") or []
    declining = len(mr) >= 3 and mr[-1] < mr[0] * 0.9
    return {
        "avg_monthly_revenue": rev,
        "account_blocked": bool(profile.get("account_blocked")),
        "payment_to_revenue": round(pay / rev, 3) if rev else 1.0,
        "forecast_gap": radar.get("gap") is not None,
        "revenue_declining": declining,
        "overdue_count": profile.get("overdue_count") or 0,
        "resilience_pct": resilience_pct,
    }


SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


def evaluate(policy: dict, profile: dict, account, radar: dict,
             resilience_pct: int) -> list[dict]:
    m = metrics_for(profile, account, radar, resilience_pct)
    breaches: list[dict] = []
    for rule in policy.get("covenants", []):
        actual = m.get(rule["metric"])
        if not _check(rule["op"], actual, rule["value"]):
            breaches.append({
                "code": rule["code"],
                "reason": rule["reason"],
                "severity": rule.get("severity", "medium"),
            })
    return breaches


def worst_severity(breaches: list[dict]) -> str:
    if not breaches:
        return "ok"
    return max(breaches, key=lambda b: SEVERITY_RANK.get(b["severity"], 0))["severity"]
