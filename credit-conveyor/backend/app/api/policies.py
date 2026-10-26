import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.db import get_db
from app.models.policy import PolicyAudit, PolicyVersion
from app.models.user import User, UserRole
from app.schemas.schemas import (
    PolicyAuditOut,
    PolicyCreateRequest,
    PolicyDetailOut,
    PolicySimulateRequest,
    PolicyVersionOut,
)
from app.services import policy_sim

router = APIRouter(prefix="/policies", tags=["policies"])

bank_only = require_roles(UserRole.underwriter, UserRole.risk_admin, UserRole.demo)
risk_only = require_roles(UserRole.risk_admin, UserRole.demo)


def _parse_yaml(text: str) -> dict:
    try:
        body = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Ошибка YAML: {exc}")
    if not isinstance(body, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Политика должна быть объектом")
    import math
    def number(value, lo, hi):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and lo <= value <= hi
    bands = body.get("score_bands")
    if not isinstance(bands, dict) or not number(bands.get("approve_min"), 0, 100) or not number(bands.get("counter_min"), 0, 100) or bands["counter_min"] > bands["approve_min"]:
        raise HTTPException(422, "score_bands: нужны числовые пороги 0..100, counter_min <= approve_min")
    for section in ("counter_offer", "affordability"):
        if section in body and not isinstance(body[section], dict):
            raise HTTPException(422, f"{section}: ожидается объект")
    limits = {"amount_factor": (0.01, 1), "rate_add": (0, 50), "collateral_above": (0, 1000000000)}
    for key, value in body.get("counter_offer", {}).items():
        if key not in limits or not number(value, *limits[key]):
            raise HTTPException(422, f"counter_offer.{key}: неверное значение")
    for key, value in body.get("affordability", {}).items():
        if key != "max_payment_to_revenue" or not number(value, 0.01, 1):
            raise HTTPException(422, "affordability: доля платежа должна быть 0.01..1")
    sources = body.get("require_sources", [])
    if not isinstance(sources, list) or any(not isinstance(x, str) or x not in {"bki", "egrul", "fns", "ofd", "receivables"} for x in sources):
        raise HTTPException(422, "require_sources: неизвестный источник")
    known_fields = {"company_status", "account_blocked", "disqualified_persons", "mass_address", "max_overdue_days", "credit_score", "debt_load_percent", "tax_arrears", "registered_years_ago", "overdue_count"}
    known_metrics = {"account_blocked", "forecast_gap", "payment_to_revenue", "revenue_declining", "resilience_pct"}
    for section in ("hard_declines", "covenants"):
        rules = body.get(section, [])
        if not isinstance(rules, list):
            raise HTTPException(422, f"{section}: ожидается список")
        for rule in rules:
            if not isinstance(rule, dict) or not isinstance(rule.get("op"), str) or rule.get("op") not in {"equals", "not_equals", "gte", "lte", "gt", "lt"} or not isinstance(rule.get("reason"), str):
                raise HTTPException(422, f"{section}: неверное правило или оператор")
            if rule.get("op") in {"gte", "lte", "gt", "lt"} and not number(rule.get("value"), -1000000000, 1000000000):
                raise HTTPException(422, "Для числового сравнения требуется число")
            if not isinstance(rule.get("value"), (str, bool, int, float)):
                raise HTTPException(422, "Неверное значение правила")
            if section == "hard_declines" and (not isinstance(rule.get("field"), str) or rule.get("field") not in known_fields):
                raise HTTPException(422, "Неизвестное поле стоп-фактора")
            if section == "covenants" and (not isinstance(rule.get("metric"), str) or rule.get("metric") not in known_metrics or not isinstance(rule.get("severity"), str) or rule.get("severity") not in {"high", "medium"} or not isinstance(rule.get("code"), str) or not rule.get("code")):
                raise HTTPException(422, "Неизвестная метрика или уровень ковенанта")
            key = rule.get("field") if section == "hard_declines" else rule.get("metric")
            if key == "company_status" and (rule["op"] not in {"equals", "not_equals"} or not isinstance(rule["value"], str)):
                raise HTTPException(422, "Статус компании сравнивается со строкой")
            if key in {"account_blocked", "disqualified_persons", "mass_address", "forecast_gap", "revenue_declining"} and (rule["op"] not in {"equals", "not_equals"} or not isinstance(rule["value"], bool)):
                raise HTTPException(422, "Логическая метрика сравнивается с true/false")

    return body


@router.get("", response_model=list[PolicyVersionOut])
def list_policies(db: Session = Depends(get_db), _: User = Depends(bank_only)):
    return list(db.scalars(select(PolicyVersion).order_by(PolicyVersion.version.desc())))


@router.get("/active", response_model=PolicyDetailOut)
def active_policy(db: Session = Depends(get_db), _: User = Depends(bank_only)):
    pol = db.scalar(select(PolicyVersion).where(PolicyVersion.active.is_(True)))
    if pol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Нет активной политики")
    return pol


@router.get("/audit", response_model=list[PolicyAuditOut])
def policy_audit(db: Session = Depends(get_db), _: User = Depends(bank_only)):
    return list(db.scalars(select(PolicyAudit).order_by(PolicyAudit.id.desc())))


@router.post("/simulate")
def simulate_policy(
    data: PolicySimulateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(bank_only),
):
    candidate = _parse_yaml(data.yaml_text)
    active = db.scalar(select(PolicyVersion).where(PolicyVersion.active.is_(True)))
    active_body = active.body if active else {}
    return policy_sim.evaluate(db, active_body, candidate, data.limit)


@router.post("", response_model=PolicyDetailOut, status_code=status.HTTP_201_CREATED)
def create_policy(
    data: PolicyCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(risk_only),
):
    body = _parse_yaml(data.yaml_text)
    max_v = db.scalar(select(PolicyVersion.version).order_by(PolicyVersion.version.desc()))
    version = (max_v or 0) + 1
    pol = PolicyVersion(
        version=version, name=data.name, active=False,
        body=body, yaml_text=data.yaml_text, created_by=user.email,
    )
    db.add(pol)
    db.add(PolicyAudit(version=version, action="created", actor=user.email))
    db.commit()
    db.refresh(pol)
    return pol


@router.post("/{version}/activate", response_model=PolicyDetailOut)
def activate_policy(
    version: int,
    db: Session = Depends(get_db),
    user: User = Depends(risk_only),
):
    pol = db.scalar(select(PolicyVersion).where(PolicyVersion.version == version))
    if pol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Версия не найдена")
    _parse_yaml(pol.yaml_text)
    for p in db.scalars(select(PolicyVersion).where(PolicyVersion.active.is_(True))):
        p.active = False
    pol.active = True
    db.add(PolicyAudit(version=version, action="activated", actor=user.email))
    db.commit()
    db.refresh(pol)
    return pol
