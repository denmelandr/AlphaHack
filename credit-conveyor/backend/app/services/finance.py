"""Финансовые расчёты: аннуитетный платёж, график, подбор суммы под платёж."""


def annuity_payment(amount: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 100 / 12
    if months <= 0:
        return amount
    if r == 0:
        return amount / months
    return amount * r / (1 - (1 + r) ** (-months))


def amount_for_payment(payment: float, annual_rate: float, months: int) -> float:
    """Обратная задача: какая сумма даёт заданный аннуитетный платёж."""
    r = annual_rate / 100 / 12
    if months <= 0:
        return 0.0
    if r == 0:
        return payment * months
    return payment * (1 - (1 + r) ** (-months)) / r


def build_schedule(amount: float, annual_rate: float, months: int) -> list[dict]:
    """График аннуитетных платежей (помесячно)."""
    r = annual_rate / 100 / 12
    pay = annuity_payment(amount, annual_rate, months)
    balance = amount
    schedule: list[dict] = []
    for m in range(1, months + 1):
        interest = balance * r
        principal = pay - interest
        balance = max(0.0, balance - principal)
        schedule.append(
            {
                "month": m,
                "payment": round(pay, 2),
                "principal": round(principal, 2),
                "interest": round(interest, 2),
                "balance": round(balance, 2),
            }
        )
    return schedule
