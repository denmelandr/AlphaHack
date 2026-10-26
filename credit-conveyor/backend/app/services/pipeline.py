"""Оркестратор кредитного пайплайна.

Выполняет автоматические шаги процесса (валидация, обогащение) и продвигает
заявку по машине состояний. Решение и скоринг подключаются на следующих фазах;
пока пайплайн доводит заявку до состояния SCORING или до NEEDS_INFO.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationState as S
from app.models.company import Company
from app.models.decision import Decision, Offer
from app.models.document import Document
from app.models.enrichment import EnrichmentSnapshot
from app.models.policy import PolicyVersion
from app.models.product import Product
from app.models.score import ScoreResult
from app.services import (
    counterparty,
    documents as docs_service,
    integrations,
    policy as policy_engine,
    scoring,
    state_machine,
)


def inn_is_valid(inn: str) -> bool:
    """ИНН корректен: 10 или 12 цифр и не из одних нулей."""
    inn = (inn or "").strip()
    if not re.fullmatch(r"\d{10}|\d{12}", inn):
        return False
    return set(inn) != {"0"}


def run_validation(db: Session, app: Application) -> list[str]:
    """Проверка полноты и корректности заявки. Возвращает список проблем."""
    problems: list[str] = []
    product = db.get(Product, app.product_id)
    company = db.get(Company, app.company_id)

    if app.amount is None or app.amount <= 0:
        problems.append("Не указана сумма кредита")
    if app.term_months is None or app.term_months <= 0:
        problems.append("Не указан срок")
    if not (app.purpose or "").strip():
        problems.append("Не указана цель финансирования")

    inn = (company.inn if company else "") or ""
    if company is None or not inn.strip():
        problems.append("Нет данных о компании (ИНН)")
    elif not inn_is_valid(inn):
        problems.append(f"Некорректный ИНН компании: {inn}")

    if product is not None and app.amount:
        if not (float(product.min_amount) <= float(app.amount) <= float(product.max_amount)):
            problems.append(
                f"Сумма вне диапазона продукта "
                f"({product.min_amount:.0f}–{product.max_amount:.0f} ₽)"
            )
    if product is not None and app.term_months:
        if not (product.min_term <= app.term_months <= product.max_term):
            problems.append(
                f"Срок вне диапазона продукта "
                f"({product.min_term}–{product.max_term} мес.)"
            )

    # Проверка комплекта документов
    if product is not None:
        required = {d["type"]: d["name"] for d in docs_service.required_docs(product.kind)}
        uploaded = {d.doc_type for d in app.documents}
        for dtype, dname in required.items():
            if dtype not in uploaded:
                problems.append(f"Не приложен документ: {dname}")
    return problems


def build_profile(app: Application, company: Company, raw: dict) -> dict:
    """Нормализует сырые ответы источников в единый профиль заявителя."""
    bki = raw.get("bki", {})
    egrul = raw.get("egrul", {})
    fns = raw.get("fns", {})
    ofd = raw.get("ofd", {})
    rec = raw.get("receivables", {})

    return {
        # параметры заявки
        "requested_amount": float(app.amount),
        "term_months": app.term_months,
        # БКИ
        "credit_score": bki.get("credit_score"),
        "active_loans": bki.get("active_loans"),
        "overdue_count": bki.get("overdue_count"),
        "max_overdue_days": bki.get("max_overdue_days"),
        "debt_load_percent": bki.get("debt_load_percent"),
        "inquiries_last_90d": bki.get("inquiries_last_90d"),
        # ЕГРЮЛ/ЕГРИП
        "company_status": egrul.get("status"),
        "registered_years_ago": egrul.get("registered_years_ago"),
        "disqualified_persons": egrul.get("disqualified_persons"),
        "mass_address": egrul.get("mass_address"),
        # ФНС
        "tax_regime": fns.get("tax_regime"),
        "employees": fns.get("employees"),
        "account_blocked": fns.get("account_blocked"),
        "tax_arrears": fns.get("tax_arrears"),
        # ОФД
        "avg_monthly_revenue": ofd.get("avg_monthly_revenue"),
        "monthly_revenue": ofd.get("monthly_revenue"),
        "receipts_last_month": ofd.get("receipts_last_month"),
        # Дебиторка: сколько бизнесу должны контрагенты
        "receivables_total": rec.get("total"),
        "receivables_overdue_total": rec.get("overdue_total"),
        "receivables": rec.get("invoices"),
        # служебное
        "sources_ok": [k for k, v in raw.items() if "error" not in v],
        "sources_failed": [k for k, v in raw.items() if "error" in v],
    }


def run_enrichment(db: Session, app: Application) -> EnrichmentSnapshot:
    """Собирает данные из моков источников и сохраняет снимок + профиль."""
    company = db.get(Company, app.company_id)
    raw = integrations.fetch_all(company.inn)
    profile = build_profile(app, company, raw)
    # радар контрагентов: размечаем должников риском и считаем собираемую дебиторку
    assessed = counterparty.assess(profile.get("receivables") or [])
    profile["receivables"] = assessed
    profile["receivables_overdue_collectable"] = counterparty.collectable_overdue(assessed)
    snapshot = EnrichmentSnapshot(application_id=app.id, raw=raw, profile=profile)
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def run_scoring(db: Session, app: Application) -> ScoreResult:
    """Считает балл по профилю последнего обогащения и сохраняет результат."""
    snap = app.latest_enrichment
    profile = snap.profile if snap else {}
    product = db.get(Product, app.product_id)
    base_rate = float(product.base_rate) if product else 22.0
    result = scoring.compute_score(profile, base_rate)
    score = ScoreResult(
        application_id=app.id,
        score=result["score"],
        risk_band=result["risk_band"],
        pd_estimate=result["pd_estimate"],
        factors=result["factors"],
    )
    db.add(score)
    db.commit()
    db.refresh(score)
    return score


def get_active_policy(db: Session) -> PolicyVersion | None:
    return db.scalar(select(PolicyVersion).where(PolicyVersion.active.is_(True)))


def simulate(db: Session, app: Application, amount: float, term: int,
             collateral_offered: bool, guarantor_offered: bool) -> dict:
    """Пересчитывает скоринг и решение под кандидатные условия, НЕ меняя заявку.
    Это движок конструктора условий «Путь к одобрению»."""
    pol = get_active_policy(db)
    snap = app.latest_enrichment
    product = db.get(Product, app.product_id)
    base_rate = float(product.base_rate)

    profile = dict(snap.profile) if snap else {}
    profile["requested_amount"] = amount
    profile["term_months"] = term
    profile["collateral_offered"] = collateral_offered
    profile["guarantor_offered"] = guarantor_offered

    sc = scoring.compute_score(profile, base_rate)
    result = policy_engine.decide(
        pol.body if pol else {}, sc, profile, product,
        amount, term, collateral_offered, guarantor_offered,
    )

    bands = (pol.body.get("score_bands", {}) if pol else {})
    approve_min = bands.get("approve_min", 70)
    counter_min = bands.get("counter_min", 45)
    span = max(1, approve_min - counter_min)
    approval = max(0.0, min(1.0, (sc["score"] - counter_min) / span))

    return {
        "score": sc["score"],
        "risk_band": sc["risk_band"],
        "pd_estimate": sc["pd_estimate"],
        "approval_probability": round(approval * 100),
        "outcome": result["outcome"],
        "reasons": result["reasons"],
        "offer": result.get("offer"),
        "factors": sc["factors"],
    }


OUTCOME_EVENT = {
    "approve": "decide_approve",
    "counter": "decide_counter",
    "need_info": "decide_need_info",
    "decline": "decide_decline",
}


def run_decision(db: Session, app: Application) -> Decision:
    """Прогоняет активную политику и формирует решение (и оффер при одобрении)."""
    pol = get_active_policy(db)
    score = app.latest_score
    snap = app.latest_enrichment
    product = db.get(Product, app.product_id)
    result = policy_engine.decide(
        pol.body if pol else {},
        {"score": score.score, "risk_band": score.risk_band, "pd_estimate": score.pd_estimate}
        if score else {},
        snap.profile if snap else {},
        product,
        float(app.amount),
        int(app.term_months),
    )
    decision = Decision(
        application_id=app.id,
        outcome=result["outcome"],
        policy_version=pol.version if pol else 0,
        reasons=result["reasons"],
        details=result["details"],
    )
    db.add(decision)
    if result.get("offer"):
        o = result["offer"]
        db.add(Offer(application_id=app.id, **o))
    db.commit()
    db.refresh(decision)
    return decision


def advance_auto(db: Session, app: Application, actor_id: int | None = None) -> Application:
    """Проводит заявку по автоматическим шагам, пока не упрётся в ручной этап."""
    # предохранитель от зацикливания
    for _ in range(10):
        if app.state == S.VALIDATION:
            problems = run_validation(db, app)
            if problems:
                state_machine.apply_event(
                    db, app, "validation_incomplete", actor_id,
                    comment="; ".join(problems),
                )
                break
            state_machine.apply_event(db, app, "validation_ok", actor_id)
        elif app.state == S.ENRICHMENT:
            snap = run_enrichment(db, app)
            failed = snap.profile.get("sources_failed") or []
            comment = "" if not failed else f"источники с ошибкой: {', '.join(failed)}"
            state_machine.apply_event(db, app, "enrichment_done", actor_id, comment=comment)
        elif app.state == S.SCORING:
            score = run_scoring(db, app)
            state_machine.apply_event(
                db, app, "scoring_done", actor_id,
                comment=f"балл {score.score}, риск {score.risk_band}, PD {score.pd_estimate}",
            )
        elif app.state == S.DECISIONING:
            decision = run_decision(db, app)
            event = OUTCOME_EVENT[decision.outcome]
            state_machine.apply_event(
                db, app, event, actor_id,
                comment="; ".join(decision.reasons)[:480],
            )
            break
        else:
            # OFFER/NEEDS_INFO/DECLINED и далее — ручные/клиентские шаги
            break
    return app
