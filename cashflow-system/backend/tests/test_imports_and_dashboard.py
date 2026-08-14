"""
Import, valyuta ajratish, ko'p ijarachilik izolyatsiyasi va dashboard hisobi.
Bu yerdagi testlar bugun topilgan xatolarning qaytmasligini kafolatlaydi.
"""
import io
import uuid

import pandas as pd
import pytest


def make_excel(rows) -> bytes:
    """1C eksport formatidagi minimal Excel fayl."""
    df = pd.DataFrame(rows, columns=[
        "Вид движения", "Кор. счет", "Аналитика", "Приход", "Расход", "Детали платежа",
    ])
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    return buffer.getvalue()


SAMPLE = [
    ["", "6310", "Mijoz A", 1000, None, "tushum"],        # asosiy tushum
    ["", "4310", "Taminotchi B", None, 600, "tovar"],      # asosiy xarajat
    ["", "6973", "Bank", None, 200, "ish haqi"],           # ish haqi
    ["", "5110", "O'z hisobi", 5000, None, "ko'chirma"],   # ICHKI — hisobga kirmasligi kerak
    ["", "7810", "Bank", 3000, None, "kredit"],            # moliyaviy
]


def upload(client, headers, account_id, period, rows=SAMPLE):
    return client.post(
        "/api/imports",
        headers=headers,
        data={"bank_account_id": account_id, "period_date": period},
        files={"file": ("test.xlsx", make_excel(rows),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_import_creates_transactions(client, account, bank_account):
    r = upload(client, account["headers"], bank_account["id"], "2026-01-05")
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 5


def test_duplicate_period_rejected(client, account, bank_account):
    """Bir hisobga bir sana uchun ikkinchi marta yuklab bo'lmaydi."""
    assert upload(client, account["headers"], bank_account["id"], "2026-01-05").status_code == 200
    second = upload(client, account["headers"], bank_account["id"], "2026-01-05")
    assert second.status_code == 409

    # Boshqa sana bloklanmaydi
    assert upload(client, account["headers"], bank_account["id"], "2026-01-06").status_code == 200


def test_deleted_period_can_be_reuploaded(client, account, bank_account):
    first = upload(client, account["headers"], bank_account["id"], "2026-01-05")
    batch_id = first.json()["id"]

    deleted = client.delete(f"/api/imports/{batch_id}", headers=account["headers"])
    assert deleted.status_code == 200
    assert deleted.json()["deleted_transactions"] == 5

    assert upload(client, account["headers"], bank_account["id"], "2026-01-05").status_code == 200


def test_internal_transfers_excluded_from_operating(client, account, bank_account):
    """
    Eng muhim hisob qoidasi: 5110 (o'z hisobi) va 7810 (kredit) tushumga kirmaydi.
    Aks holda Cash In sun'iy ravishda oshib ketadi.
    """
    upload(client, account["headers"], bank_account["id"], "2026-01-05")

    r = client.get("/api/dashboard/structure", headers=account["headers"])
    data = r.json()

    assert data["operating_in"] == 1000        # faqat 6310 — 5000 va 3000 kirmaydi
    assert data["operating_out"] == 800        # 600 + 200
    assert data["operating_net"] == 200
    assert data["financing_net"] == 3000       # 7810 alohida qatlamda
    assert data["internal_volume"] == 5000     # 5110 alohida ko'rsatiladi


def test_expense_structure_groups(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05")
    data = client.get("/api/dashboard/structure", headers=account["headers"]).json()

    operating = next(l for l in data["layers"] if l["flow_type"] == "operating")
    groups = {g["group_key"]: g["amount"] for g in operating["outflow_groups"]}
    assert groups["op.suppliers"] == 600
    assert groups["op.payroll"] == 200

    shares = sum(g["share"] for g in operating["outflow_groups"])
    assert abs(shares - 1.0) < 1e-9, "ulushlar yig'indisi 100% bo'lishi kerak"


def test_currencies_are_never_summed(client, account):
    """UZS va USD hisoblari bitta raqamga qo'shilib ketmasligi kerak."""
    uzs = client.post("/api/bank-accounts", headers=account["headers"], json={
        "bank_name": "B1", "account_number": "111", "currency": "UZS"}).json()
    usd = client.post("/api/bank-accounts", headers=account["headers"], json={
        "bank_name": "B2", "account_number": "222", "currency": "USD"}).json()

    upload(client, account["headers"], uzs["id"], "2026-01-05")
    upload(client, account["headers"], usd["id"], "2026-01-05")

    uzs_data = client.get("/api/dashboard/structure?currency=UZS",
                          headers=account["headers"]).json()
    usd_data = client.get("/api/dashboard/structure?currency=USD",
                          headers=account["headers"]).json()

    assert uzs_data["operating_in"] == 1000
    assert usd_data["operating_in"] == 1000
    assert set(uzs_data["available_currencies"]) == {"UZS", "USD"}


def test_date_filter(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05")
    upload(client, account["headers"], bank_account["id"], "2026-02-05")

    both = client.get("/api/dashboard/structure", headers=account["headers"]).json()
    assert both["operating_in"] == 2000

    only_jan = client.get(
        "/api/dashboard/structure?date_from=2026-01-01&date_to=2026-01-31",
        headers=account["headers"]).json()
    assert only_jan["operating_in"] == 1000

    empty = client.get(
        "/api/dashboard/structure?date_from=2026-06-01&date_to=2026-06-30",
        headers=account["headers"]).json()
    assert empty["period_start"] is None


def test_counterparties_exclude_internal_and_loans(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05")

    inflow = client.get("/api/dashboard/top-counterparties?direction=in",
                        headers=account["headers"]).json()
    names = [c["counterparty"] for c in inflow]
    assert "Mijoz A" in names
    assert "O'z hisobi" not in names, "ichki ko'chirma kontragent emas"
    assert "Bank" not in names, "kredit bergan bank mijoz sifatida ko'rinmasligi kerak"


def test_company_data_is_isolated(client, account, bank_account):
    """Bir kompaniya boshqasining ma'lumotini ko'rmasligi kerak."""
    upload(client, account["headers"], bank_account["id"], "2026-01-05")

    other_email = f"other_{uuid.uuid4().hex[:8]}@example.com"
    other = client.post("/api/auth/register", json={
        "company_name": "Boshqa", "email": other_email, "password": "YaxshiParol123",
    }).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    data = client.get("/api/dashboard/structure", headers=other_headers).json()
    assert data["operating_in"] == 0
    assert data["period_start"] is None

    page = client.get("/api/transactions", headers=other_headers).json()
    assert page["total"] == 0


def test_cannot_delete_another_companys_import(client, account, bank_account):
    batch_id = upload(client, account["headers"], bank_account["id"], "2026-01-05").json()["id"]

    other_email = f"other_{uuid.uuid4().hex[:8]}@example.com"
    other = client.post("/api/auth/register", json={
        "company_name": "Boshqa", "email": other_email, "password": "YaxshiParol123",
    }).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    assert client.delete(f"/api/imports/{batch_id}", headers=other_headers).status_code == 404


def test_invalid_file_returns_clear_error(client, account, bank_account):
    r = client.post(
        "/api/imports",
        headers={**account["headers"], "Accept-Language": "en"},
        data={"bank_account_id": bank_account["id"], "period_date": "2026-01-05"},
        files={"file": ("bad.xlsx", b"not an excel file", "application/vnd.ms-excel")},
    )
    assert r.status_code == 400
    assert "read" in r.json()["detail"].lower()


def test_missing_columns_error(client, account, bank_account):
    df = pd.DataFrame([[1, 2]], columns=["Noto'g'ri", "Ustunlar"])
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)

    r = client.post(
        "/api/imports",
        headers=account["headers"],
        data={"bank_account_id": bank_account["id"], "period_date": "2026-01-05"},
        files={"file": ("x.xlsx", buffer.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 400
    assert "Кор. счет" in r.json()["detail"]
