from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.i18n import translator
from app import models, schemas

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=List[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Kompaniya kategoriyalari + tizimning umumiy kategoriyalari."""
    categories = db.query(models.Category).filter(
        (models.Category.company_id == user.company_id) | (models.Category.company_id.is_(None))
    ).order_by(models.Category.name).all()

    # Har bir kategoriyada nechta operatsiya borligi — bitta so'rovda
    usage = dict(
        db.query(models.Transaction.category_id, func.count(models.Transaction.id))
        .filter(models.Transaction.company_id == user.company_id)
        .group_by(models.Transaction.category_id)
        .all()
    )

    out = []
    for c in categories:
        item = schemas.CategoryOut.model_validate(c)
        item.transaction_count = usage.get(c.id, 0)
        item.is_system = c.company_id is None
        out.append(item)
    return out


@router.post("", response_model=schemas.CategoryOut, status_code=201)
def create_category(
    request: Request,
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _ = translator(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail=_("category.name_required"))

    exists = db.query(models.Category).filter(
        models.Category.company_id == user.company_id,
        func.lower(models.Category.name) == name.lower(),
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail=_("category.duplicate", name=name))

    category = models.Category(
        company_id=user.company_id,
        name=name,
        type=models.CategoryType.income if payload.type == "income" else models.CategoryType.expense,
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    item = schemas.CategoryOut.model_validate(category)
    item.transaction_count = 0
    item.is_system = False
    return item


@router.patch("/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    request: Request,
    category_id: str,
    payload: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _ = translator(request)
    category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.company_id == user.company_id,   # tizim kategoriyasi tahrirlanmaydi
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail=_("category.not_found"))

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail=_("category.name_required"))
        clash = db.query(models.Category).filter(
            models.Category.company_id == user.company_id,
            func.lower(models.Category.name) == name.lower(),
            models.Category.id != category_id,
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail=_("category.duplicate", name=name))
        category.name = name

    if payload.type is not None:
        category.type = (
            models.CategoryType.income if payload.type == "income" else models.CategoryType.expense
        )

    db.commit()
    db.refresh(category)

    count = db.query(func.count(models.Transaction.id)).filter(
        models.Transaction.category_id == category_id
    ).scalar()

    item = schemas.CategoryOut.model_validate(category)
    item.transaction_count = count or 0
    item.is_system = False
    return item


@router.delete("/{category_id}", status_code=204)
def delete_category(
    request: Request,
    category_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Ishlatilmayotgan kategoriyani o'chiradi.
    Operatsiyalari bor kategoriya o'chirilmaydi — aks holda o'sha operatsiyalar
    kategoriyasiz qolib, hisobotdan tushib qolardi.
    """
    _ = translator(request)
    category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.company_id == user.company_id,
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail=_("category.not_found"))

    used = db.query(func.count(models.Transaction.id)).filter(
        models.Transaction.category_id == category_id
    ).scalar()
    if used:
        raise HTTPException(status_code=409, detail=_("category.in_use", count=used))

    db.query(models.CategoryRule).filter(
        models.CategoryRule.category_id == category_id
    ).delete(synchronize_session=False)
    db.delete(category)
    db.commit()
    return None
