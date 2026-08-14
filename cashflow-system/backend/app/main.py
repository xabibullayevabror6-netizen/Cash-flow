from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    auth, bank_accounts, imports, transactions, categories,
    dashboard, forecast, export,
)

# Sxema Alembic migratsiyalari orqali boshqariladi (entrypoint.sh da
# `alembic upgrade head` ishlaydi). Ilgari bu yerda Base.metadata.create_all()
# turardi — u faqat YO'Q jadvallarni yaratadi, mavjudini o'zgartirmaydi.
# Natijada har bir yangi ustun yoki indeks qo'lda ALTER TABLE talab qilardi.

# Swagger/ReDoc butun API xaritasini ochib beradi. Ichki foydalanishda qulay,
# lekin ilova internetga chiqarilganda hujumchiga tayyor yo'riqnoma bo'ladi —
# shuning uchun production'da o'chiriladi.
_docs_enabled = not settings.is_production

app = FastAPI(
    title="Cash Flow API",
    version="1.0.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# CORS: aniq manzillar ro'yxati + (development'da) lokal tarmoq shabloni.
# Shablonsiz boshqa kompyuterdan kirilganda brauzer so'rovni bloklaydi,
# chunki uning origin'i (masalan http://192.168.1.5:5173) ro'yxatda bo'lmaydi.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(bank_accounts.router)
app.include_router(imports.router)
app.include_router(transactions.router)
app.include_router(categories.router)
app.include_router(dashboard.router)
app.include_router(forecast.router)
app.include_router(export.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Frontend'ni shu serverning o'zi tarqatishi (bitta konteyner rejimi)
# --------------------------------------------------------------------------
# Bulutga joylashda ikkita alohida xizmat (nginx + backend) o'rniga bitta
# konteyner ancha sodda: bitta manzil, bitta port, CORS umuman kerak emas.
# Lokal ishlashda esa frontend hamon nginx orqali beriladi va bu blok
# shunchaki o'tkazib yuboriladi (papka yo'q bo'lgani uchun).
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        """
        SPA marshrutlari (/dashboard, /forecast, ...) fayl emas — hammasi
        index.html ga yo'naltiriladi, aks holda sahifani yangilaganda 404 chiqadi.
        API yo'llari bu yerga yetib kelmaydi: ular yuqorida ro'yxatdan o'tgan.
        """
        candidate = _STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)

        # index.html hech qachon keshlanmaydi — u yangi build fayllariga
        # ishora qiladi, keshlansa foydalanuvchi eski ilovani ko'raveradi.
        return FileResponse(
            _STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-store, must-revalidate"},
        )
