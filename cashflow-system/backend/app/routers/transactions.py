from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.i18n import translator
from app.database import get_db
from app.auth import get_current_user
from app.config import settings
from app.services.provodka_categories import category_for
from app import models, schemas

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _filtered(
    db: Session,
    company_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category_id: Optional[str] = None,
    review_status: Optional[str] = None,
    currency: Optional[str] = None,
    direction: Optional[str] = None,
    search: Optional[str] = None,
):
    q = db.query(models.Transaction).filter(models.Transaction.company_id == company_id)

    if date_from:
        q = q.filter(models.Transaction.date >= date_from)
    if date_to:
        q = q.filter(models.Transaction.date <= date_to)
    if category_id:
        q = q.filter(models.Transaction.category_id == category_id)
    if review_status:
        q = q.filter(models.Transaction.review_status == review_status)
    if currency:
        q = q.filter(models.Transaction.currency == currency)
    if direction:
        q = q.filter(
            models.Transaction.direction ==
            (models.Direction.in_ if direction == "in" else models.Direction.out)
        )
    if search:
        pattern = f"%{search.strip()}%"
        q = q.filter(
            or_(
                models.Transaction.counterparty.ilike(pattern),
                models.Transaction.raw_description.ilike(pattern),
            )
        )
    return q


@router.get("", response_model=schemas.TransactionPage)
def list_transactions(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category_id: Optional[str] = None,
    review_status: Optional[str] = None,
    currency: Optional[str] = None,
    direction: Optional[str] = Query(None, pattern="^(in|out)$"),
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Sahifalangan ro'yxat. Butun jadvalni bir yo'la qaytarish katta bazada
    interfeysni ham, serverni ham to'xtatib qo'yadi.
    """
    q = _filtered(db, user.company_id, date_from, date_to, category_id,
                  review_status, currency, direction, search)

    total = q.count()

    # joinedload — kategoriya nomi uchun har qatorga alohida so'rov ketmasligi uchun
    results = (
        q.options(joinedload(models.Transaction.category))
        .order_by(models.Transaction.date.desc(), models.Transaction.id)
        .limit(limit)
        .offset(offset)
        .all()
    )

    pending_total = (
        db.query(func.count(models.Transaction.id))
        .filter(
            models.Transaction.company_id == user.company_id,
            models.Transaction.review_status == models.ReviewStatus.pending_review,
        )
        .scalar()
    )

    items = []
    for t in results:
        item = schemas.TransactionOut.model_validate(t)
        item.category_name = t.category.name if t.category else None
        items.append(item)

    return schemas.TransactionPage(
        items=items, total=total, limit=limit, offset=offset,
        pending_total=pending_total or 0,
    )


@router.post("/bulk-confirm", response_model=schemas.BulkConfirmResult)
def bulk_confirm(
    payload: schemas.BulkConfirmRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Bir nechta operatsiyani birdan tasdiqlash.

    `transaction_ids` berilsa — faqat o'shalar; berilmasa — filtrga tushgan
    barcha tasdiqlanmagan operatsiyalar. 367 tani birma-bir tasdiqlash
    amalda ishlamaydi, shuning uchun bu zarur.
    """
    q = _filtered(
        db, user.company_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        category_id=payload.category_id,
        review_status=models.ReviewStatus.pending_review.value,
        search=payload.search,
    )
    if payload.transaction_ids:
        q = q.filter(models.Transaction.id.in_(payload.transaction_ids))

    confirmed = q.update(
        {models.Transaction.review_status: models.ReviewStatus.confirmed},
        synchronize_session=False,
    )
    db.commit()
    return schemas.BulkConfirmResult(confirmed=confirmed or 0)


@router.post("/bulk-categorize", response_model=schemas.BulkCategorizeResult)
def bulk_categorize(
    request: Request,
    payload: schemas.BulkCategorizeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Belgilangan operatsiyalarni bittada bir kategoriyaga o'tkazadi.

    Bitta operatsiyani tuzatish (PATCH) bilan bir xil ishlaydi:
      • kategoriya qo'yiladi, manba `manual` bo'ladi (buxgalter qarori)
      • operatsiya tasdiqlangan holatga o'tadi
      • har bir kontragent uchun qoida saqlanadi — keyingi importda o'sha
        kontragent avtomatik shu kategoriyaga tushadi

    `transaction_ids` berilmasa, filtrga tushgan BARCHA operatsiyalar
    o'zgartiriladi (sahifada ko'rinmayotganlari ham).
    """
    _ = translator(request)

    category = db.query(models.Category).filter(
        models.Category.id == payload.category_id,
        or_(
            models.Category.company_id == user.company_id,
            models.Category.company_id.is_(None),
        ),
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail=_("category.not_found"))

    q = _filtered(
        db, user.company_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        review_status=payload.review_status,
        search=payload.search,
    )
    if payload.transaction_ids:
        q = q.filter(models.Transaction.id.in_(payload.transaction_ids))

    transactions = q.all()
    if not transactions:
        return schemas.BulkCategorizeResult(
            updated=0, rules_created=0, category_name=category.name
        )

    counterparties = set()
    for t in transactions:
        t.category_id = category.id
        t.category_source = models.CategorySource.manual
        t.confidence_score = 1.0
        t.review_status = models.ReviewStatus.confirmed
        counterparties.add(t.counterparty)

    # Kontragent qoidalari — keyingi importda qayta so'ralmasligi uchun.
    # Mavjudlari yangilanadi, yo'qlari yaratiladi.
    existing = {
        r.counterparty_pattern: r
        for r in db.query(models.CategoryRule).filter(
            models.CategoryRule.company_id == user.company_id,
            models.CategoryRule.counterparty_pattern.in_(counterparties),
        )
    }

    rules_created = 0
    for counterparty in counterparties:
        rule = existing.get(counterparty)
        if rule:
            rule.category_id = category.id
            rule.last_used_at = datetime.utcnow()
        else:
            db.add(models.CategoryRule(
                company_id=user.company_id,
                counterparty_pattern=counterparty,
                category_id=category.id,
            ))
            rules_created += 1

    db.commit()
    return schemas.BulkCategorizeResult(
        updated=len(transactions),
        rules_created=rules_created,
        category_name=category.name,
    )


@router.post("/recategorize", response_model=schemas.RecategorizeResult)
def recategorize(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Mavjud operatsiyalarni provodka (Кор. счет) bo'yicha qayta taqsimlaydi.

    Qo'lda tuzatilgan operatsiyalarga TEGILMAYDI — buxgalterning qarori
    avtomatik qoidadan ustun turadi. Provodkasi noaniq bo'lganlar ham
    o'z joyida qoladi.

    Yangi import uchun kerak emas — u allaqachon shu mantiq bilan ishlaydi.
    Bu endpoint eski ma'lumotni yangi qoidalarga o'tkazish uchun.
    """
    categories = db.query(models.Category).filter(
        (models.Category.company_id == user.company_id) | (models.Category.company_id.is_(None))
    ).all()
    by_name = {c.name: c for c in categories}

    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.company_id == user.company_id)
        .all()
    )

    updated = skipped_manual = unresolved = 0

    for t in transactions:
        if t.category_source == models.CategorySource.manual:
            skipped_manual += 1
            continue

        direction = "in" if t.direction == models.Direction.in_ else "out"
        match = category_for(t.corr_account_code, direction)
        if not match:
            unresolved += 1
            continue

        name, confidence = match
        category = by_name.get(name)
        if category is None:
            unresolved += 1
            continue

        confirmed = confidence >= settings.ai_confidence_threshold
        changed = (
            t.category_id != category.id
            or t.category_source != models.CategorySource.provodka
        )

        t.category_id = category.id
        t.category_source = models.CategorySource.provodka
        t.confidence_score = confidence
        t.review_status = (
            models.ReviewStatus.confirmed if confirmed
            else models.ReviewStatus.pending_review
        )
        if changed:
            updated += 1

    db.commit()
    return schemas.RecategorizeResult(
        updated=updated, skipped_manual=skipped_manual, unresolved=unresolved
    )


@router.patch("/{transaction_id}", response_model=schemas.TransactionOut)
def update_transaction_category(
    request: Request,
    transaction_id: str,
    payload: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Buxgalter kategoriyani qo'lda tuzatadi — category_source=manual bo'ladi."""
    t = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.company_id == user.company_id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail=translator(request)("transaction.not_found"))

    t.category_id = payload.category_id
    t.category_source = models.CategorySource.manual
    t.review_status = models.ReviewStatus.confirmed
    db.commit()
    db.refresh(t)

    # Kelajakda avtomatik topilishi uchun qoida yangilanadi/yaratiladi
    existing_rule = db.query(models.CategoryRule).filter(
        models.CategoryRule.company_id == user.company_id,
        models.CategoryRule.counterparty_pattern == t.counterparty,
    ).first()
    if existing_rule:
        existing_rule.category_id = payload.category_id
    else:
        db.add(models.CategoryRule(
            company_id=user.company_id,
            counterparty_pattern=t.counterparty,
            category_id=payload.category_id,
        ))
    db.commit()

    item = schemas.TransactionOut.model_validate(t)
    item.category_name = t.category.name if t.category else None
    return item


@router.post("/{transaction_id}/confirm", response_model=schemas.TransactionOut)
def confirm_transaction(
    request: Request,
    transaction_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """AI taklifini o'zgartirmasdan tasdiqlash."""
    t = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.company_id == user.company_id,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail=translator(request)("transaction.not_found"))

    t.review_status = models.ReviewStatus.confirmed
    db.commit()
    db.refresh(t)

    item = schemas.TransactionOut.model_validate(t)
    item.category_name = t.category.name if t.category else None
    return item
