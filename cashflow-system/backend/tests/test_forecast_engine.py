"""
Prognoz dvigateli: ish kunlari, hafta kuni mavsumiyligi, noaniqlik oralig'i,
boshlang'ich qoldiq va o'z-o'zini tekshirish.
"""
from datetime import date, timedelta

import pytest

from app.services import forecast_service as fs


# --------------------------------------------------------------------------
# Sof funksiyalar
# --------------------------------------------------------------------------

def test_business_days_skip_weekend():
    friday = date(2026, 7, 3)          # juma
    days = fs._next_business_days(friday, 3)
    assert days == [date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)]
    assert all(d.weekday() < 5 for d in days)


def test_quantile_interpolates():
    values = [10, 20, 30, 40, 50]
    assert fs._quantile(values, 0.0) == 10
    assert fs._quantile(values, 1.0) == 50
    assert fs._quantile(values, 0.5) == 30


def test_weekday_factors_detect_pattern():
    """Dushanba ikki barobar yuqori bo'lsa, koeffitsient buni ko'rsatishi kerak."""
    series = {}
    day = date(2026, 7, 6)             # dushanba
    for week in range(8):
        for offset in range(5):
            current = day + timedelta(days=week * 7 + offset)
            series[current] = 200.0 if current.weekday() == 0 else 100.0

    level = fs._median(list(series.values()))
    factors = fs._weekday_factors(series, level)

    assert factors[0] > 1.5, "dushanba koeffitsienti ko'tarilmadi"
    assert all(factors[w] < 1.2 for w in (1, 2, 3, 4))


def test_weekday_factors_shrink_with_few_observations():
    """
    Bitta kuzatuv naqsh emas — koeffitsient 1.0 ga tortilishi kerak,
    aks holda tasodif mavsumiylik deb qabul qilinadi.
    """
    series = {date(2026, 7, 6): 1000.0, date(2026, 7, 7): 100.0}
    factors = fs._weekday_factors(series, 100.0)
    raw = 1000.0 / 100.0
    assert factors[0] < raw / 2, "kam kuzatuvda koeffitsient tortilmadi"


def test_fit_uses_median_not_mean():
    """Bitta ulkan to'lov darajani buzmasligi kerak."""
    series = {date(2026, 7, 6) + timedelta(days=i): 100.0 for i in range(10)}
    series[date(2026, 7, 6)] = 1_000_000.0

    fit = fs._fit(series)
    assert fit["level"] == pytest.approx(100.0, rel=0.2), "mediana o'rniga o'rtacha ishlatilgan"


def test_simulate_returns_requested_shape():
    fit = {"level": 100.0, "factors": {w: 1.0 for w in range(5)}, "shocks": [0.5, 1.0, 1.5]}
    horizon = fs._next_business_days(date(2026, 7, 3), 4)
    paths = fs._simulate(fit, horizon, paths=50)

    assert len(paths) == 50
    assert all(len(p) == 4 for p in paths)
    assert all(value > 0 for p in paths for value in p)


def test_simulate_zero_level_gives_zeros():
    fit = {"level": 0.0, "factors": {}, "shocks": [1.0]}
    paths = fs._simulate(fit, fs._next_business_days(date(2026, 7, 3), 3), paths=5)
    assert all(value == 0.0 for p in paths for value in p)


# --------------------------------------------------------------------------
# To'liq oqim (import orqali)
# --------------------------------------------------------------------------

def _business_days(start: date, count: int):
    days, cursor = [], start
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _seed_history(client, headers, account_id, days, inflow=1000, outflow=800):
    """Har bir ish kuni uchun bitta import."""
    import io
    import pandas as pd

    for day in days:
        rows = [
            ["", "6310", "Mijoz", inflow, None, "tushum"],
            ["", "4310", "Taminotchi", None, outflow, "tovar"],
        ]
        df = pd.DataFrame(rows, columns=[
            "Вид движения", "Кор. счет", "Аналитика", "Приход", "Расход", "Детали платежа",
        ])
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        response = client.post(
            "/api/imports", headers=headers,
            data={"bank_account_id": account_id, "period_date": day.isoformat()},
            files={"file": ("t.xlsx", buffer.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert response.status_code == 200, response.text


def test_forecast_refuses_thin_history(client, account, bank_account):
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 5))

    data = client.get("/api/forecast", headers=account["headers"]).json()
    assert data["sufficient"] is False
    assert data["items"] == []
    assert data["business_days_of_history"] < data["min_days_required"]


def test_forecast_with_enough_history(client, account, bank_account):
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    data = client.get("/api/forecast?weeks=13", headers=account["headers"]).json()
    assert data["sufficient"] is True
    assert len(data["items"]) == 13
    assert data["avg_daily_in"] > 0
    assert data["avg_daily_out"] > 0


def test_forecast_bands_are_ordered(client, account, bank_account):
    """P10 <= P50 <= P90 — buzilsa oraliq ma'nosini yo'qotadi."""
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    data = client.get("/api/forecast", headers=account["headers"]).json()
    for item in data["items"]:
        assert item["balance_p10"] <= item["predicted_balance"] <= item["balance_p90"]


def test_forecast_horizon_uses_business_days_only(client, account, bank_account):
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    data = client.get("/api/forecast?weeks=4", headers=account["headers"]).json()
    for item in data["items"]:
        day = date.fromisoformat(item["forecast_week_start"])
        assert day.weekday() < 5, "prognoz dam olish kunidan boshlanmasligi kerak"


def test_forecast_without_opening_balance_is_flagged(client, account, bank_account):
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    data = client.get("/api/forecast", headers=account["headers"]).json()
    assert data["has_opening_balance"] is False
    assert data["opening_balance"] is None


def test_opening_balance_shifts_the_forecast(client, account, bank_account):
    """Qoldiq kiritilsa, prognoz shu qoldiqdan boshlanishi kerak."""
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    before = client.get("/api/forecast", headers=account["headers"]).json()

    r = client.patch(f"/api/bank-accounts/{bank_account['id']}", headers=account["headers"],
                     json={"opening_balance": 1_000_000, "opening_balance_date": "2026-03-02"})
    assert r.status_code == 200
    assert r.json()["opening_balance"] == 1_000_000

    after = client.get("/api/forecast", headers=account["headers"]).json()
    assert after["has_opening_balance"] is True
    assert after["items"][0]["predicted_balance"] > before["items"][0]["predicted_balance"]


def test_collections_scenario_lowers_forecast(client, account, bank_account):
    """Tushum 20% sekinlashsa, prognoz pastroq bo'lishi kerak."""
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    base = client.get("/api/forecast", headers=account["headers"]).json()
    slow = client.get("/api/forecast?collections_factor=0.8",
                      headers=account["headers"]).json()

    assert slow["items"][0]["predicted_cash_in"] < base["items"][0]["predicted_cash_in"]
    assert slow["items"][-1]["predicted_balance"] < base["items"][-1]["predicted_balance"]


def test_internal_transfers_excluded_from_forecast(client, account, bank_account):
    """
    Ichki ko'chirma prognozga kirsa, kutilayotgan tushum sun'iy ravishda oshadi.
    """
    import io
    import pandas as pd

    days = _business_days(date(2026, 3, 2), 20)
    for day in days:
        rows = [
            ["", "6310", "Mijoz", 1000, None, "tushum"],
            ["", "5110", "O'z hisobi", 900_000, None, "ko'chirma"],   # ichki
            ["", "4310", "Taminotchi", None, 800, "tovar"],
        ]
        df = pd.DataFrame(rows, columns=[
            "Вид движения", "Кор. счет", "Аналитика", "Приход", "Расход", "Детали платежа",
        ])
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        client.post("/api/imports", headers=account["headers"],
                    data={"bank_account_id": bank_account["id"], "period_date": day.isoformat()},
                    files={"file": ("t.xlsx", buffer.getvalue(),
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    data = client.get("/api/forecast", headers=account["headers"]).json()
    # Kunlik kirim darajasi 1000 atrofida bo'lishi kerak, 901000 emas
    assert data["avg_daily_in"] < 10_000, "ichki ko'chirma prognozga kirib ketdi"


def test_recurring_counterparties_detected(client, account, bank_account):
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    data = client.get("/api/forecast", headers=account["headers"]).json()
    names = [r["counterparty"] for r in data["recurring_outflows"]]
    assert "Taminotchi" in names, "har kuni takrorlanuvchi to'lov aniqlanmadi"

    taminotchi = next(r for r in data["recurring_outflows"] if r["counterparty"] == "Taminotchi")
    assert taminotchi["day_share"] > 0.9


def test_weekday_factors_returned_for_audit(client, account, bank_account):
    """Model parametrlari javobda bo'lishi kerak — auditga ochiqlik uchun."""
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    data = client.get("/api/forecast", headers=account["headers"]).json()
    assert set(data["weekday_factors"]) == {"0", "1", "2", "3", "4"}
    assert all(v > 0 for v in data["weekday_factors"].values())


def test_forecast_is_deterministic(client, account, bank_account):
    """Bir xil ma'lumotda bir xil natija — hisobot takrorlanadigan bo'lishi kerak."""
    _seed_history(client, account["headers"], bank_account["id"],
                  _business_days(date(2026, 3, 2), 20))

    first = client.get("/api/forecast", headers=account["headers"]).json()
    second = client.get("/api/forecast", headers=account["headers"]).json()
    assert first["items"] == second["items"]
