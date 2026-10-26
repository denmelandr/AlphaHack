from datetime import date

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    inn: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    ogrn: Mapped[str] = mapped_column(String(15))
    name: Mapped[str] = mapped_column(String(255))
    okved: Mapped[str] = mapped_column(String(16))
    registered_at: Mapped[date] = mapped_column(Date)
    tax_regime: Mapped[str] = mapped_column(String(32), default="УСН")
    annual_revenue: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    employees: Mapped[int] = mapped_column(Integer, default=1)
