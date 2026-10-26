from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    kind: Mapped[str] = mapped_column(String(32), default="working_capital")
    min_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    max_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    min_term: Mapped[int] = mapped_column(Integer)
    max_term: Mapped[int] = mapped_column(Integer)
    base_rate: Mapped[float] = mapped_column(Numeric(5, 2))
