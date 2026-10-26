"""Прозрачный скоринг (scorecard).

Балльная модель: базовый балл 50, каждый значимый фактор профиля даёт вклад
(в плюс или минус). Итог — балл кредитоспособности 0..100, уровень риска и
оценка вероятности дефолта (PD). Модель объяснимая: возвращается разбор по
факторам с весами и reason-кодами, как описано в кейсе (стр. 14).

Это не чёрный ящик и не сложная ML-модель — ровно тот подход, который кейс
допускает: «каждому значимому признаку соответствует определённое влияние».
"""

import math

BASE_SCORE = 50


def annuity_payment(amount: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 100 / 12
    if months <= 0:
        return amount
    if r == 0:
        return amount / months
    return amount * r / (1 - (1 + r) ** (-months))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_score(profile: dict, base_rate: float) -> dict:
    factors: list[dict] = []

    def add(code: str, label: str, value, contribution: float):
        if contribution:
            factors.append(
                {
                    "code": code,
                    "label": label,
                    "value": value,
                    "contribution": round(contribution),
                }
            )

    # 1. Кредитный рейтинг БКИ
    cs = profile.get("credit_score")
    if cs is not None:
        add("credit_score", "Кредитный рейтинг БКИ", cs,
            _clamp((cs - 600) / 12, -20, 25))

    # 2. Долговая нагрузка
    dl = profile.get("debt_load_percent")
    if dl is not None:
        add("debt_load", "Долговая нагрузка", f"{dl}%",
            _clamp((30 - dl) * 0.5, -22, 8))

    # 3. Просрочки
    oc = profile.get("overdue_count")
    mo = profile.get("max_overdue_days") or 0
    if oc is not None:
        if oc == 0:
            add("overdue", "Просрочек нет", 0, 10)
        else:
            add("overdue", "Просрочки по обязательствам",
                f"{oc} шт., до {mo} дн.", _clamp(-(oc * 6 + (mo // 30) * 4), -30, 0))

    # 4. Возраст бизнеса
    yrs = profile.get("registered_years_ago")
    if yrs is not None:
        add("company_age", "Возраст бизнеса", f"{yrs} лет", min(yrs, 10) * 1.5)

    # 5. Статус компании (ЕГРЮЛ)
    status = profile.get("company_status")
    if status is not None:
        add("company_status", "Статус в ЕГРЮЛ", status,
            3 if status == "active" else -25)

    # 6. Блокировка счёта (ФНС)
    if profile.get("account_blocked"):
        add("account_blocked", "Счёт заблокирован (ФНС)", "да", -25)

    # 7. Дисквалификация и массовый адрес
    if profile.get("disqualified_persons"):
        add("disqualified", "Дисквалифицированные лица", "да", -30)
    if profile.get("mass_address"):
        add("mass_address", "Массовый адрес регистрации", "да", -8)

    # 8. Налоговая задолженность
    ta = profile.get("tax_arrears")
    if ta:
        add("tax_arrears", "Налоговая задолженность",
            f"{ta:.0f} ₽", _clamp(-ta / 20000, -10, 0))

    # 9. Запросы в БКИ за 90 дней
    iq = profile.get("inquiries_last_90d")
    if iq is not None and iq > 5:
        add("inquiries", "Много запросов в БКИ", f"{iq} за 90 дн.",
            _clamp(-(iq - 5) * 2, -10, 0))

    # 10а. Обеспечение: залог и поручитель (рычаги конструктора условий)
    if profile.get("collateral_offered"):
        add("collateral", "Предоставлен залог", "да", 12)
    if profile.get("guarantor_offered"):
        add("guarantor", "Есть поручитель", "да", 8)

    # 10. Доступность платежа: аннуитет к средней выручке
    amount = profile.get("requested_amount")
    term = profile.get("term_months")
    rev = profile.get("avg_monthly_revenue")
    if amount and term and rev:
        pay = annuity_payment(amount, base_rate, term)
        ratio = pay / rev
        if ratio <= 0.1:
            contrib = 10
        elif ratio <= 0.2:
            contrib = 3
        elif ratio <= 0.35:
            contrib = -6
        else:
            contrib = -18
        add("affordability", "Платёж к выручке",
            f"{ratio * 100:.0f}% ({pay:.0f} ₽/мес)", contrib)

    raw = BASE_SCORE + sum(f["contribution"] for f in factors)
    score = int(_clamp(raw, 0, 100))

    if score >= 70:
        band = "low"
    elif score >= 45:
        band = "medium"
    else:
        band = "high"

    pd = round(1 / (1 + math.exp((score - 50) / 12)), 3)

    factors.sort(key=lambda f: abs(f["contribution"]), reverse=True)
    return {
        "score": score,
        "risk_band": band,
        "pd_estimate": pd,
        "factors": factors,
    }
