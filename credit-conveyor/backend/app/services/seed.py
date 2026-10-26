"""Синтетические демо-данные: продукты, компания, клиентский и банковский
пользователи. Идемпотентно — повторный запуск ничего не дублирует."""

from datetime import date
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.company import Company
from app.models.policy import PolicyVersion
from app.models.product import Product
from app.models.user import User, UserRole

POLICY_FILE = Path(__file__).resolve().parent.parent / "policies" / "base_policy.yaml"

PRODUCTS = [
    dict(code="working_capital", name="Оборотный кредит", kind="working_capital",
         description="Пополнение оборотных средств на короткий срок.",
         min_amount=100_000, max_amount=10_000_000, min_term=3, max_term=36, base_rate=22.0),
    dict(code="overdraft", name="Овердрафт", kind="overdraft",
         description="Возобновляемый лимит по расчётному счёту.",
         min_amount=50_000, max_amount=5_000_000, min_term=1, max_term=12, base_rate=24.0),
    dict(code="investment", name="Инвестиционный кредит", kind="investment",
         description="Финансирование проектов и покупки оборудования.",
         min_amount=500_000, max_amount=50_000_000, min_term=12, max_term=84, base_rate=19.5),
    dict(code="revenue_based", name="Кредит под выручку", kind="revenue_based",
         description="Погашение процентом с эквайринговой выручки.",
         min_amount=100_000, max_amount=7_000_000, min_term=3, max_term=24, base_rate=26.0),
]


def seed(db: Session) -> None:
    for p in PRODUCTS:
        if db.scalar(select(Product).where(Product.code == p["code"])) is None:
            db.add(Product(**p))
    db.commit()

    company = db.scalar(select(Company).where(Company.inn == "7701234567"))
    if company is None:
        company = Company(
            inn="7701234567", ogrn="1127746000001", name='ООО "Ромашка"',
            okved="47.11", registered_at=date(2019, 5, 20),
            tax_regime="УСН", annual_revenue=24_000_000, employees=12,
        )
        db.add(company)
        db.commit()
        db.refresh(company)

    if db.scalar(select(User).where(User.email == "client@demo.ru")) is None:
        db.add(User(
            email="client@demo.ru", hashed_password=hash_password("client123"),
            full_name="Иван Предприниматель", role=UserRole.owner,
            company_id=company.id,
        ))
    if db.scalar(select(User).where(User.email == "underwriter@bank.ru")) is None:
        db.add(User(
            email="underwriter@bank.ru", hashed_password=hash_password("bank123"),
            full_name="Ольга Андеррайтер", role=UserRole.underwriter,
            company_id=None,
        ))
    if db.scalar(select(User).where(User.email == "risk@bank.ru")) is None:
        db.add(User(
            email="risk@bank.ru", hashed_password=hash_password("risk123"),
            full_name="Павел Риск-менеджер", role=UserRole.risk_admin,
            company_id=None,
        ))
    db.commit()

    # Дополнительные демо-персоны под разные исходы решения
    extra = [
        dict(inn="7701000017", name='ООО "Берёзка"', okved="62.01",
             years=8, revenue=30_000_000, employees=15,
             email="client2@demo.ru", full_name="Мария Директор"),
        dict(inn="7701000003", name='ООО "Осина"', okved="56.10",
             years=3, revenue=9_000_000, employees=6,
             email="client3@demo.ru", full_name="Сергей Владелец"),
        dict(inn="7701000009", name='ООО "Клён"', okved="47.19",
             years=2, revenue=6_000_000, employees=4,
             email="client4@demo.ru", full_name="Анна Бухгалтер"),
        dict(inn="7700000001", name='ООО "Весна"', okved="56.10",
             years=4, revenue=9_200_000, employees=5,
             email="client5@demo.ru", full_name="Пётр Кафе"),
    ]
    for e in extra:
        comp = db.scalar(select(Company).where(Company.inn == e["inn"]))
        if comp is None:
            comp = Company(
                inn=e["inn"], ogrn="112774600" + e["inn"][-4:], name=e["name"],
                okved=e["okved"], registered_at=date(2026 - e["years"], 3, 1),
                tax_regime="УСН", annual_revenue=e["revenue"], employees=e["employees"],
            )
            db.add(comp)
            db.commit()
            db.refresh(comp)
        if db.scalar(select(User).where(User.email == e["email"])) is None:
            db.add(User(
                email=e["email"], hashed_password=hash_password("client123"),
                full_name=e["full_name"], role=UserRole.owner, company_id=comp.id,
            ))
    db.commit()

    # Демо-аккаунт с полным доступом: и клиент (своя компания), и банк (видит всё)
    demo_company = db.scalar(select(Company).where(Company.inn == "7701000017"))
    if db.scalar(select(User).where(User.email == "demo@alfa.ru")) is None:
        db.add(User(
            email="demo@alfa.ru", hashed_password=hash_password("demo123"),
            full_name="Демо-пользователь", role=UserRole.demo,
            company_id=demo_company.id if demo_company else None,
        ))
        db.commit()

    if db.scalar(select(PolicyVersion)) is None:
        yaml_text = POLICY_FILE.read_text(encoding="utf-8")
        body = yaml.safe_load(yaml_text)
        db.add(PolicyVersion(
            version=1, name=body.get("name", "Базовая политика"),
            active=True, body=body, yaml_text=yaml_text, created_by="system",
        ))
        db.commit()

    seed_demo_applications(db)
    seed_auxiliary_applications(db)


def seed_demo_applications(db: Session) -> None:
    """Предзаполняет несколько заявок во всех исходах, включая выданную с
    сопровождением, чтобы с демо-аккаунта сразу был виден весь функционал.
    Лучшее усилие: при недоступности моков просто пропускаем."""
    from app.models.application import Application
    from app.models.document import Document
    from app.services import pipeline, servicing, state_machine

    if db.scalar(select(Application)) is not None:
        return

    # (email клиента, сумма, срок, довести_до_сопровождения)
    specs = [
        ("client2@demo.ru", 1_500_000, 18, True, None),             # Берёзка: здоровый
        ("client5@demo.ru", 1_000_000, 18, True, "restructure_extend"),  # Весна: риск + применена реструктуризация
        ("client@demo.ru", 3_000_000, 24, False, None),             # Ромашка: контрпредложение (оффер)
        ("client4@demo.ru", 1_500_000, 18, False, None),            # Клён: отказ по баллу
        ("client3@demo.ru", 1_500_000, 18, False, None),            # Осина: отказ (счёт заблокирован)
    ]
    try:
        for email, amount, term, to_servicing, action in specs:
            user = db.scalar(select(User).where(User.email == email))
            if user is None or user.company_id is None:
                continue
            app = Application(
                company_id=user.company_id, applicant_id=user.id, product_id=1,
                amount=amount, term_months=term, purpose="Демонстрационная заявка",
            )
            db.add(app)
            db.commit()
            db.refresh(app)
            for d in ("passport", "financials", "bank_statements"):
                db.add(Document(application_id=app.id, doc_type=d, filename=f"{d}.pdf"))
            db.commit()
            db.refresh(app)
            state_machine.apply_event(db, app, "submit", actor_id=user.id)
            state_machine.apply_event(db, app, "start_validation", actor_id=user.id)
            pipeline.advance_auto(db, app, actor_id=user.id)
            if to_servicing and app.latest_offer:
                state_machine.apply_event(db, app, "accept_offer", actor_id=user.id,
                                          comment="Демо: клиент принял условия")
                off = app.latest_offer
                off.accepted = True
                db.add(off)
                db.commit()
                state_machine.apply_event(db, app, "start_signing", actor_id=user.id,
                                          comment="Подписание (смоделировано)")
                state_machine.apply_event(db, app, "disburse", actor_id=user.id,
                                          comment="Выдача (смоделировано)")
                acc = servicing.create_account(db, app)
                state_machine.apply_event(db, app, "start_servicing", actor_id=user.id,
                                          comment="Открыт этап сопровождения")
                if action:
                    profile = app.latest_enrichment.profile if app.latest_enrichment else {}
                    servicing.apply_action(db, acc, action, profile)
    except Exception:
        db.rollback()  # моки недоступны при старте — демо-данные не критичны


def seed_auxiliary_applications(db: Session) -> None:
    """Extra reproducible examples for NEEDS_INFO and MANUAL_REVIEW."""
    from app.models.application import Application
    from app.models.document import Document
    from app.services import pipeline, state_machine
    user = db.scalar(select(User).where(User.email == "client2@demo.ru"))
    if not user:
        return
    for marker, purpose, complete in [
        ("needs-info", "Демо: дополнить документы перед решением", False),
        ("manual-review", "Демо: ручной пересмотр для андеррайтера", True),
    ]:
        existing = db.scalar(select(Application).where(Application.form_data["demo_fixture"].astext == marker))
        if existing:
            continue
        item = Application(company_id=user.company_id, applicant_id=user.id, product_id=1, amount=500000, term_months=12, purpose=purpose, form_data={"demo_fixture": marker})
        db.add(item)
        db.commit()
        db.refresh(item)
        for dtype in (["passport", "financials", "bank_statements"] if complete else ["passport"]):
            db.add(Document(application_id=item.id, doc_type=dtype, filename=f"{dtype}.pdf"))
        db.commit()
        db.refresh(item)
        state_machine.apply_event(db, item, "submit", user.id)
        state_machine.apply_event(db, item, "start_validation", user.id)
        pipeline.advance_auto(db, item, user.id)
        if complete:
            state_machine.apply_event(db, item, "to_manual_review", user.id, "Демо: прошу учесть новый контракт на поставку")
