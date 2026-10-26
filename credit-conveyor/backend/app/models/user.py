import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin


class UserRole(str, enum.Enum):
    # клиентские роли
    owner = "owner"
    director = "director"
    accountant = "accountant"
    finance = "finance"
    employee = "employee"
    # банковские роли
    underwriter = "underwriter"
    risk_admin = "risk_admin"
    # демо-роль: видит и умеет всё (и клиент, и банк) для сквозного показа
    demo = "demo"


CLIENT_ROLES = {
    UserRole.owner, UserRole.director, UserRole.accountant,
    UserRole.finance, UserRole.employee,
}
BANK_ROLES = {UserRole.underwriter, UserRole.risk_admin}


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.owner)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True
    )

    @property
    def acts_as_bank(self) -> bool:
        return self.role in BANK_ROLES or self.role == UserRole.demo

    @property
    def acts_as_client(self) -> bool:
        return self.role in CLIENT_ROLES or self.role == UserRole.demo

    # Сохраняем is_bank для видимости (демо видит все заявки, как банк)
    @property
    def is_bank(self) -> bool:
        return self.acts_as_bank
