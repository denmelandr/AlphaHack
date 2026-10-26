"""Симуляторы внешних источников (БКИ, ЕГРЮЛ/ЕГРИП, ФНС «Прозрачный бизнес», ОФД).

Контракты упрощены, но сохраняют смысл интеграции. Данные синтетические и
детерминированно выводятся из ИНН, чтобы демо было воспроизводимым.
Соответствует ограничению кейса «автономность»: никаких реальных систем.
"""

import hashlib

from fastapi import FastAPI

app = FastAPI(title="Моки внешних источников", version="0.1.0")


def _seed(inn: str) -> int:
    return int(hashlib.sha256(inn.encode()).hexdigest(), 16)


# Зарезервированный ИНН «хрупкого» бизнеса для демо: на выдаче проходит, но
# выручка снижается — радар сопровождения показывает ухудшение.
FRAGILE_INN = "7700000001"
# Проблемный контрагент-должник: ликвидируется, счёт заблокирован — его долг
# вряд ли будет собран (демонстрация цепочной заразы по дебиторке).
RISKY_DEBTOR_INN = "7700000002"
FRAGILE = {
    "bki": {"credit_score": 690, "active_loans": 1, "overdue_count": 0,
            "max_overdue_days": 0, "debt_load_percent": 30, "inquiries_last_90d": 2},
    "egrul": {"status": "active", "registered_years_ago": 4, "okved_main": "56.10",
              "disqualified_persons": False, "mass_address": False},
    "fns": {"tax_regime": "УСН", "employees": 5, "account_blocked": False,
            "tax_arrears": 0, "paid_taxes_last_year": 600000},
    "ofd": {"monthly_revenue": [1000000, 900000, 800000, 720000, 640000, 560000],
            "avg_monthly_revenue": 770000, "receipts_last_month": 900},
    "receivables": {
        "invoices": [
            {"id": "INV-204", "inn": RISKY_DEBTOR_INN, "counterparty": "ООО «Поставка-Сервис»", "amount": 280000, "days_overdue": 23},
            {"id": "INV-211", "inn": "7701000006", "counterparty": "ИП Сидоров", "amount": 160000, "days_overdue": 12},
            {"id": "INV-219", "inn": "7701000011", "counterparty": "ООО «ТоргДом»", "amount": 90000, "days_overdue": 0},
        ],
        "total": 530000, "overdue_total": 440000,
    },
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/bki/{inn}", tags=["БКИ"])
def bki(inn: str) -> dict:
    if inn == FRAGILE_INN:
        return {"inn": inn, **FRAGILE["bki"]}
    s = _seed(inn)
    score = 400 + s % 450          # кредитный рейтинг 400..849
    overdue = s % 4                # число текущих просрочек
    debt_load = 10 + s % 70        # долговая нагрузка, %
    return {
        "inn": inn,
        "credit_score": score,
        "active_loans": s % 5,
        "overdue_count": overdue,
        "max_overdue_days": 0 if overdue == 0 else 5 + s % 85,
        "debt_load_percent": debt_load,
        "inquiries_last_90d": s % 8,
    }


@app.get("/egrul/{inn}", tags=["ЕГРЮЛ/ЕГРИП"])
def egrul(inn: str) -> dict:
    if inn == FRAGILE_INN:
        return {"inn": inn, **FRAGILE["egrul"]}
    if inn == RISKY_DEBTOR_INN:
        return {"inn": inn, "status": "liquidating", "registered_years_ago": 6,
                "okved_main": "46.90", "disqualified_persons": False, "mass_address": True}
    s = _seed(inn)
    years = 1 + s % 15
    return {
        "inn": inn,
        "status": "active" if s % 10 != 0 else "liquidating",
        "registered_years_ago": years,
        "okved_main": "47.11",
        "disqualified_persons": s % 20 == 0,
        "mass_address": s % 13 == 0,
    }


@app.get("/fns/{inn}", tags=["ФНС Прозрачный бизнес"])
def fns(inn: str) -> dict:
    if inn == FRAGILE_INN:
        return {"inn": inn, **FRAGILE["fns"]}
    if inn == RISKY_DEBTOR_INN:
        return {"inn": inn, "tax_regime": "ОСНО", "employees": 8,
                "account_blocked": True, "tax_arrears": 450000,
                "paid_taxes_last_year": 100000}
    s = _seed(inn)
    return {
        "inn": inn,
        "tax_regime": ["УСН", "ОСНО", "ПСН"][s % 3],
        "employees": 1 + s % 50,
        "account_blocked": s % 17 == 0,
        "tax_arrears": (s % 9) * 10000,
        "paid_taxes_last_year": 200000 + s % 3_000_000,
    }


@app.get("/receivables/{inn}", tags=["Дебиторка"])
def receivables(inn: str) -> dict:
    """Дебиторская задолженность: сколько бизнесу должны его контрагенты."""
    if inn == FRAGILE_INN:
        return {"inn": inn, **FRAGILE["receivables"]}
    s = _seed(inn)
    n = 1 + s % 3
    invoices = []
    total = 0
    overdue_total = 0
    for i in range(n):
        amount = 50_000 + (s >> (i * 3)) % 400_000
        overdue = (s >> i) % 40  # дней просрочки, 0 — в срок
        invoices.append({
            "id": f"INV-{100 + (s >> i) % 900}",
            "inn": f"77{(s >> (i * 5)) % 100000000:08d}",
            "counterparty": f"Контрагент {i + 1}",
            "amount": amount,
            "days_overdue": overdue,
        })
        total += amount
        if overdue > 0:
            overdue_total += amount
    return {"inn": inn, "invoices": invoices, "total": total,
            "overdue_total": overdue_total}


@app.get("/ofd/{inn}", tags=["ОФД"])
def ofd(inn: str) -> dict:
    if inn == FRAGILE_INN:
        return {"inn": inn, **FRAGILE["ofd"]}
    s = _seed(inn)
    base = 800_000 + s % 4_000_000
    # помесячная выручка по чекам ККТ за 6 месяцев
    revenue = [int(base * (0.8 + ((s >> i) % 40) / 100)) for i in range(6)]
    return {
        "inn": inn,
        "monthly_revenue": revenue,
        "avg_monthly_revenue": sum(revenue) // len(revenue),
        "receipts_last_month": 300 + s % 5000,
    }
