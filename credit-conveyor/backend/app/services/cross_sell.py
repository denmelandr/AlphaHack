"""Подбор продуктов банка под профиль бизнеса из заявки и расчёт скидки,
заработанной поведением (уровнем финансового здоровья).

Награда — не снижение ставки по кредиту, а скидки на нужные бизнесу продукты.
Это защищает процентную маржу и превращает сопровождение в канал кросс-продаж.
"""

CATALOG = [
    {"code": "acquiring", "name": "Торговый эквайринг", "category": "Приём платежей",
     "benefit": "сниженная ставка эквайринга"},
    {"code": "payroll", "name": "Зарплатный проект", "category": "ФОТ",
     "benefit": "бесплатные переводы сотрудникам и обслуживание"},
    {"code": "cash_mgmt", "name": "Управление ликвидностью", "category": "Счета",
     "benefit": "накопительный счёт и автопополнение под обязательства"},
    {"code": "accounting", "name": "Онлайн-бухгалтерия", "category": "Учёт",
     "benefit": "бухгалтерия и отчётность (1С/Эльба)"},
    {"code": "ved", "name": "ВЭД и валютный контроль", "category": "Внешнеэкономическая деятельность",
     "benefit": "сопровождение контрактов и сниженная комиссия"},
    {"code": "insurance", "name": "Страхование бизнеса", "category": "Защита",
     "benefit": "страхование имущества и ответственности"},
    {"code": "leasing", "name": "Лизинг оборудования", "category": "Основные средства",
     "benefit": "оборудование в лизинг на выгодных условиях"},
    {"code": "marketing", "name": "Продвижение и реклама", "category": "Маркетинг",
     "benefit": "рекламный кабинет с кэшбэком"},
]

TIERS = {
    "gold": {"label": "Золотой", "discount": 20},
    "silver": {"label": "Серебряный", "discount": 12},
    "bronze": {"label": "Бронзовый", "discount": 5},
}


def _okved_div(okved: str) -> int:
    try:
        return int((okved or "0").split(".")[0])
    except ValueError:
        return 0


def match(company, profile: dict, product_kind: str) -> list[dict]:
    div = _okved_div(company.okved if company else "")
    revenue = profile.get("avg_monthly_revenue") or 0
    employees = profile.get("employees") or (company.employees if company else 1)
    acquiring = bool(profile.get("receipts_last_month")) or revenue > 1_000_000
    retail = div in (45, 47, 56)             # розница, авто, общепит
    wholesale_import = div == 46              # опт/импорт
    industrial = 10 <= div <= 43              # производство, строительство

    scored: list[tuple[int, dict, str]] = []

    def add(code, rel, reason):
        item = next(c for c in CATALOG if c["code"] == code)
        scored.append((rel, item, reason))

    add("acquiring", 3 if (retail or acquiring) else 1,
        "Высокий оборот по картам" if acquiring else "Приём платежей от клиентов")
    if employees >= 5:
        add("payroll", 3, f"В компании {employees} сотрудников")
    elif employees >= 2:
        add("payroll", 2, "Выплаты сотрудникам")
    add("cash_mgmt", 2, "Свободный остаток может приносить доход")
    if employees < 20:
        add("accounting", 2, "Малому бизнесу удобна онлайн-бухгалтерия")
    if wholesale_import:
        add("ved", 3, "Оптовая торговля — вероятны импортные контракты")
    add("insurance", 2 if industrial else 1,
        "Защита оборудования и помещений" if industrial else "Защита бизнеса")
    if industrial or product_kind == "investment":
        add("leasing", 3, "Нужны основные средства/оборудование")
    add("marketing", 3 if retail else 1,
        "Рост продаж в рознице" if retail else "Привлечение клиентов")

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"reason": reason, **item} for rel, item, reason in scored[:5]]


def tier_for(risk_band: str | None, serviced: bool,
             covenant_breaches: int, preventive_used: bool) -> str:
    base = {"low": "gold", "medium": "silver", "high": "bronze"}.get(risk_band or "", "silver")
    if serviced:
        if covenant_breaches == 0 and preventive_used:
            return "gold"
        if covenant_breaches > 0:
            return "bronze"
    return base


def offers_for(company, profile: dict, product_kind: str, risk_band: str | None,
               serviced: bool, covenant_breaches: int, preventive_used: bool) -> dict:
    tier = tier_for(risk_band, serviced, covenant_breaches, preventive_used)
    discount = TIERS[tier]["discount"]
    items = match(company, profile, product_kind)
    for it in items:
        it["discount_pct"] = discount
    return {
        "tier": tier,
        "tier_label": TIERS[tier]["label"],
        "discount_pct": discount,
        "offers": items,
    }
