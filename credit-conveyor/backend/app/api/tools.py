from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.product import Product
from app.schemas.schemas import (
    CalcRequest,
    CalcResponse,
    RecommendRequest,
    RecommendResponse,
)
from app.services import finance

router = APIRouter(tags=["tools"])


@router.post("/calc", response_model=CalcResponse)
def calc(data: CalcRequest) -> CalcResponse:
    """Калькулятор кредита с оценкой выгоды (из базовой продуктовой части)."""
    pay = finance.annuity_payment(data.amount, data.annual_rate, data.term_months)
    total = pay * data.term_months
    overpay = total - data.amount

    profit_vs_cost = None
    if data.expected_extra_profit:
        # сравнение ожидаемой доп-прибыли со стоимостью кредита (переплатой)
        profit_vs_cost = round(data.expected_extra_profit - overpay, 2)

    # предупреждение, если платёж превышает 40% прогнозируемой выручки
    cashflow_warning = bool(
        data.avg_monthly_revenue and pay > 0.4 * data.avg_monthly_revenue
    )

    return CalcResponse(
        monthly_payment=round(pay, 2),
        total_payment=round(total, 2),
        overpayment=round(overpay, 2),
        profit_vs_cost=profit_vs_cost,
        cashflow_warning=cashflow_warning,
        schedule=finance.build_schedule(data.amount, data.annual_rate, data.term_months),
    )


@router.post("/recommend", response_model=RecommendResponse)
def recommend(data: RecommendRequest, db: Session = Depends(get_db)) -> RecommendResponse:
    """Подбор продукта по короткому опросу (JTBD)."""
    a = data.answers
    goal = a.get("goal")  # oborotka | equipment | project | cashgap
    repay = a.get("repay")  # fixed | revenue

    if repay == "revenue":
        code = "revenue_based"
        why = "Погашение процентом с выручки удобно при неравномерных продажах."
    elif goal == "project" or goal == "equipment":
        code = "investment"
        why = "Крупные вложения в проект или оборудование — под длинный инвестиционный кредит."
    elif goal == "cashgap":
        code = "overdraft"
        why = "Для покрытия коротких кассовых разрывов подходит возобновляемый овердрафт."
    else:
        code = "working_capital"
        why = "Пополнение оборотных средств — базовый оборотный кредит."

    product = db.scalar(select(Product).where(Product.code == code))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Продукт не найден")
    return RecommendResponse(
        product_code=product.code,
        product_id=product.id,
        name=product.name,
        rationale=why,
    )
