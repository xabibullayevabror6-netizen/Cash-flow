from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth import get_current_user
from app.i18n import translator
from app import models, schemas

router = APIRouter(prefix="/api/bank-accounts", tags=["bank-accounts"])


@router.get("", response_model=List[schemas.BankAccountOut])
def list_bank_accounts(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return db.query(models.BankAccount).filter(
        models.BankAccount.company_id == user.company_id
    ).all()


@router.post("", response_model=schemas.BankAccountOut)
def create_bank_account(
    payload: schemas.BankAccountCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    account = models.BankAccount(company_id=user.company_id, **payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=schemas.BankAccountOut)
def update_bank_account(
    request: Request,
    account_id: str,
    payload: schemas.BankAccountUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Boshlang'ich qoldiqni belgilash.

    Prognoz shu qoldiqdan boshlab likvidlikni hisoblaydi. Berilmasa,
    prognoz faqat oqimni ko'rsatadi — bu "pul qachon tugaydi" savoliga
    javob bermaydi.
    """
    _ = translator(request)
    account = db.query(models.BankAccount).filter(
        models.BankAccount.id == account_id,
        models.BankAccount.company_id == user.company_id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail=_("bank_account.not_found"))

    data = payload.model_dump(exclude_unset=True)
    if "opening_balance" in data:
        account.opening_balance = data["opening_balance"]
    if "opening_balance_date" in data:
        account.opening_balance_date = data["opening_balance_date"]

    db.commit()
    db.refresh(account)
    return account
