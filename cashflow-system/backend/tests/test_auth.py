"""Autentifikatsiya: parol siyosati, cheklov, va yetim kompaniya xatosi."""
import uuid


def test_register_and_login(client):
    email = f"a_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/register", json={
        "company_name": "Kompaniya", "email": email, "password": "YaxshiParol123",
    })
    assert r.status_code == 200
    assert r.json()["access_token"]

    r = client.post("/api/auth/login", json={"email": email, "password": "YaxshiParol123"})
    assert r.status_code == 200


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={
        "company_name": "K", "email": "short@example.com", "password": "qisqa",
    })
    assert r.status_code == 400


def test_common_password_rejected(client):
    r = client.post("/api/auth/register", json={
        "company_name": "K", "email": "common@example.com", "password": "password123",
    })
    assert r.status_code == 400


def test_duplicate_email_leaves_no_orphan_company(client, db):
    """
    Regressiya testi: ilgari kompaniya alohida commit qilinardi, shuning uchun
    takroriy email urinishida bazada egasiz kompaniya qolib ketardi.
    """
    from app import models

    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/auth/register", json={
        "company_name": "Birinchi", "email": email, "password": "YaxshiParol123",
    })
    before = db.query(models.Company).count()

    r = client.post("/api/auth/register", json={
        "company_name": "Ikkinchi", "email": email, "password": "YaxshiParol123",
    })
    assert r.status_code == 400

    db.expire_all()
    assert db.query(models.Company).count() == before, "egasiz kompaniya yaratildi"


def test_login_lockout_after_repeated_failures(client, account):
    for _ in range(5):
        r = client.post("/api/auth/login",
                        json={"email": account["email"], "password": "NOTOGRI"})
        assert r.status_code == 401

    r = client.post("/api/auth/login",
                    json={"email": account["email"], "password": "NOTOGRI"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers

    # To'g'ri parol ham blok tugagunicha o'tmaydi
    r = client.post("/api/auth/login",
                    json={"email": account["email"], "password": account["password"]})
    assert r.status_code == 429


def test_successful_login_resets_attempt_counter(client, account):
    for _ in range(3):
        client.post("/api/auth/login", json={"email": account["email"], "password": "X"})

    r = client.post("/api/auth/login",
                    json={"email": account["email"], "password": account["password"]})
    assert r.status_code == 200

    # Hisoblagich nolga tushgani uchun yana 5 ta urinishga joy bor
    for _ in range(4):
        r = client.post("/api/auth/login", json={"email": account["email"], "password": "X"})
        assert r.status_code == 401


def test_error_message_language(client, account):
    r = client.post("/api/auth/login",
                    json={"email": account["email"], "password": "NOTOGRI"},
                    headers={"Accept-Language": "ru"})
    assert r.status_code == 401
    assert "Неверный" in r.json()["detail"]

    r = client.post("/api/auth/login",
                    json={"email": account["email"], "password": "NOTOGRI"},
                    headers={"Accept-Language": "en"})
    assert "Incorrect" in r.json()["detail"]


def test_protected_endpoint_requires_token(client):
    assert client.get("/api/transactions").status_code in (401, 403)
