import types

from app.services import policy

POLICY = {
    "hard_declines": [
        {"field": "account_blocked", "op": "equals", "value": True,
         "reason": "Счёт заблокирован"},
        {"field": "max_overdue_days", "op": "gte", "value": 90,
         "reason": "Просрочка 90+"},
    ],
    "require_sources": ["bki"],
    "score_bands": {"approve_min": 70, "counter_min": 45},
    "counter_offer": {"amount_factor": 0.6, "rate_add": 4.0, "collateral_above": 3_000_000},
    "affordability": {"max_payment_to_revenue": 0.4},
}

PRODUCT = types.SimpleNamespace(base_rate=22.0)


def _profile(**over):
    base = {"avg_monthly_revenue": 3_000_000, "sources_failed": []}
    base.update(over)
    return base


def test_hard_decline_blocks_regardless_of_score():
    r = policy.decide(POLICY, {"score": 95}, _profile(account_blocked=True),
                      PRODUCT, 1_000_000, 12)
    assert r["outcome"] == "decline"
    assert "заблокирован" in r["reasons"][0].lower()


def test_missing_bki_requests_info():
    r = policy.decide(POLICY, {"score": 80}, _profile(sources_failed=["bki"]),
                      PRODUCT, 1_000_000, 12)
    assert r["outcome"] == "need_info"


def test_high_score_approves():
    r = policy.decide(POLICY, {"score": 85}, _profile(), PRODUCT, 1_000_000, 12)
    assert r["outcome"] == "approve"
    assert r["offer"]["amount"] == 1_000_000


def test_low_score_declines():
    r = policy.decide(POLICY, {"score": 30}, _profile(), PRODUCT, 1_000_000, 12)
    assert r["outcome"] == "decline"


def test_mid_score_counters_with_reduced_amount():
    r = policy.decide(POLICY, {"score": 55}, _profile(), PRODUCT, 1_000_000, 12)
    assert r["outcome"] == "counter"
    assert r["offer"]["amount"] < 1_000_000
    assert r["offer"]["rate"] > PRODUCT.base_rate


def test_collateral_offered_satisfies_requirement():
    # большая сумma требует залог; при collateral_offered флаг снимается
    r = policy.decide(POLICY, {"score": 85}, _profile(), PRODUCT,
                      4_000_000, 24, collateral_offered=True)
    assert r["offer"]["collateral_required"] is False
