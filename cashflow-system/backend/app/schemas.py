from datetime import date, datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr


# ---------- Auth ----------
class UserRegister(BaseModel):
    company_name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class MeOut(BaseModel):
    id: str
    email: str
    role: str
    company_name: str

    class Config:
        from_attributes = True


# ---------- Bank accounts ----------
class BankAccountCreate(BaseModel):
    bank_name: str
    account_number: str
    currency: str = "UZS"
    # Haqiqiy bank qoldig'i va u qaysi kun boshiga tegishli.
    # Prognozda likvidlikni hisoblash uchun kerak.
    opening_balance: Optional[float] = None
    opening_balance_date: Optional[date] = None


class BankAccountUpdate(BaseModel):
    opening_balance: Optional[float] = None
    opening_balance_date: Optional[date] = None


class BankAccountOut(BaseModel):
    id: str
    bank_name: str
    account_number: str
    currency: str
    opening_balance: Optional[float] = None
    opening_balance_date: Optional[date] = None

    class Config:
        from_attributes = True


# ---------- Categories ----------
class CategoryOut(BaseModel):
    id: str
    name: str
    type: str
    transaction_count: int = 0
    is_system: bool = False      # tizim kategoriyasi — tahrirlab bo'lmaydi

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str
    type: Literal["income", "expense"] = "expense"


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[Literal["income", "expense"]] = None


# ---------- Import ----------
class ImportBatchOut(BaseModel):
    id: str
    file_name: str
    period_date: date
    row_count: int
    status: str

    class Config:
        from_attributes = True


class ImportBatchListItem(BaseModel):
    id: str
    file_name: str
    period_date: date
    row_count: int
    status: str
    uploaded_at: Optional[datetime]
    bank_name: str
    account_number: str
    transaction_count: int
    cash_in: float
    cash_out: float


class ImportDeleteResult(BaseModel):
    deleted_batch_id: str
    deleted_transactions: int
    period_date: date


# ---------- Transactions ----------
class TransactionOut(BaseModel):
    id: str
    date: date
    direction: str
    amount: float
    currency: str
    counterparty: str
    raw_description: Optional[str]
    category_id: Optional[str]
    category_name: Optional[str] = None
    category_source: Optional[str]
    confidence_score: Optional[float]
    review_status: str

    class Config:
        from_attributes = True


class TransactionUpdate(BaseModel):
    category_id: str


class TransactionPage(BaseModel):
    items: List[TransactionOut]
    total: int
    limit: int
    offset: int
    pending_total: int          # butun kompaniya bo'yicha tasdiqlanmaganlar soni


class BulkConfirmRequest(BaseModel):
    transaction_ids: Optional[List[str]] = None   # bo'sh bo'lsa — filtrga tushgan hammasi
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    category_id: Optional[str] = None
    search: Optional[str] = None


class BulkConfirmResult(BaseModel):
    confirmed: int


class BulkCategorizeRequest(BaseModel):
    category_id: str
    # Berilmasa — filtrga tushgan barcha operatsiyalar (sahifadan tashqari ham)
    transaction_ids: Optional[List[str]] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    review_status: Optional[str] = None
    search: Optional[str] = None


class BulkCategorizeResult(BaseModel):
    updated: int
    rules_created: int      # kelajakdagi importlar uchun o'rganilgan qoidalar
    category_name: str


class RecategorizeResult(BaseModel):
    updated: int          # kategoriyasi o'zgargan operatsiyalar
    skipped_manual: int   # qo'lda tuzatilgani uchun tegilmaganlar
    unresolved: int       # provodka bo'yicha aniqlab bo'lmadi


# ---------- Dashboard ----------
class DashboardSummary(BaseModel):
    cash_in: float
    cash_out: float
    net_cash_flow: float
    period_start: Optional[date]
    period_end: Optional[date]


class CategoryBreakdownItem(BaseModel):
    category_name: str
    direction: str
    amount: float


class CounterpartyItem(BaseModel):
    counterparty: str
    amount: float


# ---------- Cash flow tuzilmasi (CFO) ----------
class StructureGroup(BaseModel):
    group_key: str        # barqaror identifikator — interfeys shu bo'yicha tarjima qiladi
    group: str            # sukut bo'yicha (o'zbekcha) nom
    amount: float
    share: float          # shu qatlam ichidagi ulush, 0-1
    transaction_count: int


class StructureLayer(BaseModel):
    flow_type: str        # operating | investing | financing | internal
    cash_in: float
    cash_out: float
    net: float
    inflow_groups: List[StructureGroup]
    outflow_groups: List[StructureGroup]


class CashFlowStructure(BaseModel):
    period_start: Optional[date]
    period_end: Optional[date]
    currency: Optional[str]              # hisobot shu valyuta ichida yig'ilgan
    available_currencies: List[str]      # kompaniyada mavjud valyutalar
    # Ichki ko'chirmalar chiqarib tashlangan haqiqiy ko'rsatkichlar
    operating_in: float
    operating_out: float
    operating_net: float
    investing_net: float
    financing_net: float
    net_change: float
    internal_volume: float
    layers: List[StructureLayer]


# ---------- Konsentratsiya va risk ----------
class ConcentrationItem(BaseModel):
    name: str
    amount: float
    share: float          # umumiy chiqim/kirimdagi ulushi, 0-1


class LargePayment(BaseModel):
    date: date
    counterparty: str
    amount: float
    category_name: Optional[str]


class ConcentrationOut(BaseModel):
    direction: str                 # "out" | "in"
    currency: Optional[str]
    total: float
    counterparty_count: int
    top1_share: float
    top3_share: float
    top10_share: float
    # Necha kontragent umumiy summaning 80% ini tashkil qiladi
    counterparties_for_80pct: int
    top_counterparties: List[ConcentrationItem]
    largest_payments: List[LargePayment]


# ---------- Davrlarni taqqoslash ----------
class PeriodPoint(BaseModel):
    period: date
    operating_in: float
    operating_out: float
    operating_net: float
    transaction_count: int


class PeriodComparison(BaseModel):
    currency: Optional[str]
    periods: List[PeriodPoint]     # eng eskisidan yangisiga
    current: Optional[PeriodPoint]
    previous: Optional[PeriodPoint]
    # O'zgarish foizi (previous bo'lmasa None)
    change_in: Optional[float]
    change_out: Optional[float]
    change_net: Optional[float]


# ---------- Forecast ----------
class ForecastItem(BaseModel):
    forecast_week_start: date
    predicted_cash_in: float
    predicted_cash_out: float
    predicted_balance: float        # markaziy stsenariy (P50)
    balance_p10: float              # pessimistik (10% ehtimol shundan past)
    balance_p90: float              # optimistik


class RecurringFlow(BaseModel):
    counterparty: str
    day_share: float                # necha ulush kunda uchraydi, 0-1
    median_amount: float
    days_seen: int


class ForecastResponse(BaseModel):
    items: List[ForecastItem]
    sufficient: bool                # tarix yetarlimi — yo'q bo'lsa items bo'sh
    business_days_of_history: int
    min_days_required: int
    currency: Optional[str]

    # Model parametrlari — auditga ochiq bo'lishi kerak
    avg_daily_in: float
    avg_daily_out: float
    weekday_factors: dict           # "0"=dushanba … "4"=juma
    collections_factor: float       # stsenariy tutqichi

    # Likvidlik
    opening_balance: Optional[float]
    has_opening_balance: bool
    minimum_balance: Optional[float]
    minimum_balance_date: Optional[date]

    # Ishonchlilik
    accuracy_mape: Optional[float]  # backtest xatosi, 0.15 = 15%
    history_start: Optional[date]
    history_end: Optional[date]

    recurring_inflows: List[RecurringFlow]
    recurring_outflows: List[RecurringFlow]
