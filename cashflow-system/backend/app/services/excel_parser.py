"""
1C bank export Excel faylini o'qish va normallashtirish.

Kutilayotgan ustunlar (namunaviy faylga asosan):
  N | Вид движения | Кор. счет | Аналитика | Приход | Расход | Детали платежа

Faylda operatsiya sanasi YO'Q — shuning uchun period_date barcha qatorlarga
tashqaridan (import so'rovidan) beriladi.
"""
from datetime import date
from typing import List, Dict, Any

import pandas as pd

REQUIRED_COLUMNS = [
    "Вид движения", "Кор. счет", "Аналитика", "Приход", "Расход", "Детали платежа"
]


class ExcelParseError(Exception):
    """Tarjima kaliti va o'rin almashtirish qiymatlarini olib yuradi —
    matnni router so'rov tiliga qarab shakllantiradi."""

    def __init__(self, key: str, **params):
        self.key = key
        self.params = params
        super().__init__(key)


def parse_bank_export(file_path: str, period_date: date) -> List[Dict[str, Any]]:
    """
    Excel faylni o'qiydi va normallashtirilgan tranzaksiyalar ro'yxatini qaytaradi.
    Har bir element: {date, direction, amount, counterparty, corr_account_code, raw_description}
    """
    try:
        df = pd.read_excel(file_path)
    except Exception as exc:
        raise ExcelParseError("excel.unreadable", error=str(exc))

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ExcelParseError("excel.missing_columns", columns=", ".join(missing))

    rows = []
    for _, r in df.iterrows():
        prihod = r.get("Приход")
        rashod = r.get("Расход")

        if pd.notna(prihod) and float(prihod) != 0:
            direction = "in"
            amount = float(prihod)
        elif pd.notna(rashod) and float(rashod) != 0:
            direction = "out"
            amount = float(rashod)
        else:
            # ikkalasi ham bo'sh — o'tkazib yuboriladi
            continue

        counterparty = str(r.get("Аналитика") or "").strip()
        corr_code = str(r.get("Кор. счет")) if pd.notna(r.get("Кор. счет")) else None
        description = str(r.get("Детали платежа") or "").strip()

        if not counterparty:
            continue

        rows.append({
            "date": period_date,
            "direction": direction,
            "amount": amount,
            "counterparty": counterparty,
            "corr_account_code": corr_code,
            "raw_description": description,
        })

    if not rows:
        raise ExcelParseError("excel.no_rows")

    return rows
