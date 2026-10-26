from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr, Field
from datetime import date
import secrets
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import create_access_token, verify_password, hash_password
from app.models.user import User, UserRole
from app.models.company import Company
from app.core.config import settings
from app.schemas.schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if user is None or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=255)
    account_type: str = "client"
    invitation: str = ""
    company_name: str | None = None
    inn: str | None = None


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Такой email уже зарегистрирован")
    company = None
    role = UserRole.owner
    if data.account_type == "bank":
        if not settings.bank_invitation_code or not secrets.compare_digest(data.invitation, settings.bank_invitation_code):
            raise HTTPException(403, "Приглашение сотрудника не подтверждено сервером")
        role = UserRole.underwriter
    elif data.account_type == "client":
        from app.services.pipeline import inn_is_valid
        if not data.company_name or not data.company_name.strip() or not inn_is_valid(data.inn or ""):
            raise HTTPException(422, "Укажите название бизнеса и ИНН из 10 или 12 цифр")
        if db.scalar(select(Company).where(Company.inn == data.inn)):
            raise HTTPException(409, "Компания уже зарегистрирована. Доступ к ней выдаёт администратор")
        company = Company(inn=data.inn, name=data.company_name.strip(), ogrn="", okved="", registered_at=date.today(), tax_regime="УСН", annual_revenue=0, employees=1)
        db.add(company)
        db.flush()
    else:
        raise HTTPException(422, "Неизвестный тип аккаунта")
    user = User(email=email, full_name=data.full_name.strip(), hashed_password=hash_password(data.password), role=role, company_id=company.id if company else None)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email или компания уже зарегистрированы")
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(subject=str(user.id), role=user.role.value))


@router.get("/company")
def company(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(Company, user.company_id) if user.company_id else None
    if item is None:
        return None
    return {"id": item.id, "name": item.name, "inn": item.inn, "okved": item.okved, "tax_regime": item.tax_regime, "annual_revenue": float(item.annual_revenue), "employees": item.employees}
