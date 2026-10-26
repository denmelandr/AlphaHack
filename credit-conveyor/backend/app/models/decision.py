from sqlalchemy import Boolean, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin


class Decision(Base, TimestampMixin):
    """Итог кредитного рассмотрения: одобрение / контрусловия / запрос данных /
    отказ. Не бинарен (кейс, стр. 15)."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(16))  # approve/counter/need_info/decline
    policy_version: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    actor: Mapped[str] = mapped_column(String(64), default="policy-engine")

    application = relationship("Application", back_populates="decisions")


class Offer(Base, TimestampMixin):
    """Предложенные условия финансирования и график платежей."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    rate: Mapped[float] = mapped_column(Numeric(5, 2))
    monthly_payment: Mapped[float] = mapped_column(Numeric(18, 2))
    total_payment: Mapped[float] = mapped_column(Numeric(18, 2))
    overpayment: Mapped[float] = mapped_column(Numeric(18, 2))
    collateral_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_counter: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule: Mapped[list] = mapped_column(JSONB, default=list)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)

    application = relationship("Application", back_populates="offers")
