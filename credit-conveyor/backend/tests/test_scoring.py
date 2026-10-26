from app.services import scoring

GOOD = {
    "credit_score": 800, "debt_load_percent": 15, "overdue_count": 0,
    "max_overdue_days": 0, "registered_years_ago": 10, "company_status": "active",
    "account_blocked": False, "disqualified_persons": False, "mass_address": False,
    "tax_arrears": 0, "inquiries_last_90d": 1,
    "requested_amount": 1_000_000, "term_months": 24, "avg_monthly_revenue": 3_000_000,
}
BAD = {
    "credit_score": 410, "debt_load_percent": 70, "overdue_count": 3,
    "max_overdue_days": 80, "registered_years_ago": 1, "company_status": "active",
    "account_blocked": False, "disqualified_persons": False, "mass_address": False,
    "tax_arrears": 50_000, "inquiries_last_90d": 7,
    "requested_amount": 5_000_000, "term_months": 6, "avg_monthly_revenue": 400_000,
}


def test_good_profile_scores_higher_than_bad():
    g = scoring.compute_score(GOOD, 22)
    b = scoring.compute_score(BAD, 22)
    assert g["score"] > b["score"]
    assert g["risk_band"] == "low"
    assert b["risk_band"] == "high"


def test_score_bounded_0_100():
    for p in (GOOD, BAD):
        s = scoring.compute_score(p, 22)["score"]
        assert 0 <= s <= 100


def test_factors_have_contributions_and_sorted():
    s = scoring.compute_score(GOOD, 22)
    assert s["factors"]
    contribs = [abs(f["contribution"]) for f in s["factors"]]
    assert contribs == sorted(contribs, reverse=True)


def test_collateral_and_guarantor_raise_score():
    # умеренный профиль (балл не упирается в 0), чтобы рычаги были видны
    mid = {
        "credit_score": 600, "debt_load_percent": 35, "overdue_count": 0,
        "max_overdue_days": 0, "registered_years_ago": 5, "company_status": "active",
        "tax_arrears": 0, "inquiries_last_90d": 2,
        "requested_amount": 1_000_000, "term_months": 24, "avg_monthly_revenue": 2_000_000,
    }
    base = scoring.compute_score(mid, 22)["score"]
    with_sec = dict(mid, collateral_offered=True, guarantor_offered=True)
    assert scoring.compute_score(with_sec, 22)["score"] > base
