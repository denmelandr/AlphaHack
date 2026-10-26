"""Машина состояний заявки — единый источник правды о переходах.

Любое изменение состояния проходит только здесь: проверяется допустимость
перехода по событию и записывается в аудит (ApplicationEvent).
"""

from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationEvent, ApplicationState as S

# event -> (from_state -> to_state)
TRANSITIONS: dict[str, dict[S, S]] = {
    "revise_conditions": {S.OFFER: S.DECISIONING, S.DECLINED: S.DECISIONING, S.NEEDS_INFO: S.DECISIONING},
    "submit": {S.DRAFT: S.SUBMITTED},
    "start_validation": {S.SUBMITTED: S.VALIDATION},
    "validation_ok": {S.VALIDATION: S.ENRICHMENT},
    "validation_incomplete": {S.VALIDATION: S.NEEDS_INFO},
    "enrichment_done": {S.ENRICHMENT: S.SCORING},
    "scoring_done": {S.SCORING: S.DECISIONING},
    "decide_approve": {S.DECISIONING: S.OFFER},
    "decide_counter": {S.DECISIONING: S.OFFER},
    "decide_need_info": {S.DECISIONING: S.NEEDS_INFO},
    "decide_decline": {S.DECISIONING: S.DECLINED},
    "to_manual_review": {
        S.DECISIONING: S.MANUAL_REVIEW,
        S.OFFER: S.MANUAL_REVIEW,
        S.DECLINED: S.MANUAL_REVIEW,
        S.NEEDS_INFO: S.MANUAL_REVIEW,
    },
    "manual_approve": {S.MANUAL_REVIEW: S.OFFER},
    "manual_decline": {S.MANUAL_REVIEW: S.DECLINED},
    "manual_need_info": {S.MANUAL_REVIEW: S.NEEDS_INFO},
    "client_resubmit": {S.NEEDS_INFO: S.VALIDATION},
    "accept_offer": {S.OFFER: S.OFFER_ACCEPTED},
    "adjust_offer": {S.OFFER: S.DECISIONING},
    "start_signing": {S.OFFER_ACCEPTED: S.SIGNING},
    "disburse": {S.SIGNING: S.DISBURSED},
    "start_servicing": {S.DISBURSED: S.SERVICING},
}


class TransitionError(Exception):
    pass


def available_events(state: S) -> list[str]:
    return [ev for ev, mapping in TRANSITIONS.items() if state in mapping]


def apply_event(
    db: Session,
    application: Application,
    event: str,
    actor_id: int | None = None,
    comment: str = "",
) -> Application:
    mapping = TRANSITIONS.get(event)
    if mapping is None:
        raise TransitionError(f"Неизвестное событие: {event}")
    current = application.state
    target = mapping.get(current)
    if target is None:
        raise TransitionError(
            f"Переход '{event}' недопустим из состояния '{current.value}'"
        )

    audit = ApplicationEvent(
        application_id=application.id,
        event=event,
        from_state=current.value,
        to_state=target.value,
        actor_id=actor_id,
        comment=comment,
    )
    application.state = target
    db.add(audit)
    db.add(application)
    db.commit()
    db.refresh(application)
    return application
