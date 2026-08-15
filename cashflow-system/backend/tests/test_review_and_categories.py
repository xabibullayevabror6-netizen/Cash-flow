"""Tasdiqlash oqimi, kategoriyalar boshqaruvi va prognoz chegaralari."""
import io
import uuid

import pandas as pd


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


ROWS = [
    ["", "6310", "Mijoz A", 1000, None, "tushum"],
    ["", "4310", "Taminotchi B", None, 600, "tovar"],
    ["", "9430", "Boshqa C", None, 50, "xizmat"],
]


def test_transactions_are_paginated(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)

    page = client.get("/api/transactions?limit=2", headers=account["headers"]).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert page["limit"] == 2

    page2 = client.get("/api/transactions?limit=2&offset=2", headers=account["headers"]).json()
    assert len(page2["items"]) == 1


def test_search_filters_transactions(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)

    page = client.get("/api/transactions?search=Mijoz", headers=account["headers"]).json()
    assert page["total"] == 1
    assert page["items"][0]["counterparty"] == "Mijoz A"


# ROWS dagi uchta qatordan faqat ikkitasi tasdiqlashni talab qiladi:
#   6310 (mijozdan tushum) — provodka aniq, avtomatik tasdiqlanadi
#   4310 (ta'minotchi) va 9430 (boshqa xarajat) — noaniq, tasdiqlashga tushadi
PENDING_IN_ROWS = 2


def test_bulk_confirm_selected(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)
    page = client.get("/api/transactions?review_status=pending_review",
                      headers=account["headers"]).json()
    assert page["pending_total"] == PENDING_IN_ROWS

    ids = [i["id"] for i in page["items"][:1]]
    r = client.post("/api/transactions/bulk-confirm",
                    headers=account["headers"], json={"transaction_ids": ids})
    assert r.json()["confirmed"] == 1

    after = client.get("/api/transactions?limit=1", headers=account["headers"]).json()
    assert after["pending_total"] == PENDING_IN_ROWS - 1


def test_bulk_confirm_all(client, account, bank_account):
    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)
    r = client.post("/api/transactions/bulk-confirm", headers=account["headers"], json={})
    assert r.json()["confirmed"] == PENDING_IN_ROWS

    after = client.get("/api/transactions?limit=1", headers=account["headers"]).json()
    assert after["pending_total"] == 0


def test_changing_category_creates_reusable_rule(client, account, bank_account):
    """
    Buxgalter kategoriyani tuzatsa, o'sha kontragent uchun qoida saqlanishi kerak —
    keyingi importda AI qayta so'ralmaydi.
    """
    from app import models

    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)
    page = client.get("/api/transactions?search=Taminotchi", headers=account["headers"]).json()
    transaction = page["items"][0]

    categories = client.get("/api/categories", headers=account["headers"]).json()
    target = next(c for c in categories if c["name"] == "Ijara")

    r = client.patch(f"/api/transactions/{transaction['id']}",
                     headers=account["headers"], json={"category_id": target["id"]})
    assert r.status_code == 200
    assert r.json()["review_status"] == "confirmed"
    assert r.json()["category_source"] == "manual"

    # Ikkinchi davrda o'sha kontragent qoida orqali topiladi
    upload(client, account["headers"], bank_account["id"], "2026-02-05", ROWS)
    page = client.get("/api/transactions?search=Taminotchi&date_from=2026-02-01",
                      headers=account["headers"]).json()
    assert page["items"][0]["category_id"] == target["id"]
    assert page["items"][0]["category_source"] == "rule"


def test_create_and_rename_category(client, account):
    r = client.post("/api/categories", headers=account["headers"],
                    json={"name": "Marketing", "type": "expense"})
    assert r.status_code == 201
    category_id = r.json()["id"]

    dup = client.post("/api/categories", headers=account["headers"],
                      json={"name": "marketing", "type": "expense"})
    assert dup.status_code == 409, "nom katta-kichik harfdan qat'i nazar takrorlanmasligi kerak"

    r = client.patch(f"/api/categories/{category_id}", headers=account["headers"],
                     json={"name": "Reklama", "type": "income"})
    assert r.json()["name"] == "Reklama"
    assert r.json()["type"] == "income"


def test_category_in_use_cannot_be_deleted(client, account, bank_account):
    created = client.post("/api/categories", headers=account["headers"],
                          json={"name": "Vaqtinchalik", "type": "expense"}).json()

    upload(client, account["headers"], bank_account["id"], "2026-01-05", ROWS)
    page = client.get("/api/transactions?limit=1", headers=account["headers"]).json()
    client.patch(f"/api/transactions/{page['items'][0]['id']}",
                 headers=account["headers"], json={"category_id": created["id"]})

    r = client.delete(f"/api/categories/{created['id']}", headers=account["headers"])
    assert r.status_code == 409


def test_unused_category_can_be_deleted(client, account):
    created = client.post("/api/categories", headers=account["headers"],
                          json={"name": "Ishlatilmagan", "type": "expense"}).json()
    assert client.delete(f"/api/categories/{created['id']}",
                         headers=account["headers"]).status_code == 204


def test_system_category_cannot_be_edited(client, account):
    categories = client.get("/api/categories", headers=account["headers"]).json()
    system = next(c for c in categories if c["is_system"])
    r = client.patch(f"/api/categories/{system['id']}",
                     headers=account["headers"], json={"name": "Buzildi"})
    assert r.status_code == 404

# Prognoz testlari test_forecast_engine.py ga ko'chirildi — u yerda yangi
# model (ish kunlari, noaniqlik oralig'i, backtest) to'liqroq qoplangan.
