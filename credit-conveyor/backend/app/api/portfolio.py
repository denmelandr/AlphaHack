from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.db import get_db
from app.models.application import Application, ApplicationState
from app.models.company import Company
from app.models.policy import PolicyVersion
from app.models.user import User, UserRole
from app.models.product import Product
from app.services import covenants, cross_sell, forecast

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

bank_only = require_roles(UserRole.underwriter, UserRole.risk_admin, UserRole.demo)

# Модельные допущения для оценки эффекта (помечаются в UI как модельные)
BASELINE_30DPD = 0.08          # базовая доля 30+ просрочки по сегменту
AVERTED_PER_ACTION = 0.35      # доля предотвращённых просрочек на сработавшее действие
CROSS_SELL_MARGIN = 4000       # модельная маржа банка с одного кросс-продукта в мес., ₽
CROSS_SELL_CONVERSION = 0.3    # модельная конверсия персонального предложения


def _serviced(db: Session):
    apps = db.scalars(
        select(Application).where(Application.state == ApplicationState.SERVICING)
    )
    return [a for a in apps if a.latest_account and a.latest_enrichment]


def _active_policy_body(db: Session) -> dict:
    pol = db.scalar(select(PolicyVersion).where(PolicyVersion.active.is_(True)))
    return pol.body if pol else {}


@router.get("/early-warnings")
def early_warnings(db: Session = Depends(get_db), _: User = Depends(bank_only)) -> list[dict]:
    policy = _active_policy_body(db)
    items = []
    for app in _serviced(db):
        acc = app.latest_account
        profile = app.latest_enrichment.profile
        rad = forecast.radar(profile, acc)
        res = forecast.resilience(profile, acc)
        breaches = covenants.evaluate(policy, profile, acc, rad, res)
        company = db.get(Company, app.company_id)
        acted = bool(acc.servicing_log)
        items.append({
            "application_id": app.id,
            "company": company.name if company else "",
            "outstanding": float(acc.outstanding_balance),
            "severity": covenants.worst_severity(breaches),
            "breaches": breaches,
            "gap": rad.get("gap"),
            "resilience_pct": res,
            "recommended": rad.get("recommended"),
            "preventive_applied": acted,
        })
    order = {"high": 0, "medium": 1, "ok": 2}
    items.sort(key=lambda x: (order.get(x["severity"], 3), x["resilience_pct"]))
    return items


@router.get("/metrics")
def metrics(db: Session = Depends(get_db), _: User = Depends(bank_only)) -> dict:
    policy = _active_policy_body(db)
    serviced = _serviced(db)
    total = len(serviced)
    with_action = 0
    at_risk = 0
    outstanding = 0.0
    at_risk_outstanding = 0.0
    cross_sell_candidates = 0
    for app in serviced:
        acc = app.latest_account
        profile = app.latest_enrichment.profile
        rad = forecast.radar(profile, acc)
        res = forecast.resilience(profile, acc)
        breaches = covenants.evaluate(policy, profile, acc, rad, res)
        outstanding += float(acc.outstanding_balance)
        if acc.servicing_log:
            with_action += 1
        if breaches:
            at_risk += 1
            at_risk_outstanding += float(acc.outstanding_balance)
        company = db.get(Company, app.company_id)
        product = db.get(Product, app.product_id)
        matched = cross_sell.match(company, profile,
                                   product.kind if product else "working_capital")
        cross_sell_candidates += len(matched)

    preventive_share = round(with_action / total * 100, 1) if total else 0.0
    # модельная оценка снижения 30+ просрочки за счёт превентивных действий
    projected_30dpd_reduction_pp = round(
        with_action / total * BASELINE_30DPD * AVERTED_PER_ACTION * 100, 2
    ) if total else 0.0
    prevented_delinquencies = round(with_action * BASELINE_30DPD * AVERTED_PER_ACTION, 1)

    # модельная оценка дохода от кросс-продаж по персональным предложениям
    projected_cross_sell_monthly = round(
        total * CROSS_SELL_CONVERSION * CROSS_SELL_MARGIN
    )

    return {
        "serviced_total": total,
        "with_preventive_action": with_action,
        "preventive_share_pct": preventive_share,
        "at_risk": at_risk,
        "portfolio_outstanding": round(outstanding),
        "at_risk_outstanding": round(at_risk_outstanding),
        "projected_30dpd_reduction_pp": projected_30dpd_reduction_pp,
        "prevented_delinquencies": prevented_delinquencies,
        "cross_sell_candidates": cross_sell_candidates,
        "projected_cross_sell_monthly": projected_cross_sell_monthly,
        "assumptions": {
            "baseline_30dpd": BASELINE_30DPD,
            "averted_per_action": AVERTED_PER_ACTION,
            "cross_sell_margin": CROSS_SELL_MARGIN,
            "cross_sell_conversion": CROSS_SELL_CONVERSION,
        },
    }
