"""Движок кредитного решения (policy-as-code).

На вход: активная политика, результат скоринга, профиль заявителя, продукт и
параметры заявки. На выходе — решение (approve / counter / need_info / decline),
причины и, для одобрения и контрпредложения, условия оффера с графиком.

Важно: скоринг и решение разделены (кейс, стр. 14–15). Скоринг даёт балл риска,
политика превращает его вместе с правилами банка в решение и условия.
"""

from app.services import finance


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


def _build_offer(amount: float, term: int, rate: float, is_counter: bool,
                 collateral: bool) -> dict:
    pay = finance.annuity_payment(amount, rate, term)
    total = pay * term
    return {
        "amount": round(amount, 2),
        "term_months": term,
        "rate": round(rate, 2),
        "monthly_payment": round(pay, 2),
        "total_payment": round(total, 2),
        "overpayment": round(total - amount, 2),
        "collateral_required": collateral,
        "is_counter": is_counter,
        "schedule": finance.build_schedule(amount, rate, term),
    }


def _decide(policy: dict, score: dict, profile: dict, product, amount: float,
           term: int, collateral_offered: bool = False,
           guarantor_offered: bool = False) -> dict:
    reasons: list[str] = []
    requested = float(amount)
    term = int(term)
    base_rate = float(product.base_rate)

    # 1. Жёсткие стоп-факторы
    for rule in policy.get("hard_declines", []):
        if _check(rule["op"], profile.get(rule["field"]), rule.get("value")):
            reasons.append(rule["reason"])
    if reasons:
        return {"outcome": "decline", "reasons": reasons,
                "details": {"stage": "hard_declines"}, "offer": None}

    # 2. Критичные источники недоступны → запрос данных
    failed = set(profile.get("sources_failed") or [])
    missing = [s for s in policy.get("require_sources", []) if s in failed]
    if missing:
        return {"outcome": "need_info",
                "reasons": [f"Недоступен источник: {', '.join(missing)}. Нужна повторная проверка."],
                "details": {"stage": "sources"}, "offer": None}

    bands = policy.get("score_bands", {})
    approve_min = bands.get("approve_min", 70)
    counter_min = bands.get("counter_min", 45)
    s = score.get("score", 0)

    aff = policy.get("affordability", {})
    max_ptr = aff.get("max_payment_to_revenue", 0.4)
    revenue = profile.get("avg_monthly_revenue") or 0

    co = policy.get("counter_offer", {})
    collateral_above = co.get("collateral_above", float("inf"))

    # 3. Ниже нижнего порога → отказ
    if s < counter_min:
        return {"outcome": "decline",
                "reasons": [f"Балл кредитоспособности {s} ниже минимального {counter_min}"],
                "details": {"stage": "score", "score": s}, "offer": None}

    # 4. Одобрение на запрошенных условиях
    if s >= approve_min:
        rate = base_rate
        amount = requested
        is_counter = False
        # проверка доступности платежа
        if revenue:
            max_pay = max_ptr * revenue
            pay = finance.annuity_payment(amount, rate, term)
            if pay > max_pay:
                amount = min(amount, finance.amount_for_payment(max_pay, rate, term))
                is_counter = True
                reasons.append(
                    f"Сумма снижена до {amount:.0f} ₽: платёж не должен превышать "
                    f"{int(max_ptr*100)}% выручки"
                )
        needs_collateral = amount > collateral_above
        collateral = needs_collateral and not collateral_offered
        if needs_collateral and collateral_offered:
            reasons.append("Залог предоставлен — требование по обеспечению выполнено")
        elif needs_collateral:
            reasons.append(f"Требуется залог: сумма превышает {collateral_above:.0f} ₽")
        outcome = "counter" if is_counter else "approve"
        if not reasons:
            reasons.append("Заявка соответствует кредитной политике")
        return {"outcome": outcome, "reasons": reasons,
                "details": {"stage": "score", "score": s},
                "offer": _build_offer(amount, term, rate, is_counter, collateral)}

    # 5. Средний балл → контрпредложение
    rate = base_rate + co.get("rate_add", 4.0)
    amount = requested * co.get("amount_factor", 0.6)
    reasons.append(
        f"Балл {s} в зоне контрпредложения: сумма {amount:.0f} ₽ "
        f"(из запрошенных {requested:.0f} ₽), ставка {rate:.1f}%"
    )
    if revenue:
        max_pay = max_ptr * revenue
        pay = finance.annuity_payment(amount, rate, term)
        if pay > max_pay:
            amount = min(amount, finance.amount_for_payment(max_pay, rate, term))
            reasons.append(f"Сумма дополнительно снижена до {amount:.0f} ₽ под доступность платежа")
    needs_collateral = amount > collateral_above
    collateral = needs_collateral and not collateral_offered
    if needs_collateral and collateral_offered:
        reasons.append("Залог предоставлен — требование по обеспечению выполнено")
    elif needs_collateral:
        reasons.append(f"Требуется залог: сумма превышает {collateral_above:.0f} ₽")
    return {"outcome": "counter", "reasons": reasons,
            "details": {"stage": "score", "score": s},
            "offer": _build_offer(amount, term, rate, True, collateral)}


def decide(policy: dict, score: dict, profile: dict, product, amount: float, term: int, collateral_offered: bool = False, guarantor_offered: bool = False) -> dict:
    result = _decide(policy, score, profile, product, amount, term, collateral_offered, guarantor_offered)
    offer = result.get("offer")
    if offer and offer["amount"] < float(getattr(product, "min_amount", 0)):
        return {"outcome": "decline", "reasons": ["Доступная сумма ниже минимума продукта. Нужны другой продукт или пересмотр"], "details": {"stage": "affordability"}, "offer": None}
    return result
