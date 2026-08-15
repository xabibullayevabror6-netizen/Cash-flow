"""
Tizimning umumiy (company_id=NULL) kategoriyalarini bazaga qo'shadi.
Ishga tushirish: python seed.py

Sxema Alembic orqali yaratiladi — bu skript faqat ma'lumot qo'shadi.
Bir necha marta ishlatish xavfsiz: mavjud kategoriyalar takrorlanmaydi.
"""
from app.database import SessionLocal
from app.default_categories import DEFAULT_CATEGORIES, seed_categories

db = SessionLocal()
try:
    added = seed_categories(db)
    print(f"{len(DEFAULT_CATEGORIES)} ta kategoriya tekshirildi, {added} tasi qo'shildi.")
finally:
    db.close()
