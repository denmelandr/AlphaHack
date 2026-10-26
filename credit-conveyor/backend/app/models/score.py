from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin


class ScoreResult(Base, TimestampMixin):
    """Результат скоринга: балл кредитоспособности, уровень риска и разбор
    по факторам с весами (объяснимость)."""

    __tablename__ = "score_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True
    )
    score: Mapped[int] = mapped_column(Integer)
    risk_band: Mapped[str] = mapped_column(String(16))
    pd_estimate: Mapped[float] = mapped_column(Float)
    factors: Mapped[list] = mapped_column(JSONB, default=list)

    application = relationship("Application", back_populates="scores")
