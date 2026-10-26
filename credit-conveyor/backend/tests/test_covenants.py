import types

from app.services import covenants

POLICY = {"covenants": [
    {"code": "no_cashgap", "metric": "forecast_gap", "op": "equals",
     "value": False, "severity": "high", "reason": "разрыв"},
    {"code": "resilience", "metric": "resilience_pct", "op": "gte",
     "value": 25, "severity": "medium", "reason": "низкий запас прочности"},
    {"code": "payment_load", "metric": "payment_to_revenue", "op": "lte",
     "value": 0.5, "severity": "medium", "reason": "высокая нагрузка платежа"},
]}


def _acc(payment=50000):
    return types.SimpleNamespace(monthly_payment=payment)


def test_breach_on_gap_and_low_resilience():
    b = covenants.evaluate(
        POLICY, {"avg_monthly_revenue": 500000, "monthly_revenue": []},
        _acc(), {"gap": {"amount": 100000}}, resilience_pct=0)
    codes = {x["code"] for x in b}
    assert "no_cashgap" in codes
    assert "resilience" in codes
    assert covenants.worst_severity(b) == "high"


def test_no_breach_when_healthy():
    b = covenants.evaluate(
        POLICY, {"avg_monthly_revenue": 5_000_000, "monthly_revenue": []},
        _acc(), {"gap": None}, resilience_pct=60)
    assert b == []
    assert covenants.worst_severity(b) == "ok"


def test_payment_load_breach():
    b = covenants.evaluate(
        POLICY, {"avg_monthly_revenue": 80000, "monthly_revenue": []},
        _acc(payment=60000), {"gap": None}, resilience_pct=60)
    assert any(x["code"] == "payment_load" for x in b)
