"""Радар кассовых разрывов: дневной прогноз ликвидности и оптимизатор действий.

Модель денежного потока на горизонт N дней строится из данных ОФД (выручка),
календаря обязательных оттоков (зарплата, налоги) и графика по кредиту. Даёт
дату и сумму прогнозируемого кассового разрыва, а оптимизатор перебирает
превентивные действия и показывает, какое закрывает разрыв и во сколько обходится.

Все параметры — синтетические допущения для демонстрации, значения детерминированы
из профиля заявителя (ОФД, число сотрудников) и условий кредита.
"""

from datetime import date, timedelta

from app.services import finance

HORIZON = 60
OPEX_RATIO = 0.55          # операционные расходы как доля выручки
SALARY_PER_EMPLOYEE = 55_000
TAX_RATE = 0.06            # упрощённая налоговая нагрузка от выручки
START_BUFFER_RATIO = 0.35  # стартовый остаток как доля месячной выручки


def _projected_monthly(profile: dict, drop_pct: float) -> float:
    """Проекция выручки на следующий месяц по тренду ОФД плюс заданный стресс."""
    mr = profile.get("monthly_revenue") or []
    if len(mr) >= 3:
        slope = (mr[-1] - mr[0]) / (len(mr) - 1)   # средний помесячный прирост
        base = max(0.0, mr[-1] + slope)            # экстраполяция тренда вперёд
    elif mr:
        base = mr[-1]
    else:
        base = profile.get("avg_monthly_revenue") or 0
    return max(0.0, base * (1 - drop_pct / 100))


INJECT_ACTIONS = {"bridge", "collect_receivables", "factor_receivables"}


def build_forecast(profile: dict, account, drop_pct: float = 0.0,
                   extra_expense: float = 0.0, extra_day: int = 14,
                   action: str | None = None, inject_amount: float = 0.0) -> dict:
    today = date.today()
    monthly = _projected_monthly(profile, drop_pct)
    daily_in = monthly / 30
    opex_daily = monthly * OPEX_RATIO / 30
    employees = profile.get("employees") or 1
    salary_half = employees * SALARY_PER_EMPLOYEE / 2
    tax = monthly * TAX_RATE

    rate = float(account.rate)
    term = account.term_months
    bal_principal = float(account.outstanding_balance)
    pay = float(account.monthly_payment)
    pay_date = account.next_payment_date

    # применяем кандидатное действие к параметрам платежа
    if action == "shift_date":
        pay_date = pay_date + timedelta(days=15)
    elif action == "restructure_extend":
        pay = finance.annuity_payment(bal_principal, rate, term + 6)
    elif action == "smart_balance":
        pay = finance.annuity_payment(bal_principal, max(0.0, rate - 2), term)
    elif action == "refinance":
        pay = finance.annuity_payment(bal_principal, max(0.0, rate - 3), term)
    elif action == "revenue_based":
        pay = 0.1 * monthly

    if action == "bridge":
        pay = finance.annuity_payment(bal_principal + inject_amount, rate, term)

    # мост или собранная дебиторка дают ликвидность сразу
    balance = START_BUFFER_RATIO * monthly
    if action in INJECT_ACTIONS:
        balance += inject_amount
    balance += float((getattr(account, "autopilot", None) or {}).get("liquidity_credit", 0))
    start_balance = balance
    curve = []
    min_bal = balance
    first_neg = None

    for d in range(0, HORIZON + 1):
        day = today + timedelta(days=d)
        balance += daily_in - opex_daily
        if day.day in (5, 20):
            balance -= salary_half
        if day.day == 28:
            balance -= tax
        if day == pay_date or day == pay_date + timedelta(days=30):
            balance -= pay
        if extra_expense and d == extra_day:
            balance -= extra_expense
        if balance < min_bal:
            min_bal = balance
        if balance < -1 and first_neg is None:
            first_neg = day
        if d % 2 == 0 or balance < -1:
            curve.append({"day": d, "date": day.isoformat(), "balance": round(balance)})

    gap = None
    if first_neg is not None:
        gap = {"date": first_neg.isoformat(), "amount": round(-min_bal)}

    return {
        "curve": curve,
        "gap": gap,
        "min_balance": round(min_bal),
        "start_balance": round(start_balance),
        "projected_monthly_revenue": round(monthly),
        "horizon_days": HORIZON,
    }


def resilience(profile: dict, account) -> int:
    """Запас прочности: минимальное падение выручки (%), при котором появляется
    кассовый разрыв. 80 означает «выдерживает падение до 80% и более»."""
    for drop in range(0, 85, 5):
        if build_forecast(profile, account, drop_pct=drop)["gap"] is not None:
            return drop
    return 80


def _interest_total(pay: float, term: int, principal: float) -> float:
    return pay * term - principal


def _action_cost(code: str, account, gap_amount: float) -> float:
    """Стоимость решения для клиента в ₽ (плюс — переплата, минус — экономия)."""
    rate = float(account.rate)
    term = account.term_months
    principal = float(account.outstanding_balance)
    pay = float(account.monthly_payment)
    old = _interest_total(pay, term, principal)
    if code == "shift_date":
        return 0.0
    if code == "restructure_extend":
        new_pay = finance.annuity_payment(principal, rate, term + 6)
        return round(_interest_total(new_pay, term + 6, principal) - old)
    if code == "smart_balance":
        new_pay = finance.annuity_payment(principal, max(0.0, rate - 2), term)
        return round(_interest_total(new_pay, term, principal) - old)
    if code == "refinance":
        new_pay = finance.annuity_payment(principal, max(0.0, rate - 3), term)
        return round(_interest_total(new_pay, term, principal) - old)
    if code == "revenue_based":
        return 0.0
    if code == "bridge":
        new_pay = finance.annuity_payment(principal + gap_amount, rate, term)
        return round((new_pay - pay) * term - gap_amount)
    return 0.0


ACTION_LABELS = {
    "collect_receivables": "Собрать дебиторку (напоминания контрагентам)",
    "factor_receivables": "Ранняя оплата счетов (факторинг)",
    "shift_date": "Перенести дату платежа",
    "restructure_extend": "Реструктуризация (+6 мес.)",
    "revenue_based": "Погашение % с выручки",
    "smart_balance": "Умный остаток",
    "refinance": "Рефинансирование",
    "bridge": "Предодобренный мост",
}


def radar(profile: dict, account, drop_pct: float = 0.0,
          extra_expense: float = 0.0) -> dict:
    """Прогноз + оптимизатор действий по закрытию разрыва (с учётом стресса)."""
    base = build_forecast(profile, account, drop_pct=drop_pct,
                          extra_expense=extra_expense)
    collected = float((getattr(account, "autopilot", None) or {}).get("collected_receivables", 0))
    _overdue = max(0, (profile.get("receivables_overdue_total") or 0) - collected)
    _collectable = profile.get("receivables_overdue_collectable")
    if _collectable is None:
        _collectable = _overdue
    _collectable = max(0, _collectable - collected)
    receivables_block = {
        "total": max(0, (profile.get("receivables_total") or 0) - collected),
        "overdue_total": _overdue,
        "collectable_overdue": _collectable,
        "risky_overdue": max(0, _overdue - _collectable),
        "invoices": profile.get("receivables") or [],
    }
    if base["gap"] is None:
        return {"gap": None, "options": [], "recommended": None, "bridge": None,
                "forecast": base, "receivables": receivables_block}

    gap_amount = base["gap"]["amount"]
    options = []

    # Приоритет — собрать свои деньги (дебиторку), а не брать новый долг.
    # Учитываем только надёжных должников: рисковых исключает радар контрагентов.
    overdue = max(0, (profile.get("receivables_overdue_total") or 0) - collected)
    collectable = profile.get("receivables_overdue_collectable")
    if collectable is None:
        collectable = overdue
    collectable = max(0, collectable - collected)
    if collectable > 0:
        for code in ("collect_receivables", "factor_receivables"):
            gross = min(collectable, gap_amount / .97 if code == "factor_receivables" else gap_amount)
            cost = round(gross * .03) if code == "factor_receivables" else 0
            inject = gross - cost
            f = build_forecast(profile, account, drop_pct=drop_pct,
                               extra_expense=extra_expense, action=code,
                               inject_amount=inject)
            options.append({
                "code": code, "label": ACTION_LABELS[code],
                "closes_gap": f["gap"] is None,
                "new_min_balance": f["min_balance"], "cost": cost,
            })

    bridge_amount = gap_amount
    for _ in range(30):
        candidate_bridge = build_forecast(profile, account, drop_pct=drop_pct, extra_expense=extra_expense, action="bridge", inject_amount=bridge_amount)
        if candidate_bridge["gap"] is None:
            break
        bridge_amount += candidate_bridge["gap"]["amount"] + 2

    for code in ["shift_date", "restructure_extend", "smart_balance",
                 "refinance", "revenue_based", "bridge"]:
        f = build_forecast(profile, account, drop_pct=drop_pct,
                           extra_expense=extra_expense, action=code,
                           inject_amount=bridge_amount if code == "bridge" else 0.0)
        options.append({
            "code": code,
            "label": ACTION_LABELS[code],
            "closes_gap": f["gap"] is None,
            "new_min_balance": f["min_balance"],
            "cost": _action_cost(code, account, bridge_amount if code == "bridge" else gap_amount),
        })
    # сначала те, что закрывают разрыв, затем по возрастанию стоимости
    applied = {entry.get("action") for entry in (getattr(account, "servicing_log", None) or [])}
    options = [o for o in options if o["code"] not in applied]
    options.sort(key=lambda o: (not o["closes_gap"], 0 if o["code"] == "collect_receivables" else 1, o["cost"]))
    recommended = next((o["code"] for o in options if o["closes_gap"]),
                       options[0]["code"] if options else None)

    monthly = base["projected_monthly_revenue"]
    bridge = {
        "amount": bridge_amount,
        "preapproved": bridge_amount <= 0.5 * monthly if monthly else False,
    }
    pay = float(account.monthly_payment)
    inaction = {
        "date": base["gap"]["date"],
        "missed_payment": round(pay),
        "penalty": round(pay * 0.001 * 30),  # пени ~0.1%/день за ~30 дней
        "note": "просрочка снизит кредитный рейтинг и ограничит доступ к новым кредитам",
    }
    invoices = profile.get("receivables") or []
    return {"gap": base["gap"], "options": options, "recommended": recommended,
            "bridge": bridge, "forecast": base, "inaction": inaction,
            "receivables": {
                "total": max(0, (profile.get("receivables_total") or 0) - collected),
                "overdue_total": overdue,
                "collectable_overdue": collectable,
                "risky_overdue": max(0, overdue - collectable),
                "invoices": invoices,
            }}
