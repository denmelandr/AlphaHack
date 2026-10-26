from app.services import finance


def test_annuity_payment_positive_rate():
    pay = finance.annuity_payment(1_000_000, 22, 12)
    assert 90_000 < pay < 96_000


def test_annuity_zero_rate_is_linear():
    assert finance.annuity_payment(1_200_000, 0, 12) == 100_000


def test_amount_for_payment_is_inverse():
    amount = 1_000_000
    pay = finance.annuity_payment(amount, 20, 24)
    back = finance.amount_for_payment(pay, 20, 24)
    assert abs(back - amount) < 1.0


def test_schedule_amortizes_to_zero():
    sched = finance.build_schedule(500_000, 18, 10)
    assert len(sched) == 10
    assert sched[-1]["balance"] == 0.0
    # остаток убывает монотонно
    balances = [row["balance"] for row in sched]
    assert balances == sorted(balances, reverse=True)
