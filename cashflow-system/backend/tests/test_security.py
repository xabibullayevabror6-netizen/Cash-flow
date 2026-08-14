"""Parol o'zgartirish, token bekor qilish va cheklovlar."""
import uuid


def test_change_password_revokes_old_tokens(client, account):
    """
    Eng muhim xavfsizlik qoidasi: parol o'zgartirilgach, eski token
    darhol kuchini yo'qotishi kerak. Aks holda o'g'irlangan token
    24 soat davomida ishlayverardi.
    """
    old_headers = account["headers"]
    assert client.get("/api/auth/me", headers=old_headers).status_code == 200

    r = client.post("/api/auth/change-password", headers=old_headers, json={
        "current_password": account["password"],
        "new_password": "MutlaqoYangi9876",
    })
    assert r.status_code == 200
    new_token = r.json()["access_token"]

    # Eski token endi qabul qilinmaydi
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401
    # Yangisi ishlaydi
    assert client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}
    ).status_code == 200


def test_change_password_updates_login(client, account):
    client.post("/api/auth/change-password", headers=account["headers"], json={
        "current_password": account["password"],
        "new_password": "MutlaqoYangi9876",
    })

    old = client.post("/api/auth/login",
                      json={"email": account["email"], "password": account["password"]})
    assert old.status_code == 401

    new = client.post("/api/auth/login",
                      json={"email": account["email"], "password": "MutlaqoYangi9876"})
    assert new.status_code == 200


def test_change_password_requires_correct_current(client, account):
    r = client.post("/api/auth/change-password", headers=account["headers"], json={
        "current_password": "NOTOGRI",
        "new_password": "MutlaqoYangi9876",
    })
    assert r.status_code == 400
    # Parol o'zgarmagani uchun eski token hali ham ishlaydi
    assert client.get("/api/auth/me", headers=account["headers"]).status_code == 200


def test_change_password_rejects_weak_password(client, account):
    r = client.post("/api/auth/change-password", headers=account["headers"], json={
        "current_password": account["password"],
        "new_password": "qisqa",
    })
    assert r.status_code == 400


def test_change_password_rejects_same_password(client, account):
    r = client.post("/api/auth/change-password", headers=account["headers"], json={
        "current_password": account["password"],
        "new_password": account["password"],
    })
    assert r.status_code == 400


def test_change_password_requires_auth(client):
    r = client.post("/api/auth/change-password", json={
        "current_password": "x", "new_password": "YangiParol12345",
    })
    assert r.status_code in (401, 403)


def test_tampered_token_rejected(client, account):
    """Imzosi buzilgan token qabul qilinmasligi kerak."""
    token = account["headers"]["Authorization"].split()[1]
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


def test_me_returns_own_company_only(client, account):
    r = client.get("/api/auth/me", headers=account["headers"])
    assert r.status_code == 200
    assert r.json()["email"] == account["email"]
    assert r.json()["company_name"] == "Test Kompaniya"


def test_registration_is_rate_limited(client):
    """Bitta IP dan cheksiz akkaunt ochib bo'lmaydi."""
    from app import security
    security.reset_all()

    codes = []
    for _ in range(security.MAX_REGISTRATIONS + 2):
        r = client.post("/api/auth/register", json={
            "company_name": "K",
            "email": f"rl_{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestParol12345",
        })
        codes.append(r.status_code)

    assert codes.count(200) == security.MAX_REGISTRATIONS
    assert 429 in codes
