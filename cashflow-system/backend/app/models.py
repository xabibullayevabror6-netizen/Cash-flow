import uuid
import enum
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Numeric, Date, DateTime, ForeignKey, Integer,
    Enum as SAEnum, Float, Text, UniqueConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class TariffPlan(str, enum.Enum):
    start = "start"
    pro = "pro"
    enterprise = "enterprise"


class UserRole(str, enum.Enum):
    admin = "admin"
    accountant = "accountant"
    viewer = "viewer"


class Direction(str, enum.Enum):
    in_ = "in"
    out = "out"


class CategorySource(str, enum.Enum):
    rule = "rule"          # kontragent bo'yicha o'rganilgan qoida
    provodka = "provodka"  # Кор. счет kodidan aniqlangan
    ai = "ai"
    manual = "manual"      # buxgalter qo'lda tuzatgan


class ReviewStatus(str, enum.Enum):
    pending_review = "pending_review"
    confirmed = "confirmed"


class ImportStatus(str, enum.Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class CategoryType(str, enum.Enum):
    income = "income"
    expense = "expense"


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    tariff_plan = Column(SAEnum(TariffPlan), default=TariffPlan.start)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="company")
    bank_accounts = relationship("BankAccount", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.accountant)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Token bekor qilish uchun. Har bir JWT ichida shu raqam saqlanadi;
    # parol o'zgartirilganda raqam oshiriladi va eski tokenlar darhol
    # ishlamay qoladi. Aks holda o'g'irlangan token 24 soat amal qilardi.
    token_version = Column(Integer, nullable=False, server_default="0", default=0)

    company = relationship("Company", back_populates="users")


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    bank_name = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    currency = Column(String(3), default="UZS")

    # Haqiqiy bank qoldig'i. Prognoz busiz likvidlikni ko'rsata olmaydi:
    # importlardagi kirim-chiqim yig'indisi qoldiq EMAS, u faqat oqim.
    # opening_balance_date — shu qoldiq qaysi kun boshiga tegishli.
    opening_balance = Column(Numeric(18, 2), nullable=True)
    opening_balance_date = Column(Date, nullable=True)

    company = relationship("Company", back_populates="bank_accounts")


class Branch(Base):
    __tablename__ = "branches"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        # Bir bank hisobiga bir sana uchun faqat bitta import.
        # Muvaffaqiyatsiz (failed) importlar cheklovga kirmaydi — qayta yuklash mumkin.
        Index(
            "uq_import_batch_account_period",
            "bank_account_id",
            "period_date",
            unique=True,
            postgresql_where=text("status != 'failed'"),
        ),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    bank_account_id = Column(UUID(as_uuid=False), ForeignKey("bank_accounts.id"), nullable=False)
    file_name = Column(String, nullable=False)
    period_date = Column(Date, nullable=False)  # foydalanuvchi qo'lda kiritadi
    uploaded_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    row_count = Column(Integer, default=0)
    status = Column(SAEnum(ImportStatus), default=ImportStatus.processing)

    transactions = relationship("Transaction", back_populates="import_batch")


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=True)
    name = Column(String, nullable=False)
    type = Column(SAEnum(CategoryType), nullable=False)
    parent_category_id = Column(UUID(as_uuid=False), ForeignKey("categories.id"), nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False, index=True)
    import_batch_id = Column(UUID(as_uuid=False), ForeignKey("import_batches.id"), nullable=False)
    bank_account_id = Column(UUID(as_uuid=False), ForeignKey("bank_accounts.id"), nullable=False)

    date = Column(Date, nullable=False, index=True)
    direction = Column(SAEnum(Direction), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    # Valyuta import paytida bank hisobidan ko'chiriladi. Tranzaksiyada saqlanadi,
    # chunki hisobot har doim bitta valyuta ichida yig'ilishi kerak — UZS va USD
    # summasini qo'shib yuborish jimgina noto'g'ri natija beradi.
    currency = Column(String(3), nullable=False, server_default="UZS", index=True)

    counterparty = Column(String, nullable=False)          # Аналитика
    corr_account_code = Column(String, nullable=True)       # Кор. счет — faqat referens
    raw_description = Column(Text, nullable=True)           # Детали платежа

    branch_id = Column(UUID(as_uuid=False), ForeignKey("branches.id"), nullable=True)
    category_id = Column(UUID(as_uuid=False), ForeignKey("categories.id"), nullable=True)
    category_source = Column(SAEnum(CategorySource), nullable=True)
    confidence_score = Column(Float, nullable=True)
    review_status = Column(SAEnum(ReviewStatus), default=ReviewStatus.pending_review, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    import_batch = relationship("ImportBatch", back_populates="transactions")
    category = relationship("Category")


class CategoryRule(Base):
    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("company_id", "counterparty_pattern", name="uq_company_counterparty"),)

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    counterparty_pattern = Column(String, nullable=False)  # Аналитика nomi bo'yicha (koddan mustaqil)
    category_id = Column(UUID(as_uuid=False), ForeignKey("categories.id"), nullable=False)
    match_count = Column(Integer, default=1)
    last_used_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category")


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False)
    forecast_week_start = Column(Date, nullable=False)
    predicted_cash_in = Column(Numeric(18, 2), default=0)
    predicted_cash_out = Column(Numeric(18, 2), default=0)
    predicted_balance = Column(Numeric(18, 2), default=0)
    actual_balance = Column(Numeric(18, 2), nullable=True)
    model_version = Column(String, default="moving_average_v1")
    generated_at = Column(DateTime, default=datetime.utcnow)
