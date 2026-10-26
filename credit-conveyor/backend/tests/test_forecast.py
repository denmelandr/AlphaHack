import types
from datetime import date, timedelta

from app.services import forecast


def _account(payment=98000, rate=22, term=18, balance=1_500_000):
    return types.SimpleNamespace(
        rate=rate, term_months=term, outstanding_balance=balance,
        monthly_payment=payment, next_payment_date=date.today() + timedelta(days=10),
    )


HEALTHY = {
    "monthly_revenue": [3_300_000, 3_500_000, 3_700_000, 3_600_000, 3_500_000, 3_600_000],
    "avg_monthly_revenue": 3_500_000, "employees": 15,
}


def test_healthy_business_has_no_gap():
    f = forecast.build_forecast(HEALTHY, _account())
    assert f["gap"] is None
    assert f["min_balance"] > 0


def test_severe_revenue_drop_creates_gap():
    f = forecast.build_forecast(HEALTHY, _account(), drop_pct=80)
    assert f["gap"] is not None
    assert f["gap"]["amount"] > 0


def test_radar_recommends_closing_action_under_stress():
    r = forecast.radar(HEALTHY, _account(), drop_pct=80)
    assert r["gap"] is not None
    assert r["recommended"] is not None
    # рекомендованное действие должно закрывать разрыв
    rec = next(o for o in r["options"] if o["code"] == r["recommended"])
    assert rec["closes_gap"] is True


def test_bridge_closes_gap_and_is_preapproved_for_small_gap():
    r = forecast.radar(HEALTHY, _account(), drop_pct=80)
    bridge = next(o for o in r["options"] if o["code"] == "bridge")
    assert bridge["closes_gap"] is True
    assert r["bridge"]["amount"] > 0
