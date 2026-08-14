#!/bin/sh
# Server ishga tushishidan oldin baza sxemasini migratsiyalar bilan yangilaydi.
# Migratsiya xato bersa konteyner ko'tarilmaydi — bu ataylab: sxemasi
# mos kelmagan baza ustida ishlash jimgina buzilgan ma'lumotga olib keladi.
set -e

echo "Baza sxemasi tekshirilmoqda…"
alembic upgrade head

# Boshlang'ich kategoriyalar (bir necha marta ishlatish xavfsiz — mavjudlari
# takrorlanmaydi). Bulutga birinchi joylashda qo'lda buyruq berish shart emas.
echo "Boshlang'ich kategoriyalar tekshirilmoqda…"
python seed.py || echo "Ogohlantirish: kategoriyalarni qo'shib bo'lmadi"

# Bulut xizmatlari portni PORT orqali beradi; lokal holatda 8000.
PORT="${PORT:-8000}"

echo "Server ishga tushmoqda (port $PORT)…"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
