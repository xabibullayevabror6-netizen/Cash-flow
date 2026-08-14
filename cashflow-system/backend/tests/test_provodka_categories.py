"""Provodka bo'yicha avtomatik kategoriyalash."""
import io

import pandas as pd
import pytest

from app.services.provodka_categories import category_for, HIGH, MEDIUM


def make_excel(rows):
    df = pd.DataFrame(rows, columns=[
        "Вид движения", "Кор. счет", "Аналитика", "Приход", "Расход", "Детали платежа",
    ])
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    return buffer.getvalue()


def upload(client, headers, account_id, period, rows):
    return client.post(
        "/api/imports", headers=headers,
        data={"bank_account_id": account_id, "period_date": period},
        files={"file": ("t.xlsx", make_excel(rows),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


# --- Sof funksiya darajasida ---

@pytest.mark.parametrize("code,direction,expected,confidence", [
    ("6310", "in", "Mijozlardan tushum", HIGH),
    ("6973", "out", "Ish haqi", HIGH),
    ("6710", "out", "Ish haqi", HIGH),
    ("6980", "out", "Ijara", HIGH),
    ("9422", "out", "Kommunal xizmatlar", HIGH),
    ("6410", "out", "Soliq", HIGH),
    ("5110", "in", "Hisoblar orasidagi ko'chirma", HIGH),
    ("5710", "in", "Hisoblar orasidagi ko'chirma", HIGH),
    ("7810", "in", "Kredit olish", HIGH),
    ("7810", "out", "Kredit to'lovi", HIGH),
    ("9610", "out", "Foiz to'lovlari", HIGH),
    ("0120", "out", "Asosiy vositalar", HIGH),
    # Yo'nalish aniq, tafsilot noaniq — past ishonch
    ("4310", "out", "Dori/tovar xaridi", MEDIUM),
    ("9430", "out", "Boshqa", MEDIUM),
])
def test_category_for_known_codes(code, direction, expected, confidence):
    result = category_for(code, direction)
    assert result is not None, f"{code}/{direction} aniqlanmadi"
    assert result[0] == expected
    assert result[1] == confidence


def test_unknown_code_returns_none():
    """Noaniq kod AI'ga qolishi kerak, taxmin qilinmasligi kerak."""
    assert category_for("4890", "out") is None
    assert category_for("9999", "in") is None
    assert category_for(None, "out") is None


def test_direction_changes_category():
    """Bir kod yo'nalishga qarab turli kategoriyaga tushadi."""
    assert category_for("7810", "in")[0] == "Kredit olish"
    assert category_for("7810", "out")[0] == "Kredit to'lovi"


# --- Import orqali (uchdan uchi) ---

ROWS = [
    ["", "6310", "Mijoz A", 1000, None, "tushum"],
    ["", "6973", "Bank", None, 500, "ish haqi"],
    ["", "6980", "Ijarachi", None, 300, "ijara"],
    ["", "5110", "O'z hisobi", 7000, None, "ko'chirma"],
    ["", "4310", "Taminotchi", None, 200, "tovar"],
    ["", "4890", "Noma'lum", None, 50, "boshqa"],
]


def test_import_categorises_by_provodka(client, account, bank_account):
    """AI kaliti yo'q bo'lsa ham provodka kategoriyani aniqlaydi."""
    assert upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS).status_code == 200

    page = client.get("/api/transactions?limit=50", headers=account["headers"]).json()
    by_counterparty = {i["counterparty"]: i for i in page["items"]}

    assert by_counterparty["Mijoz A"]["category_name"] == "Mijozlardan tushum"
    assert by_counterparty["Mijoz A"]["category_source"] == "provodka"
    assert by_counterparty["Mijoz A"]["review_status"] == "confirmed"

    assert by_counterparty["Bank"]["category_name"] == "Ish haqi"
    assert by_counterparty["Ijarachi"]["category_name"] == "Ijara"
    assert by_counterparty["O'z hisobi"]["category_name"] == "Hisoblar orasidagi ko'chirma"


def test_medium_confidence_goes_to_review(client, account, bank_account):
    """Noaniq kod kategoriya oladi, lekin tasdiqlashga yuboriladi."""
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)

    page = client.get("/api/transactions?search=Taminotchi", headers=account["headers"]).json()
    item = page["items"][0]
    assert item["category_name"] == "Dori/tovar xaridi"
    assert item["review_status"] == "pending_review", "past ishonch tasdiqlashni talab qiladi"


def test_recategorize_preserves_manual_corrections(client, account, bank_account):
    """
    Eng muhim qoida: buxgalterning qo'lda tuzatgani avtomatik qoidadan
    ustun turadi va qayta taqsimlashda o'zgarmaydi.
    """
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)

    page = client.get("/api/transactions?search=Mijoz A", headers=account["headers"]).json()
    transaction = page["items"][0]

    categories = client.get("/api/categories", headers=account["headers"]).json()
    reklama = next(c for c in categories if c["name"] == "Reklama")

    client.patch(f"/api/transactions/{transaction['id']}",
                 headers=account["headers"], json={"category_id": reklama["id"]})

    r = client.post("/api/transactions/recategorize", headers=account["headers"])
    assert r.status_code == 200
    assert r.json()["skipped_manual"] >= 1

    after = client.get("/api/transactions?search=Mijoz A", headers=account["headers"]).json()
    assert after["items"][0]["category_name"] == "Reklama", "qo'lda tuzatilgan kategoriya o'zgardi"
    assert after["items"][0]["category_source"] == "manual"


def test_recategorize_reports_unresolved(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)
    r = client.post("/api/transactions/recategorize", headers=account["headers"]).json()
    # 4890 — provodka bo'yicha aniqlab bo'lmaydi
    assert r["unresolved"] >= 1


def test_recategorize_requires_auth(client):
    assert client.post("/api/transactions/recategorize").status_code in (401, 403)


# --- Guruhli kategoriyalash ---

def test_bulk_categorize_selected(client, account, bank_account):
    """Belgilangan operatsiyalar bittada bir kategoriyaga o'tadi."""
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)

    page = client.get("/api/transactions?limit=50", headers=account["headers"]).json()
    ids = [i["id"] for i in page["items"][:3]]

    categories = client.get("/api/categories", headers=account["headers"]).json()
    target = next(c for c in categories if c["name"] == "Transport")

    r = client.post("/api/transactions/bulk-categorize", headers=account["headers"], json={
        "category_id": target["id"], "transaction_ids": ids,
    })
    assert r.status_code == 200
    assert r.json()["updated"] == 3
    assert r.json()["category_name"] == "Transport"

    after = client.get("/api/transactions?limit=50", headers=account["headers"]).json()
    changed = [i for i in after["items"] if i["id"] in ids]
    assert all(i["category_name"] == "Transport" for i in changed)
    assert all(i["category_source"] == "manual" for i in changed)
    assert all(i["review_status"] == "confirmed" for i in changed)


def test_bulk_categorize_creates_rules(client, account, bank_account):
    """
    Guruhli o'tkazish ham qoida yaratadi — keyingi importda o'sha
    kontragentlar avtomatik shu kategoriyaga tushishi kerak.
    """
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)

    page = client.get("/api/transactions?search=Taminotchi", headers=account["headers"]).json()
    categories = client.get("/api/categories", headers=account["headers"]).json()
    target = next(c for c in categories if c["name"] == "Reklama")

    r = client.post("/api/transactions/bulk-categorize", headers=account["headers"], json={
        "category_id": target["id"],
        "transaction_ids": [page["items"][0]["id"]],
    })
    assert r.json()["rules_created"] == 1

    upload(client, account["headers"], bank_account["id"], "2026-02-05", ROWS)
    later = client.get("/api/transactions?search=Taminotchi&date_from=2026-02-01",
                       headers=account["headers"]).json()
    assert later["items"][0]["category_name"] == "Reklama"
    assert later["items"][0]["category_source"] == "rule"


def test_bulk_categorize_all_matching_filter(client, account, bank_account):
    """id'lar berilmasa — filtrga tushgan hammasi (sahifadan tashqari ham)."""
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)

    categories = client.get("/api/categories", headers=account["headers"]).json()
    target = next(c for c in categories if c["name"] == "Soliq")

    r = client.post("/api/transactions/bulk-categorize", headers=account["headers"], json={
        "category_id": target["id"], "review_status": "pending_review",
    })
    assert r.status_code == 200
    assert r.json()["updated"] >= 1

    after = client.get("/api/transactions?limit=50", headers=account["headers"]).json()
    assert after["pending_total"] == 0, "hammasi tasdiqlangan bo'lishi kerak"


def test_bulk_categorize_rejects_unknown_category(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)
    r = client.post("/api/transactions/bulk-categorize", headers=account["headers"], json={
        "category_id": "00000000-0000-0000-0000-000000000000",
    })
    assert r.status_code == 404


def test_bulk_categorize_cannot_touch_other_company(client, account, bank_account):
    import uuid as _uuid

    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)
    categories = client.get("/api/categories", headers=account["headers"]).json()
    target = next(c for c in categories if c["name"] == "Transport")

    other = client.post("/api/auth/register", json={
        "company_name": "Boshqa",
        "email": f"other_{_uuid.uuid4().hex[:8]}@example.com",
        "password": "YaxshiParol123",
    }).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    r = client.post("/api/transactions/bulk-categorize", headers=other_headers, json={
        "category_id": target["id"],
    })
    assert r.json()["updated"] == 0, "boshqa kompaniya operatsiyalariga tegdi"


def test_bulk_categorize_requires_auth(client):
    r = client.post("/api/transactions/bulk-categorize", json={"category_id": "x"})
    assert r.status_code in (401, 403)


def test_counterparty_rule_beats_provodka(client, account, bank_account):
    """
    Qoida (o'rganilgan bilim) provodkadan ustun bo'lishi kerak —
    u aniqroq, chunki aynan shu kontragent uchun tasdiqlangan.
    """
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)

    page = client.get("/api/transactions?search=Taminotchi", headers=account["headers"]).json()
    categories = client.get("/api/categories", headers=account["headers"]).json()
    transport = next(c for c in categories if c["name"] == "Transport")

    # Qo'lda tuzatish qoida yaratadi
    client.patch(f"/api/transactions/{page['items'][0]['id']}",
                 headers=account["headers"], json={"category_id": transport["id"]})

    # Keyingi davrda o'sha kontragent qoida bo'yicha topiladi, provodka emas
    upload(client, account["headers"], bank_account["id"], "2026-02-05", ROWS)
    later = client.get("/api/transactions?search=Taminotchi&date_from=2026-02-01",
                       headers=account["headers"]).json()
    assert later["items"][0]["category_name"] == "Transport"
    assert later["items"][0]["category_source"] == "rule"
