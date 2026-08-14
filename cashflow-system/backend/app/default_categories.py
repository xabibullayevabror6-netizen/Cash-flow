"""
Tizimning umumiy kategoriyalari (company_id = NULL).

Yagona manba: seed.py ham, testlar ham shu ro'yxatdan foydalanadi —
ikki joyda alohida saqlansa, vaqt o'tib ular bir-biridan uzoqlashadi.
"""
from typing import List, Tuple

DEFAULT_CATEGORIES: List[Tuple[str, str]] = [
    ("Mijozlardan tushum", "income"),
    ("Kredit olish", "income"),
    ("Qarz qaytishi", "income"),
    ("Ustav kapitali", "income"),
    ("Dori/tovar xaridi", "expense"),
    ("Ish haqi", "expense"),
    ("Soliq", "expense"),
    ("Ijara", "expense"),
    ("Kommunal xizmatlar", "expense"),
    ("Transport", "expense"),
    ("Reklama", "expense"),
    ("Bank xizmati", "expense"),
    ("Kredit to'lovi", "expense"),
    ("Foiz to'lovlari", "expense"),
    ("Dividendlar", "expense"),
    ("Asosiy vositalar", "expense"),
    ("Korporativ karta", "expense"),
    # Ichki ko'chirmalar alohida turadi: ular na daromad, na xarajat, lekin
    # "Boshqa"ga tushib ketsa hisobotni chalkashtiradi.
    ("Hisoblar orasidagi ko'chirma", "expense"),
    ("Boshqa", "expense"),
]


def seed_categories(db) -> int:
    """Yetishmayotgan umumiy kategoriyalarni qo'shadi. Qo'shilganlar sonini qaytaradi."""
    from app import models

    added = 0
    for name, category_type in DEFAULT_CATEGORIES:
        exists = db.query(models.Category).filter(
            models.Category.name == name,
            models.Category.company_id.is_(None),
        ).first()
        if not exists:
            db.add(models.Category(company_id=None, name=name, type=category_type))
            added += 1
    db.commit()
    return added
