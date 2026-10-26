import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin


class ApplicationState(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VALIDATION = "VALIDATION"
    ENRICHMENT = "ENRICHMENT"
    SCORING = "SCORING"
    DECISIONING = "DECISIONING"
    OFFER = "OFFER"
    NEEDS_INFO = "NEEDS_INFO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    DECLINED = "DECLINED"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    SIGNING = "SIGNING"
    DISBURSED = "DISBURSED"
    SERVICING = "SERVICING"


TERMINAL_STATES = {ApplicationState.DECLINED, ApplicationState.SERVICING}


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))

    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(512), default="")
    form_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    state: Mapped[ApplicationState] = mapped_column(
        SAEnum(ApplicationState), default=ApplicationState.DRAFT, index=True
    )

    company = relationship("Company")
    applicant = relationship("User")
    product = relationship("Product")
    events = relationship(
        "ApplicationEvent",
        back_populates="application",
        order_by="ApplicationEvent.id",
        cascade="all, delete-orphan",
    )
    enrichments = relationship(
        "EnrichmentSnapshot",
        back_populates="application",
        order_by="EnrichmentSnapshot.id",
        cascade="all, delete-orphan",
    )
    scores = relationship(
        "ScoreResult",
        back_populates="application",
        order_by="ScoreResult.id",
        cascade="all, delete-orphan",
    )
    decisions = relationship(
        "Decision",
        back_populates="application",
        order_by="Decision.id",
        cascade="all, delete-orphan",
    )
    offers = relationship(
        "Offer",
        back_populates="application",
        order_by="Offer.id",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "Document",
        back_populates="application",
        order_by="Document.id",
        cascade="all, delete-orphan",
    )
    accounts = relationship(
        "CreditAccount",
        back_populates="application",
        order_by="CreditAccount.id",
        cascade="all, delete-orphan",
    )

    @property
    def company_name(self):
        return self.company.name if self.company else ""

    @property
    def company_inn(self):
        return self.company.inn if self.company else ""

    @property
    def latest_enrichment(self):
        return self.enrichments[-1] if self.enrichments else None

    @property
    def latest_score(self):
        return self.scores[-1] if self.scores else None

    @property
    def latest_decision(self):
        return self.decisions[-1] if self.decisions else None

    @property
    def latest_offer(self):
        return self.offers[-1] if self.offers else None

    @property
    def latest_account(self):
        return self.accounts[-1] if self.accounts else None


class ApplicationEvent(Base, TimestampMixin):
    """Аудит переходов состояния: кто, что, когда."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    event: Mapped[str] = mapped_column(String(64))
    from_state: Mapped[str] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")

    application = relationship("Application", back_populates="events")
