"""
O'zbekiston milliy hisoblar rejasi (Кор. счет) ma'lumotnomasi.

Kod bo'yicha hisob nomini topadi va uni AI promptiga kontekst sifatida beradi.
Texnik hujjatning 5.2-bo'limiga muvofiq, kod hech qachon yagona/qat'iy asos sifatida
ishlatilmaydi — faqat qo'shimcha signal.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "accounts.json"


@lru_cache(maxsize=1)
def _accounts() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def lookup(corr_account_code: Optional[str]) -> Optional[str]:
    """Kod bo'yicha hisob nomini qaytaradi: avval aniq mos, so'ng guruh (masalan 9021 -> 9020 -> 9000)."""
    if not corr_account_code:
        return None

    code = str(corr_account_code).strip()
    if not code:
        return None

    accounts = _accounts()
    if code in accounts:
        return accounts[code]["name"]

    # 1C ba'zan subkonto bilan uzunroq kod beradi — guruh darajasiga qadar qisqartiriladi
    digits = code.split(".")[0]
    for candidate in (digits[:4], digits[:3] + "0", digits[:2] + "00", digits[:1] + "000"):
        if candidate in accounts:
            return accounts[candidate]["name"]

    return None
