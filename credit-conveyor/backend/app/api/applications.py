from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.application import Application, ApplicationState
from app.models.company import Company
from app.models.document import Document
from app.models.product import Product
from app.models.score import ScoreResult
from app.models.decision import Decision, Offer
from pydantic import BaseModel
from datetime import datetime, timezone
from app.models.user import User
from app.schemas.schemas import (
    ApplicationCreate,
    ApplicationDetail,
    AccountOut,
    ApplicationOut,
    ApplicationUpdate,
    AutopilotConfig,
    CopilotOut,
    CrossSellOut,
    DecisionOut,
    DocumentItem,
    DocumentUpload,
    EnrichmentOut,
    OfferOut,
    ReadinessOut,
    ReviewRequest,
    ScoreOut,
    ForecastRequest,
    ServicingApply,
    ServicingOut,
    SimulateRequest,
    SimulateResponse,
    TransitionRequest,
)
from app.services import documents as docs_service
from app.services import (
    copilot,
    covenants,
    cross_sell,
    forecast,
    pipeline,
    servicing,
    state_machine,
)

router = APIRouter(prefix="/applications", tags=["applications"])


def _visible_query(user: User):
    q = select(Application).order_by(Application.id.desc())
    if not user.is_bank:
        q = q.where(Application.company_id == user.company_id)
    return q


def _get_or_404(db: Session, user: User, app_id: int) -> Application:
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    if not user.is_bank and app.company_id != user.company_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к заявке")
    return app


def _detail(db: Session, app: Application) -> ApplicationDetail:
    db.refresh(app)
    detail = ApplicationDetail.model_validate(app)
    detail.events = app.events  # type: ignore[assignment]
    detail.available_events = state_machine.available_events(app.state)
    snap = app.latest_enrichment
    detail.enrichment = EnrichmentOut.model_validate(snap) if snap else None
    sc = app.latest_score
    detail.score = ScoreOut.model_validate(sc) if sc else None
    dec = app.latest_decision
    detail.decision = DecisionOut.model_validate(dec) if dec else None
    off = app.latest_offer
    detail.offer = OfferOut.model_validate(off) if off else None
    return detail


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Application]:
    return list(db.scalars(_visible_query(user)))


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Application:
    if not user.acts_as_client or user.company_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Заявку создаёт клиент компании")
    product = db.get(Product, data.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Продукт не найден")
    app = Application(
        company_id=user.company_id,
        applicant_id=user.id,
        product_id=product.id,
        amount=data.amount,
        term_months=data.term_months,
        purpose=data.purpose,
        form_data=data.form_data or {},
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def _doc_items(app: Application, product: Product) -> list[DocumentItem]:
    uploaded = {d.doc_type: d.filename for d in app.documents}
    items: list[DocumentItem] = []
    for d in docs_service.required_docs(product.kind):
        items.append(DocumentItem(
            type=d["type"], name=d["name"], how=d["how"],
            uploaded=d["type"] in uploaded, filename=uploaded.get(d["type"], ""),
            has_file=_document_path(app.id, d["type"]).is_file(),
        ))
    return items


def _readiness(db: Session, app: Application) -> ReadinessOut:
    product = db.get(Product, app.product_id)
    problems = pipeline.run_validation(db, app)
    items = _doc_items(app, product)
    docs_total = len(items)
    docs_uploaded = sum(1 for i in items if i.uploaded)
    field_problems = [p for p in problems if "документ" not in p.lower()]
    return ReadinessOut(
        fields_ok=len(field_problems) == 0,
        docs_total=docs_total,
        docs_uploaded=docs_uploaded,
        ready=len(problems) == 0,
        missing=problems,
    )


EDITABLE_STATES = {ApplicationState.DRAFT, ApplicationState.NEEDS_INFO}


def _require_client_draft(app: Application, user: User) -> None:
    if not user.acts_as_client:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно клиенту")
    if app.state not in EDITABLE_STATES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Заявку сейчас нельзя редактировать")


@router.patch("/{app_id}", response_model=ApplicationDetail)
def update_application(
    app_id: int,
    data: ApplicationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    app = _get_or_404(db, user, app_id)
    _require_client_draft(app, user)
    if data.product_id is not None:
        if db.get(Product, data.product_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Продукт не найден")
        app.product_id = data.product_id
    if data.amount is not None:
        app.amount = data.amount
    if data.term_months is not None:
        app.term_months = data.term_months
    if data.purpose is not None:
        app.purpose = data.purpose
    if data.form_data is not None:
        app.form_data = data.form_data
    db.add(app)
    db.commit()
    return _detail(db, app)


@router.get("/{app_id}/documents", response_model=list[DocumentItem])
def list_documents(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentItem]:
    app = _get_or_404(db, user, app_id)
    return _doc_items(app, db.get(Product, app.product_id))


@router.post("/{app_id}/documents", response_model=list[DocumentItem])
def upload_document(
    app_id: int,
    data: DocumentUpload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentItem]:
    app = _get_or_404(db, user, app_id)
    _require_client_draft(app, user)
    existing = next((d for d in app.documents if d.doc_type == data.doc_type), None)
    if existing:
        existing.filename = data.filename
    else:
        db.add(Document(application_id=app.id, doc_type=data.doc_type, filename=data.filename))
    db.commit()
    db.refresh(app)
    return _doc_items(app, db.get(Product, app.product_id))


@router.delete("/{app_id}/documents/{doc_type}", response_model=list[DocumentItem])
def delete_document(
    app_id: int,
    doc_type: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentItem]:
    app = _get_or_404(db, user, app_id)
    _require_client_draft(app, user)
    for d in list(app.documents):
        if d.doc_type == doc_type:
            db.delete(d)
    db.commit()
    _document_path(app_id, doc_type).unlink(missing_ok=True)
    db.refresh(app)
    return _doc_items(app, db.get(Product, app.product_id))


@router.get("/{app_id}/readiness", response_model=ReadinessOut)
def readiness(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReadinessOut:
    app = _get_or_404(db, user, app_id)
    return _readiness(db, app)


@router.get("/{app_id}", response_model=ApplicationDetail)
def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    app = _get_or_404(db, user, app_id)
    return _detail(db, app)


@router.get("/{app_id}/enrichment", response_model=EnrichmentOut)
def get_enrichment(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EnrichmentOut:
    app = _get_or_404(db, user, app_id)
    snap = app.latest_enrichment
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Обогащение ещё не выполнялось")
    return EnrichmentOut.model_validate(snap)


@router.get("/{app_id}/score", response_model=ScoreOut)
def get_score(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScoreOut:
    app = _get_or_404(db, user, app_id)
    sc = app.latest_score
    if sc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Скоринг ещё не выполнялся")
    return ScoreOut.model_validate(sc)


@router.post("/{app_id}/submit", response_model=ApplicationDetail)
def submit_application(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    app = _get_or_404(db, user, app_id)
    if not user.acts_as_client:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Отправляет заявку клиент")
    try:
        state_machine.apply_event(db, app, "submit", actor_id=user.id)
        state_machine.apply_event(db, app, "start_validation", actor_id=user.id)
        pipeline.advance_auto(db, app, actor_id=user.id)
    except state_machine.TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return _detail(db, app)


@router.get("/{app_id}/copilot", response_model=CopilotOut)
def application_copilot(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CopilotOut:
    """Копилот андеррайтера: саммари, аномалии, черновик обоснования."""
    if not user.is_bank:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно банковской стороне")
    app = _get_or_404(db, user, app_id)
    return CopilotOut(**copilot.generate(db, app))


def _app_profile(app: Application) -> dict:
    snap = app.latest_enrichment
    return snap.profile if snap else {}


@router.get("/{app_id}/offers", response_model=CrossSellOut)
def personalized_offers(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CrossSellOut:
    """Персональный подбор продуктов банка под профиль бизнеса со скидкой,
    заработанной уровнем финансового здоровья (не трогает ставку по кредиту)."""
    app = _get_or_404(db, user, app_id)
    company = db.get(Company, app.company_id)
    product = db.get(Product, app.product_id)
    profile = _app_profile(app)
    score = app.latest_score
    risk_band = score.risk_band if score else None

    serviced = app.state == ApplicationState.SERVICING and app.latest_account is not None
    breaches = 0
    preventive_used = False
    if serviced:
        acc = app.latest_account
        rad = forecast.radar(profile, acc)
        res = forecast.resilience(profile, acc)
        policy = pipeline.get_active_policy(db)
        breaches = len(covenants.evaluate(policy.body if policy else {},
                                          profile, acc, rad, res))
        preventive_used = bool(acc.servicing_log)

    result = cross_sell.offers_for(
        company, profile, product.kind if product else "working_capital",
        risk_band, serviced, breaches, preventive_used,
    )
    return CrossSellOut(**result)


@router.get("/{app_id}/servicing", response_model=ServicingOut)
def get_servicing(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ServicingOut:
    app = _get_or_404(db, user, app_id)
    acc = app.latest_account
    if acc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Кредит ещё не выдан")
    profile = _app_profile(app)
    return ServicingOut(
        account=AccountOut.model_validate(acc),
        signals=servicing.compute_signals(acc, profile),
        actions=servicing.action_options(acc, profile),
        radar=forecast.radar(profile, acc),
    )


@router.post("/{app_id}/servicing/autopilot", response_model=ServicingOut)
def configure_autopilot(
    app_id: int,
    data: AutopilotConfig,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ServicingOut:
    if not user.acts_as_client:
        raise HTTPException(403, "Правила автопилота задаёт клиент")
    app = _get_or_404(db, user, app_id)
    acc = app.latest_account
    if acc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Кредит ещё не выдан")
    cfg = dict(acc.autopilot or {})
    cfg.update({"enabled": data.enabled, "max_bridge": data.max_bridge})
    acc.autopilot = cfg
    db.add(acc)
    db.commit()
    db.refresh(acc)
    profile = _app_profile(app)
    return ServicingOut(
        account=AccountOut.model_validate(acc),
        signals=servicing.compute_signals(acc, profile),
        actions=servicing.action_options(acc, profile),
        radar=forecast.radar(profile, acc),
    )


@router.post("/{app_id}/servicing/autopilot/run", response_model=ServicingOut)
def run_autopilot(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ServicingOut:
    if not user.acts_as_client:
        raise HTTPException(403, "Правила автопилота задаёт клиент")
    app = _get_or_404(db, user, app_id)
    acc = app.latest_account
    if acc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Кредит ещё не выдан")
    profile = _app_profile(app)
    servicing.run_autopilot(db, acc, profile)
    db.refresh(acc)
    return ServicingOut(
        account=AccountOut.model_validate(acc),
        signals=servicing.compute_signals(acc, profile),
        actions=servicing.action_options(acc, profile),
        radar=forecast.radar(profile, acc),
    )


@router.post("/{app_id}/servicing/forecast")
def servicing_forecast(
    app_id: int,
    data: ForecastRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """What-if прогноз ликвидности: падение выручки и разовый расход."""
    app = _get_or_404(db, user, app_id)
    acc = app.latest_account
    if acc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Кредит ещё не выдан")
    return forecast.radar(
        _app_profile(app), acc,
        drop_pct=data.revenue_drop_pct, extra_expense=data.extra_expense,
    )


@router.post("/{app_id}/servicing/apply", response_model=ServicingOut)
def apply_servicing(
    app_id: int,
    data: ServicingApply,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ServicingOut:
    app = _get_or_404(db, user, app_id)
    acc = app.latest_account
    if acc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Кредит ещё не выдан")
    profile = _app_profile(app)
    if not user.acts_as_client:
        raise HTTPException(403, "Действия сопровождения подтверждает клиент")
    try:
        acc = servicing.apply_action(db, acc, data.action, profile)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return ServicingOut(
        account=AccountOut.model_validate(acc),
        signals=servicing.compute_signals(acc, profile),
        actions=servicing.action_options(acc, profile),
        radar=forecast.radar(profile, acc),
    )


@router.post("/{app_id}/simulate", response_model=SimulateResponse)
def simulate_conditions(
    app_id: int,
    data: SimulateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SimulateResponse:
    """Конструктор условий «Путь к одобрению»: пересчёт решения под кандидатные
    параметры без изменения заявки."""
    app = _get_or_404(db, user, app_id)
    product = db.get(Product, app.product_id)
    if not (float(product.min_amount) <= data.amount <= float(product.max_amount)) or not (product.min_term <= data.term_months <= product.max_term):
        raise HTTPException(422, "Сумма или срок вне диапазона продукта")
    result = pipeline.simulate(
        db, app, data.amount, data.term_months,
        data.collateral_offered, data.guarantor_offered,
    )
    return SimulateResponse(**result)


@router.post("/{app_id}/review", response_model=ApplicationDetail)
def request_review(
    app_id: int,
    data: ReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    """Клиент просит пересмотр решения человеком — заявка уходит андеррайтеру."""
    app = _get_or_404(db, user, app_id)
    if not user.acts_as_client:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Пересмотр запрашивает клиент")
    comment = f"Запрос пересмотра клиентом. {data.comment}".strip()
    try:
        state_machine.apply_event(db, app, "to_manual_review", actor_id=user.id, comment=comment)
    except state_machine.TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return _detail(db, app)


@router.post("/{app_id}/resubmit", response_model=ApplicationDetail)
def resubmit_application(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    app = _get_or_404(db, user, app_id)
    if not user.acts_as_client:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Переотправляет заявку клиент")
    try:
        state_machine.apply_event(db, app, "client_resubmit", actor_id=user.id,
                                  comment="Клиент дополнил заявку")
        pipeline.advance_auto(db, app, actor_id=user.id)
    except state_machine.TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return _detail(db, app)


@router.post("/{app_id}/accept", response_model=ApplicationDetail)
def accept_offer(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    app = _get_or_404(db, user, app_id)
    if not user.acts_as_client:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Оффер принимает клиент")
    offer = app.latest_offer
    if offer is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "По заявке нет оффера")
    try:
        state_machine.apply_event(db, app, "accept_offer", actor_id=user.id,
                                  comment="Клиент принял условия")
        offer.accepted = True
        db.add(offer)
        db.commit()
        # Подписание и выдача смоделированы (допускается кейсом): доводим заявку
        # до этапа сопровождения, чтобы кредит сразу стал обслуживаемым.
        state_machine.apply_event(db, app, "start_signing", actor_id=user.id,
                                  comment="Подписание документов (смоделировано)")
        state_machine.apply_event(db, app, "disburse", actor_id=user.id,
                                  comment="Выдача средств (смоделировано)")
        servicing.create_account(db, app)
        state_machine.apply_event(db, app, "start_servicing", actor_id=user.id,
                                  comment="Открыт этап сопровождения")
    except state_machine.TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return _detail(db, app)


@router.post("/{app_id}/transition", response_model=ApplicationDetail)
def transition_application(
    app_id: int,
    data: TransitionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationDetail:
    app = _get_or_404(db, user, app_id)
    if not user.is_bank:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Переходы кредитного процесса выполняет банковская сторона",
        )
    allowed_bank_events = {"to_manual_review", "manual_approve", "manual_decline", "manual_need_info", "adjust_offer"}
    if data.event not in allowed_bank_events:
        raise HTTPException(403, "Клиентские и автоматические этапы недоступны через банковский переход")
    if data.event.startswith("manual_"):
        if app.state != ApplicationState.MANUAL_REVIEW:
            raise HTTPException(409, "Сначала возьмите заявку на ручной пересмотр")
        if not data.comment.strip():
            raise HTTPException(422, "Укажите обоснование ручного решения")
        outcome = {"manual_approve": "approve", "manual_decline": "decline", "manual_need_info": "need_info"}[data.event]
        pol = pipeline.get_active_policy(db)
        db.add(Decision(application_id=app.id, outcome=outcome, policy_version=pol.version if pol else 0, reasons=[data.comment], details={"manual": True}, actor=user.email))
        if outcome == "approve":
            from app.services.policy import _build_offer
            product = db.get(Product, app.product_id)
            db.add(Offer(application_id=app.id, **_build_offer(float(app.amount), app.term_months, float(product.base_rate), False, False)))
        db.flush()
    try:
        state_machine.apply_event(db, app, data.event, actor_id=user.id, comment=data.comment)
        pipeline.advance_auto(db, app, actor_id=user.id)
        # при выдаче создаём кредитный счёт и переводим на сопровождение
        if app.state == ApplicationState.DISBURSED:
            servicing.create_account(db, app)
            state_machine.apply_event(db, app, "start_servicing", actor_id=user.id,
                                      comment="Кредит выдан, открыт этап сопровождения")
    except state_machine.TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return _detail(db, app)


@router.post("/{app_id}/conditions", response_model=ApplicationDetail)
def save_conditions(app_id: int, data: SimulateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = _get_or_404(db, user, app_id)
    if not user.acts_as_client:
        raise HTTPException(403, "Условия выбирает клиент")
    if app.state not in {ApplicationState.OFFER, ApplicationState.DECLINED, ApplicationState.NEEDS_INFO}:
        raise HTTPException(409, "На этом этапе условия не редактируются")
    product = db.get(Product, app.product_id)
    if not (float(product.min_amount) <= data.amount <= float(product.max_amount)) or not (product.min_term <= data.term_months <= product.max_term):
        raise HTTPException(422, "Сумма или срок вне диапазона продукта")
    if not app.latest_enrichment:
        raise HTTPException(409, "Сначала выполните обогащение заявки")
    result = pipeline.simulate(db, app, data.amount, data.term_months, data.collateral_offered, data.guarantor_offered)
    if not result.get("offer"):
        raise HTTPException(409, "Эти условия не проходят политику. Запросите пересмотр")
    app.amount = data.amount
    app.term_months = data.term_months
    app.form_data = {**(app.form_data or {}), "collateral_offered": data.collateral_offered, "guarantor_offered": data.guarantor_offered}
    state_machine.apply_event(db, app, "revise_conditions", user.id, "Клиент выбрал условия конструктора")
    policy = pipeline.get_active_policy(db)
    db.add(ScoreResult(application_id=app.id, score=result["score"], risk_band=result["risk_band"], pd_estimate=result["pd_estimate"], factors=result["factors"]))
    db.add(Decision(application_id=app.id, outcome=result["outcome"], policy_version=policy.version if policy else 0, reasons=result["reasons"], details={"source": "conditions"}))
    db.add(Offer(application_id=app.id, **result["offer"]))
    db.commit()
    state_machine.apply_event(db, app, pipeline.OUTCOME_EVENT[result["outcome"]], user.id, "; ".join(result["reasons"]))
    return _detail(db, app)


class CollaborationUpdate(BaseModel):
    actor: str = ""
    task: str = ""
    complete: bool = False
    sign: bool = False


@router.get("/{app_id}/collaboration")
def get_collaboration(app_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = _get_or_404(db, user, app_id)
    return (app.form_data or {}).get("collaboration", {"tasks": {}, "signed": False, "history": []})


@router.post("/{app_id}/collaboration")
def update_collaboration(app_id: int, data: CollaborationUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = _get_or_404(db, user, app_id)
    if not user.acts_as_client:
        raise HTTPException(403, "Доступно участнику компании")
    actor = data.actor if user.role.value == "demo" else user.role.value
    required = {"finance": {"accountant", "finance"}, "documents": {"employee"}, "terms": {"director", "owner"}}
    value = dict((app.form_data or {}).get("collaboration", {}))
    if value.get("signed"):
        raise HTTPException(409, "Демо-согласование уже завершено")
    tasks = dict(value.get("tasks", {}))
    if data.sign:
        if actor not in {"director", "owner"} or not all(tasks.get(k) for k in required):
            raise HTTPException(403, "Нужны все задачи и роль директора")
        value["signed"] = True
        action = "Внутреннее согласование и демо-подпись (не ПЭП)"
    else:
        if data.task not in required or actor not in required[data.task]:
            raise HTTPException(403, "Это задача другого участника")
        tasks[data.task] = data.complete
        value["tasks"] = tasks
        action = f"{data.task}: {'готово' if data.complete else 'возвращено'}"
    value["history"] = [*value.get("history", []), {"actor": f"{user.email} ({actor})", "action": action, "at": datetime.now(timezone.utc).isoformat()}][-100:]
    app.form_data = {**(app.form_data or {}), "collaboration": value}
    db.add(app)
    db.commit()
    return value


# Actual local document storage for the integrated cabinet; metadata-only seed
# documents are still supported and explicitly marked in the response.
from pathlib import Path
import os
import re
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse

UPLOADS = Path(os.getenv("UPLOADS_DIR", "/app/uploads"))


def _document_path(app_id: int, doc_type: str) -> Path:
    if not re.fullmatch(r"[a-z_]{1,32}", doc_type):
        raise HTTPException(422, "Неверный тип документа")
    return UPLOADS / str(app_id) / doc_type


@router.post("/{app_id}/documents/file", response_model=list[DocumentItem])
def upload_document_file(app_id: int, doc_type: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = _get_or_404(db, user, app_id)
    _require_client_draft(app, user)
    product = db.get(Product, app.product_id)
    if doc_type not in {doc["type"] for doc in docs_service.required_docs(product.kind)}:
        raise HTTPException(422, "Документ не входит в перечень продукта")
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
        raise HTTPException(422, "Поддерживаются PDF, JPG и PNG")
    content = file.file.read(5 * 1024 * 1024 + 1)
    if not content or len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Размер файла должен быть от 1 байта до 5 МБ")
    path = _document_path(app_id, doc_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(content)
    temp.replace(path)
    document = next((d for d in app.documents if d.doc_type == doc_type), None)
    if document:
        document.filename = filename
    else:
        db.add(Document(application_id=app_id, doc_type=doc_type, filename=filename))
    db.commit()
    db.refresh(app)
    return _doc_items(app, product)


@router.get("/{app_id}/documents/{doc_type}/file")
def download_document_file(app_id: int, doc_type: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = _get_or_404(db, user, app_id)
    document = next((d for d in app.documents if d.doc_type == doc_type), None)
    path = _document_path(app_id, doc_type)
    if document is None or not path.is_file():
        raise HTTPException(404, "Содержимое файла отсутствует: это документ из синтетического seed")
    return FileResponse(path, filename=document.filename, media_type="application/octet-stream")
