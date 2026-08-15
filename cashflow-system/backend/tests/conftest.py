"""
Test infratuzilmasi.

Har bir test alohida, toza PostgreSQL bazasida ishlaydi — ishlab turgan
ma'lumotga umuman tegilmaydi. Baza nomi test seansi uchun tasodifiy
generatsiya qilinadi va oxirida o'chiriladi.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Ilova import qilinishidan OLDIN sozlamalar berilishi kerak —
# app.config modul yuklanganda o'qiladi.
#
# Ulanish ma'lumotlari muhitdan olinadi, kodda saqlanmaydi: parol
# o'zgartirilganda testlarni tahrirlash kerak bo'lmasin va sir repoga tushmasin.
_APP_URL = os.environ.get("DATABASE_URL")
if not _APP_URL:
    raise RuntimeError(
        "DATABASE_URL berilmagan. Testlar backend konteynerida ishga tushiriladi:\n"
        "    docker compose exec backend pytest"
    )

ADMIN_URL = os.environ.get("TEST_ADMIN_DATABASE_URL") or (_APP_URL.rsplit("/", 1)[0] + "/postgres")
TEST_DB = f"test_{uuid.uuid4().hex[:12]}"
TEST_URL = ADMIN_URL.rsplit("/", 1)[0] + "/" + TEST_DB

os.environ["DATABASE_URL"] = TEST_URL
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-that-is-long-enough-1234567890"
os.environ["ANTHROPIC_API_KEY"] = ""          # AI o'chiq — testlar tashqi xizmatga bog'lanmaydi
os.environ["ENVIRONMENT"] = "development"


@pytest.fixture(scope="session", autouse=True)
def _database():
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}"'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    admin.dispose()

    from app.database import Base
    from app import models  # noqa: F401 — modellarni ro'yxatga oladi

    engine = create_engine(TEST_URL)
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    yield

    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{TEST_DB}' AND pid <> pg_backend_pid()"
        ))
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}"'))
    admin.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    """
    Har bir testdan oldin jadvallarni tozalaydi — testlar bir-biriga ta'sir qilmaydi.
    So'ng tizim kategoriyalari qayta ekiladi, chunki ilova ular mavjud deb ishlaydi
    (xuddi haqiqiy o'rnatishda `python seed.py` bajarilgani kabi).
    """
    from app.database import engine, SessionLocal
    from app.default_categories import seed_categories

    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE transactions, import_batches, category_rules, forecasts, "
            "bank_accounts, branches, categories, users, companies RESTART IDENTITY CASCADE"
        ))

    session = SessionLocal()
    try:
        seed_categories(session)
    finally:
        session.close()

    from app import security
    security.reset_all()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    from app.database import engine
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def account(client):
    """Ro'yxatdan o'tgan kompaniya + tayyor Authorization sarlavhasi."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestParol12345"
    response = client.post("/api/auth/register", json={
        "company_name": "Test Kompaniya",
        "email": email,
        "password": password,
    })
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {
        "email": email,
        "password": password,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def bank_account(client, account):
    response = client.post("/api/bank-accounts", headers=account["headers"], json={
        "bank_name": "Test Bank",
        "account_number": "20208000000000000001",
        "currency": "UZS",
    })
    assert response.status_code in (200, 201), response.text
    return response.json()
