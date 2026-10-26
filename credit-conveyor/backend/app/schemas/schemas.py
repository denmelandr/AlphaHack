from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.application import ApplicationState
from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    inn: str
    name: str
    okved: str
    tax_regime: str
    annual_revenue: float
    employees: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    company_id: int | None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str
    kind: str
    min_amount: float
    max_amount: float
    min_term: int
    max_term: int
    base_rate: float


class ApplicationCreate(BaseModel):
    product_id: int
    amount: float = Field(gt=0, le=50000000, allow_inf_nan=False)
    term_months: int = Field(ge=1, le=120)
    purpose: str = ""
    form_data: dict = {}


class ApplicationUpdate(BaseModel):
    product_id: int | None = None
    amount: float | None = Field(default=None, gt=0, le=50000000, allow_inf_nan=False)
    term_months: int | None = Field(default=None, ge=1, le=120)
    purpose: str | None = None
    form_data: dict | None = None


class DocumentItem(BaseModel):
    type: str
    name: str
    how: str
    uploaded: bool
    filename: str = ""
    has_file: bool = False


class DocumentUpload(BaseModel):
    doc_type: str
    filename: str


class ReadinessOut(BaseModel):
    fields_ok: bool
    docs_total: int
    docs_uploaded: int
    ready: bool
    missing: list[str]


class CalcRequest(BaseModel):
    amount: float = Field(gt=0, le=50000000, allow_inf_nan=False)
    annual_rate: float = Field(ge=0, le=100, allow_inf_nan=False)
    term_months: int = Field(ge=1, le=120)
    expected_extra_profit: float = Field(default=0, ge=0, le=1000000000, allow_inf_nan=False)
    avg_monthly_revenue: float = Field(default=0, ge=0, allow_inf_nan=False)


class CalcResponse(BaseModel):
    monthly_payment: float
    total_payment: float
    overpayment: float
    profit_vs_cost: float | None = None
    cashflow_warning: bool = False
    schedule: list[dict]


class RecommendRequest(BaseModel):
    answers: dict


class RecommendResponse(BaseModel):
    product_code: str
    product_id: int
    name: str
    rationale: str


class SimulateRequest(BaseModel):
    amount: float = Field(gt=0, le=50000000, allow_inf_nan=False)
    term_months: int = Field(ge=1, le=120)
    collateral_offered: bool = False
    guarantor_offered: bool = False


class SimulateResponse(BaseModel):
    score: int
    risk_band: str
    pd_estimate: float
    approval_probability: int
    outcome: str
    reasons: list[str]
    offer: dict | None = None
    factors: list[dict]


class ReviewRequest(BaseModel):
    comment: str = ""


class PolicyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version: int
    name: str
    active: bool
    created_by: str
    created_at: datetime


class PolicyDetailOut(PolicyVersionOut):
    yaml_text: str = Field(max_length=65536)
    body: dict


class PolicyCreateRequest(BaseModel):
    name: str
    yaml_text: str = Field(max_length=65536)


class PolicySimulateRequest(BaseModel):
    yaml_text: str = Field(max_length=65536)
    limit: int = Field(default=50, ge=1, le=500)


class PolicyAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version: int
    action: str
    actor: str
    created_at: datetime


class CopilotOut(BaseModel):
    summary: str
    anomalies: list[str]
    justification: str
    source: str


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    principal: float
    rate: float
    term_months: int = Field(ge=1, le=120)
    monthly_payment: float
    outstanding_balance: float
    next_payment_date: date
    status: str
    servicing_log: list
    autopilot: dict = {}


class ServicingOut(BaseModel):
    account: AccountOut
    signals: list[dict]
    actions: list[dict]
    radar: dict | None = None


class ServicingApply(BaseModel):
    action: str


class AutopilotConfig(BaseModel):
    enabled: bool = False
    max_bridge: float = Field(default=0, ge=0, le=1000000, allow_inf_nan=False)


class ForecastRequest(BaseModel):
    revenue_drop_pct: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)
    extra_expense: float = Field(default=0, ge=0, le=100000000, allow_inf_nan=False)


class CrossSellOut(BaseModel):
    tier: str
    tier_label: str
    discount_pct: int
    offers: list[dict]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event: str
    from_state: str
    to_state: str
    actor_id: int | None
    comment: str
    created_at: datetime


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    applicant_id: int
    company_name: str = ""
    company_inn: str = ""
    product_id: int
    amount: float = Field(gt=0, le=50000000, allow_inf_nan=False)
    term_months: int = Field(ge=1, le=120)
    purpose: str
    form_data: dict = {}
    state: ApplicationState
    created_at: datetime
    updated_at: datetime


class EnrichmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    profile: dict
    raw: dict
    created_at: datetime


class ScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    score: int
    risk_band: str
    pd_estimate: float
    factors: list[dict]
    created_at: datetime


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    outcome: str
    policy_version: int
    reasons: list[str]
    created_at: datetime


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amount: float = Field(gt=0, le=50000000, allow_inf_nan=False)
    term_months: int = Field(ge=1, le=120)
    rate: float
    monthly_payment: float
    total_payment: float
    overpayment: float
    collateral_required: bool
    is_counter: bool
    accepted: bool
    schedule: list[dict]


class ApplicationDetail(ApplicationOut):
    events: list[EventOut] = []
    available_events: list[str] = []
    enrichment: EnrichmentOut | None = None
    score: ScoreOut | None = None
    decision: DecisionOut | None = None
    offer: OfferOut | None = None


class TransitionRequest(BaseModel):
    event: str
    comment: str = ""
