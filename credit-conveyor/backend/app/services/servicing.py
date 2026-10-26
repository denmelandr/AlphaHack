"""Сопровождение кредита после выдачи.

Создаёт кредитный счёт при выдаче, мониторит денежный поток и формирует ранние
сигналы, предлагает меню превентивных действий с расчётом последствий и применяет
их в один клик. Закрывает этап, который большинство решений игнорируют.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.account import CreditAccount
from app.services import finance, forecast


def create_account(db: Session, app) -> CreditAccount:
    """Создаёт счёт из принятого (или последнего) оффера при выдаче."""
    if app.latest_account:
        return app.latest_account
    offer = next((o for o in reversed(app.offers) if o.accepted), app.latest_offer)
    if offer is None:
        return None
    acc = CreditAccount(
        application_id=app.id,
        principal=offer.amount,
        rate=offer.rate,
        term_months=offer.term_months,
        monthly_payment=offer.monthly_payment,
        outstanding_balance=offer.amount,
        next_payment_date=date.today() + timedelta(days=30),
        status="active",
        servicing_log=[],
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def compute_signals(acc: CreditAccount, profile: dict) -> list[dict]:
    """Ранние сигналы по денежному потоку (мониторинг до первой просрочки)."""
    signals: list[dict] = []
    revenue = profile.get("avg_monthly_revenue") or 0
    pay = float(acc.monthly_payment)

    if revenue:
        ratio = pay / revenue
        if ratio > 0.4:
            gap = int(pay - 0.4 * revenue)
            days = (acc.next_payment_date - date.today()).days
            signals.append({
                "code": "cashgap_risk",
                "severity": "high",
                "text": (
                    f"Риск кассового разрыва: через {days} дн. платёж "
                    f"{pay:,.0f} ₽ — это {int(ratio*100)}% средней выручки. "
                    f"Прогнозируемая нехватка ~{gap:,.0f} ₽."
                ).replace(",", " "),
            })
        elif ratio > 0.25:
            signals.append({
                "code": "load_watch",
                "severity": "medium",
                "text": f"Платёж занимает {int(ratio*100)}% выручки — держите подушку на счёте.",
            })

    # тренд выручки по ОФД (последние месяцы вниз)
    mr = profile.get("monthly_revenue") or []
    if len(mr) >= 3 and mr[-1] < mr[0] * 0.85:
        signals.append({
            "code": "revenue_down",
            "severity": "medium",
            "text": "Выручка по ОФД снижается последние месяцы — рассмотрите снижение платежа.",
        })

    if not signals:
        signals.append({
            "code": "ok",
            "severity": "low",
            "text": "Денежный поток в норме, платёж комфортен.",
        })
    return signals


def action_options(acc: CreditAccount, profile: dict) -> list[dict]:
    """Меню превентивных действий с расчётом последствий (до применения)."""
    rate = float(acc.rate)
    pay = float(acc.monthly_payment)
    bal = float(acc.outstanding_balance)
    term = acc.term_months
    revenue = profile.get("avg_monthly_revenue") or 0
    opts: list[dict] = []

    # 1. Реструктуризация: продлить срок на 6 мес → ниже платёж
    new_term = term + 6
    new_pay = finance.annuity_payment(bal, rate, new_term)
    opts.append({
        "code": "restructure_extend",
        "label": "Продлить срок на 6 мес.",
        "description": "Снижает ежемесячный платёж за счёт удлинения срока.",
        "before": {"monthly_payment": round(pay), "term_months": term},
        "after": {"monthly_payment": round(new_pay), "term_months": new_term},
    })

    # 2. Перенос даты платежа на 15 дней
    opts.append({
        "code": "shift_date",
        "label": "Перенести дату платежа на 15 дней",
        "description": "Сдвигает ближайший платёж, чтобы дождаться поступлений.",
        "before": {"next_payment_date": str(acc.next_payment_date)},
        "after": {"next_payment_date": str(acc.next_payment_date + timedelta(days=15))},
    })

    # 3. Погашение процентом с выручки
    rev_pay = round(0.1 * forecast._projected_monthly(profile, 0)) if profile.get("avg_monthly_revenue") is not None else round(pay)
    opts.append({
        "code": "revenue_based",
        "label": "Перейти на погашение % с выручки",
        "description": "Платёж = 10% выручки: нет продаж — меньше платёж.",
        "before": {"monthly_payment": round(pay)},
        "after": {"monthly_payment": rev_pay},
    })

    # 4. Умный остаток: доход с неиспользуемых остатков снижает ставку
    new_rate = max(0.0, rate - 2.0)
    new_pay2 = finance.annuity_payment(bal, new_rate, term)
    opts.append({
        "code": "smart_balance",
        "label": "Включить умный остаток",
        "description": "Доход с неиспользуемых остатков на счёте снижает стоимость кредита.",
        "before": {"rate": rate, "monthly_payment": round(pay)},
        "after": {"rate": round(new_rate, 1), "monthly_payment": round(new_pay2)},
    })

    # 5. Рефинансирование под более низкую ставку
    ref_rate = max(0.0, rate - 3.0)
    ref_pay = finance.annuity_payment(bal, ref_rate, term)
    opts.append({
        "code": "refinance",
        "label": "Рефинансировать",
        "description": "Переоформление остатка под сниженную ставку.",
        "before": {"rate": rate, "monthly_payment": round(pay)},
        "after": {"rate": round(ref_rate, 1), "monthly_payment": round(ref_pay)},
    })
    applied = {entry.get("action") for entry in (getattr(acc, "servicing_log", None) or [])}
    return [o for o in opts if o["code"] not in applied]


def apply_action(db: Session, acc: CreditAccount, code: str, profile: dict) -> CreditAccount:
    if any(entry.get("action") == code for entry in (acc.servicing_log or [])):
        raise ValueError("Это действие уже применено к кредиту")
    rate = float(acc.rate)
    bal = float(acc.outstanding_balance)
    term = acc.term_months
    revenue = profile.get("avg_monthly_revenue") or 0

    if code == "restructure_extend":
        acc.term_months = term + 6
        acc.monthly_payment = round(finance.annuity_payment(bal, rate, acc.term_months), 2)
    elif code == "shift_date":
        acc.next_payment_date = acc.next_payment_date + timedelta(days=15)
    elif code == "revenue_based":
        acc.monthly_payment = round(0.1 * forecast._projected_monthly(profile, 0)) if profile.get("avg_monthly_revenue") is not None else acc.monthly_payment
    elif code == "smart_balance":
        acc.rate = round(max(0.0, rate - 2.0), 1)
        acc.monthly_payment = round(finance.annuity_payment(bal, float(acc.rate), term), 2)
    elif code == "refinance":
        acc.rate = round(max(0.0, rate - 3.0), 1)
        acc.monthly_payment = round(finance.annuity_payment(bal, float(acc.rate), term), 2)
    elif code == "bridge":
        # предодобренный мост: сумма разрыва добавляется к остатку, платёж
        # пересчитывается по оставшемуся сроку
        fc = forecast.radar(profile, acc)
        gap = (fc.get("bridge") or {}).get("amount", 0)
        if not (fc.get("bridge") or {}).get("preapproved") or gap <= 0:
            raise ValueError("Мост не предодобрен или не требуется")
        acc.autopilot = {**(acc.autopilot or {}), "liquidity_credit": float((acc.autopilot or {}).get("liquidity_credit", 0)) + gap}
        if gap > 0:
            acc.outstanding_balance = round(bal + gap, 2)
            acc.monthly_payment = round(
                finance.annuity_payment(float(acc.outstanding_balance), rate, term), 2)
    elif code in ("collect_receivables", "factor_receivables"):
        # собранная дебиторка — это собственные деньги клиента: кредит не меняется,
        # фиксируем факт применения превентивной меры
        fc = forecast.radar(profile, acc)
        collectable = fc["receivables"]["collectable_overdue"]
        gap_amount = (fc.get("gap") or {}).get("amount", 0)
        amount = min(collectable, gap_amount / .97 if code == "factor_receivables" else gap_amount)
        fee = round(amount * .03) if code == "factor_receivables" else 0
        if amount <= 0:
            raise ValueError("Нет собираемой дебиторки для покрытия разрыва")
        cfg = dict(acc.autopilot or {})
        cfg["collected_receivables"] = float(cfg.get("collected_receivables", 0)) + amount
        cfg["liquidity_credit"] = float(cfg.get("liquidity_credit", 0)) + amount - fee
        acc.autopilot = cfg
    else:
        raise ValueError("Неизвестное действие сопровождения")

    log = list(acc.servicing_log or [])
    log.append({"action": code, "at": date.today().isoformat()})
    acc.servicing_log = log
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


FREE_OR_SOFT = {"collect_receivables", "shift_date", "revenue_based"}


def run_autopilot(db: Session, acc, profile: dict) -> dict:
    cfg = dict(acc.autopilot or {})
    rad = forecast.radar(profile, acc)
    result = {"applied": None, "reason": "автопилот выключен"}
    if cfg.get("enabled"):
        if not rad.get("gap"):
            result = {"applied": None, "reason": "разрыв не прогнозируется"}
        else:
            free = next((o for o in rad.get("options", []) if o["code"] in FREE_OR_SOFT and o["cost"] == 0 and o["closes_gap"]), None)
            bridge = next((o for o in rad.get("options", []) if o["code"] == "bridge" and o["closes_gap"]), None)
            bridge_info = rad.get("bridge") or {}
            code = free["code"] if free else "bridge" if bridge and bridge_info.get("preapproved") and bridge_info.get("amount", 0) <= float(cfg.get("max_bridge") or 0) else None
            if code:
                apply_action(db, acc, code, profile)
                cfg = dict(acc.autopilot or {})
                cfg["log"] = [*cfg.get("log", []), {"action": code, "at": date.today().isoformat()}]
                result = {"applied": code, "reason": f"автопилот применил: {code}"}
            else:
                result = {"applied": None, "needs_attention": True, "reason": "Бесплатные действия не закрывают разрыв; мост не предодобрен или превышает лимит. Требуется решение клиента"}
    acc.autopilot = {**cfg, "last_result": result}
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return result
