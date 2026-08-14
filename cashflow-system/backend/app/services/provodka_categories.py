"""
Provodka (Кор. счет) bo'yicha kategoriyani avtomatik aniqlash.

Nima uchun kerak:
  Kontragent nomi bo'yicha qoida faqat o'sha kontragent avval uchragan bo'lsa
  ishlaydi. AI esa kalit talab qiladi va pul turadi. Provodka esa har bir
  operatsiyada mavjud va buxgalteriya jihatidan ma'noga ega — 6973 bu ish haqi,
  6980 bu ijara. Demak kategoriyaning katta qismini u bepul va darhol hal qiladi.

Ishonch darajalari:
  HIGH   — kod aynan bitta ma'noni bildiradi (6973 = ish haqi). Avtomatik
           tasdiqlanadi.
  MEDIUM — kod yo'nalishni ko'rsatadi, lekin tafsilotni emas (4310 = ta'minotchi,
           u nima sotgani noma'lum). Kategoriya qo'yiladi, ammo buxgalter
           tasdig'iga yuboriladi.
  Yo'q   — kod umumiy (4890 "boshqa debitorlar"). AI'ga yoki "Boshqa"ga qoladi.

Kodlar to'g'ridan-to'g'ri emas, cash_flow_structure dagi guruh kalitlari orqali
ishlatiladi — kod ro'yxati bir joyda turishi uchun.
"""
from typing import Optional, Tuple

from app.services import cash_flow_structure as cfs

HIGH = 0.95
MEDIUM = 0.6

# (group_key, direction) -> (kategoriya nomi, ishonch)
# direction: "in" | "out" | None (ikkalasi uchun ham)
_MAP = {
    # --- Aniq ma'noli kodlar ---
    (cfs.G_REVENUE, "in"): ("Mijozlardan tushum", HIGH),
    (cfs.G_PAYROLL, "out"): ("Ish haqi", HIGH),
    (cfs.G_RENT, "out"): ("Ijara", HIGH),
    (cfs.G_TAXES, None): ("Soliq", HIGH),
    (cfs.G_UTILITIES, "out"): ("Kommunal xizmatlar", HIGH),
    (cfs.G_INTERNAL, None): ("Hisoblar orasidagi ko'chirma", HIGH),

    (cfs.G_LOANS, "in"): ("Kredit olish", HIGH),
    (cfs.G_LOANS, "out"): ("Kredit to'lovi", HIGH),
    (cfs.G_INTEREST, "out"): ("Foiz to'lovlari", HIGH),
    (cfs.G_DIVIDENDS, "out"): ("Dividendlar", HIGH),
    (cfs.G_EQUITY, "in"): ("Ustav kapitali", HIGH),

    (cfs.G_LONG_TERM_ASSETS, None): ("Asosiy vositalar", HIGH),
    (cfs.G_ADVANCE_FA, "out"): ("Asosiy vositalar", HIGH),

    # --- Yo'nalish aniq, tafsilot noaniq ---
    # 4310/6010 — ta'minotchi bilan hisob-kitob. Nima sotib olingani kodda yo'q.
    (cfs.G_SUPPLIERS, "out"): ("Dori/tovar xaridi", MEDIUM),
    # 9410-9440 — "boshqa operatsion xarajatlar". Bank xizmati ham, kanselyariya
    # ham shu yerga tushadi, shuning uchun tasdiqlashga yuboriladi.
    (cfs.G_ADMIN, "out"): ("Boshqa", MEDIUM),
}


def category_for(corr_account_code: Optional[str], direction: str) -> Optional[Tuple[str, float]]:
    """
    Provodka bo'yicha kategoriya nomi va ishonch darajasini qaytaradi.
    Aniqlab bo'lmasa — None (keyingi bosqichga, AI'ga o'tadi).
    """
    _flow, group_key = cfs.classify(corr_account_code, direction)

    match = _MAP.get((group_key, direction))
    if match is None:
        match = _MAP.get((group_key, None))
    return match
