import os
import shutil
import tempfile
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.i18n import translator
from app import models, schemas
from app.services.excel_parser import parse_bank_export, ExcelParseError
from app.services.categorizer import categorize_transaction

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("", response_model=schemas.ImportBatchOut)
def upload_import(
    request: Request,
    bank_account_id: str = Form(...),
    period_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _ = translator(request)
    bank_account = db.query(models.BankAccount).filter(
        models.BankAccount.id == bank_account_id,
        models.BankAccount.company_id == user.company_id,
    ).first()
    if not bank_account:
        raise HTTPException(status_code=404, detail=_("bank_account.not_found"))

    # Bir hisob raqamiga bir sana uchun faqat bitta import (takroriy yuklashning oldini olish).
    # Muvaffaqiyatsiz (failed) importlar hisobga olinmaydi — ularni qayta yuklash mumkin.
    duplicate = db.query(models.ImportBatch).filter(
        models.ImportBatch.bank_account_id == bank_account.id,
        models.ImportBatch.period_date == period_date,
        models.ImportBatch.status != models.ImportStatus.failed,
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            # Xabarda hisob raqami aniq aytiladi — aks holda cheklov
            # butun tizimga tegishlidek tuyuladi
            detail=_("import.duplicate",
                     date=period_date.strftime('%d.%m.%Y'),
                     file=duplicate.file_name,
                     bank=bank_account.bank_name,
                     account=bank_account.account_number),
        )

    # Faylni vaqtinchalik saqlash
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    batch = models.ImportBatch(
        company_id=user.company_id,
        bank_account_id=bank_account.id,
        file_name=file.filename,
        period_date=period_date,
        uploaded_by=user.id,
        status=models.ImportStatus.processing,
    )
    db.add(batch)
    try:
        db.commit()
    except IntegrityError:
        # Bir vaqtda kelgan ikkinchi so'rov — bazadagi unique indeks ushlab qoldi
        db.rollback()
        os.unlink(tmp_path)
        raise HTTPException(
            status_code=409,
            detail=_("import.duplicate_short",
                     date=period_date.strftime('%d.%m.%Y'),
                     bank=bank_account.bank_name,
                     account=bank_account.account_number),
        )
    db.refresh(batch)

    try:
        rows = parse_bank_export(tmp_path, period_date)
    except ExcelParseError as exc:
        batch.status = models.ImportStatus.failed
        db.commit()
        raise HTTPException(status_code=400, detail=_(exc.key, **exc.params))
    finally:
        os.unlink(tmp_path)

    # Har bir qatorni yozish + kategoriyalash (5.1 va 5.2 bosqichlar).
    # Kutilmagan xatoda batch 'processing' holida qotib qolmasligi kerak — aks holda
    # unique indeks shu hisob/sana uchun qayta yuklashni butunlay bloklab qo'yadi.
    try:
        _write_transactions(db, batch, bank_account, user, rows)
    except Exception:
        db.rollback()
        batch.status = models.ImportStatus.failed
        db.commit()
        raise HTTPException(status_code=500, detail=_("import.processing_failed"))

    db.refresh(batch)
    return batch


def _write_transactions(db, batch, bank_account, user, rows):
    for row in rows:
        result = categorize_transaction(
            db=db,
            company_id=user.company_id,
            counterparty=row["counterparty"],
            raw_description=row["raw_description"],
            corr_account_code=row["corr_account_code"],
            direction=row["direction"],
        )

        transaction = models.Transaction(
            company_id=user.company_id,
            import_batch_id=batch.id,
            bank_account_id=bank_account.id,
            date=row["date"],
            direction=models.Direction.in_ if row["direction"] == "in" else models.Direction.out,
            amount=row["amount"],
            currency=bank_account.currency,
            counterparty=row["counterparty"],
            corr_account_code=row["corr_account_code"],
            raw_description=row["raw_description"],
            category_id=result["category_id"],
            category_source=result["category_source"],
            confidence_score=result["confidence_score"],
            review_status=result["review_status"],
        )
        db.add(transaction)

    batch.row_count = len(rows)
    batch.status = models.ImportStatus.completed
    db.commit()


@router.get("", response_model=List[schemas.ImportBatchListItem])
def list_imports(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Yuklangan davrlar ro'yxati — eng yangisi birinchi."""
    batches = (
        db.query(models.ImportBatch, models.BankAccount)
        .join(models.BankAccount, models.ImportBatch.bank_account_id == models.BankAccount.id)
        .filter(models.ImportBatch.company_id == user.company_id)
        .order_by(models.ImportBatch.period_date.desc(), models.ImportBatch.uploaded_at.desc())
        .all()
    )

    # Har bir batch bo'yicha tranzaksiya soni va aylanma — bitta so'rovda
    stats = dict(
        (row[0], row[1:])
        for row in db.query(
            models.Transaction.import_batch_id,
            func.count(models.Transaction.id),
            func.coalesce(
                func.sum(
                    case((models.Transaction.direction == models.Direction.in_,
                          models.Transaction.amount), else_=0)
                ), 0),
            func.coalesce(
                func.sum(
                    case((models.Transaction.direction == models.Direction.out,
                          models.Transaction.amount), else_=0)
                ), 0),
        )
        .filter(models.Transaction.company_id == user.company_id)
        .group_by(models.Transaction.import_batch_id)
        .all()
    )

    result = []
    for batch, account in batches:
        count, cash_in, cash_out = stats.get(batch.id, (0, 0, 0))
        result.append(
            schemas.ImportBatchListItem(
                id=batch.id,
                file_name=batch.file_name,
                period_date=batch.period_date,
                row_count=batch.row_count,
                status=batch.status.value,
                uploaded_at=batch.uploaded_at,
                bank_name=account.bank_name,
                account_number=account.account_number,
                transaction_count=count,
                cash_in=float(cash_in),
                cash_out=float(cash_out),
            )
        )
    return result


@router.delete("/{batch_id}", response_model=schemas.ImportDeleteResult)
def delete_import(
    request: Request,
    batch_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Import qilingan davrni va unga tegishli barcha tranzaksiyalarni o'chiradi.

    Kategoriya qoidalari (category_rules) o'chirilmaydi — ular o'rganilgan bilim
    bo'lib, keyingi importlarda qayta ishlatiladi.
    """
    batch = db.query(models.ImportBatch).filter(
        models.ImportBatch.id == batch_id,
        models.ImportBatch.company_id == user.company_id,
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail=translator(request)("import.not_found"))

    deleted = db.query(models.Transaction).filter(
        models.Transaction.import_batch_id == batch.id
    ).delete(synchronize_session=False)

    period_date = batch.period_date
    db.delete(batch)
    db.commit()

    return schemas.ImportDeleteResult(
        deleted_batch_id=batch_id,
        deleted_transactions=deleted,
        period_date=period_date,
    )


@router.get("/{batch_id}/status", response_model=schemas.ImportBatchOut)
def get_import_status(
    request: Request,
    batch_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    batch = db.query(models.ImportBatch).filter(
        models.ImportBatch.id == batch_id,
        models.ImportBatch.company_id == user.company_id,
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail=translator(request)("import.not_found"))
    return batch
