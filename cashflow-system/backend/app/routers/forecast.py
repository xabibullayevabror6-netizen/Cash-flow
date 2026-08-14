from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.auth import get_current_user
from app import models, schemas
from app.services.forecast_service import generate_forecast, save_forecast

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("", response_model=schemas.ForecastResponse)
def get_forecast(
    weeks: int = Query(13, ge=1, le=52),
    currency: Optional[str] = None,
    collections_factor: float = Query(
        1.0, ge=0.1, le=2.0,
        description="Stsenariy: tushumni shu koeffitsientga ko'paytiradi "
                    "(0.8 = tushum 20% sekinlashsa)",
    ),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Pul oqimi prognozi — noaniqlik oralig'i va o'z-o'zini tekshirish bilan.

    Tarix yetarli bo'lmasa `sufficient=false` qaytadi va `items` bo'sh bo'ladi:
    kam ma'lumotdan chizilgan prognoz ishonchli ko'rinadi, lekin asossiz.

    `has_opening_balance=false` bo'lsa, qoldiq nolldan boshlanadi va faqat
    oqimni ko'rsatadi — "pul qachon tugaydi" savoliga javob bermaydi.
    Buning uchun bank hisobiga haqiqiy qoldiqni kiritish kerak.
    """
    if not currency:
        row = (
            db.query(models.Transaction.currency, func.count(models.Transaction.id))
            .filter(models.Transaction.company_id == user.company_id)
            .group_by(models.Transaction.currency)
            .order_by(func.count(models.Transaction.id).desc())
            .first()
        )
        currency = row[0] if row else None

    result = generate_forecast(
        db, user.company_id,
        weeks=weeks,
        currency=currency,
        collections_factor=collections_factor,
    )

    # Faqat asosiy (stsenariysiz) prognoz saqlanadi — stsenariy tahlili
    # vaqtinchalik hisob, uni bazaga yozish tarixni chalkashtiradi
    if result["sufficient"] and collections_factor == 1.0:
        save_forecast(db, user.company_id, result["items"])

    return result
