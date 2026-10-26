from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin


class CreditAccount(Base, TimestampMixin):
    """Выданный кредит на этапе сопровождения: остаток, платёж, график,
    журнал применённых превентивных действий."""

    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    principal: Mapped[float] = mapped_column(Numeric(18, 2))
    rate: Mapped[float] = mapped_column(Numeric(5, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    monthly_payment: Mapped[float] = mapped_column(Numeric(18, 2))
    outstanding_balance: Mapped[float] = mapped_column(Numeric(18, 2))
    next_payment_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")
    servicing_log: Mapped[list] = mapped_column(JSONB, default=list)
    # Автопилот: правила, по которым система сама закрывает прогнозируемый разрыв
    autopilot: Mapped[dict] = mapped_column(JSONB, default=dict)

    application = relationship("Application", back_populates="accounts")
