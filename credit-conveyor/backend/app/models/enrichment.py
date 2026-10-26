from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin


class EnrichmentSnapshot(Base, TimestampMixin):
    """Снимок данных из внешних источников на момент обработки заявки.

    raw — сырые ответы источников (БКИ, ЕГРЮЛ/ЕГРИП, ФНС, ОФД).
    profile — нормализованный единый профиль заявителя для скоринга.
    """

    __tablename__ = "enrichment_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), index=True
    )
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)

    application = relationship("Application", back_populates="enrichments")
