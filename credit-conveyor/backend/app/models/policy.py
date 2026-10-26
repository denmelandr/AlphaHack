from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin


class PolicyVersion(Base, TimestampMixin):
    """Версионируемая кредитная политика (policy-as-code).

    body — разобранные правила (из YAML), yaml_text — исходный текст для
    редактора консоли банка. Активна ровно одна версия (active=True)."""

    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    body: Mapped[dict] = mapped_column(JSONB, default=dict)
    yaml_text: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(128), default="system")


class PolicyAudit(Base, TimestampMixin):
    """Аудит изменений кредитной политики: кто и когда создал/активировал версию."""

    __tablename__ = "policy_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))  # created / activated
    actor: Mapped[str] = mapped_column(String(128))
