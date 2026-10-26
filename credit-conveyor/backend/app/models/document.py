from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin


class Document(Base, TimestampMixin):
    """Метаданные документа. Новые файлы хранятся в томе uploads по app/type;
    документы синтетического seed могут не иметь содержимого."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(255))

    application = relationship("Application", back_populates="documents")
