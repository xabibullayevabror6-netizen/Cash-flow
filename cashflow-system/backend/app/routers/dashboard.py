"""
Dashboard endpointlari.

Ishlash tamoyili: yig'indi SQL tomonida hisoblanadi, Python'ga faqat guruhlangan
natija keladi. Ilgari barcha tranzaksiyalar xotiraga yuklanib, Python'da
aylantirilardi — 100 ming qatorda bu har bir so'rovga ~3 soniya qo'shardi.

Buni qilish mumkin, chunki classify() sof funksiya bo'lib, faqat
(corr_account_code, direction) ga bog'liq. Demak avval SQL'da shu ikkilik
bo'yicha guruhlab, keyin guruhlarni klassifikatsiya qilsa bo'ladi — natija
qatorma-qator hisoblangani bilan bir xil, lekin qatorlar soni yuzlab marta kam.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.services.cash_flow_structure import classify, label as group_label
from app import models, schemas

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

IN = models.Direction.in_
OUT = models.Direction.out


def _conditions(
    company_id: str,
    date_from: Optional[date],
    date_to: Optional[date],
    currency: Optional[str],
):
    conditions = [models.Transaction.company_id == company_id]
    if date_from:
        conditions.append(models.Transaction.date >= date_from)
    if date_to:
        conditions.append(models.Transaction.date <= date_to)
    if currency:
        conditions.append(models.Transaction.currency == currency)
    return conditions


def _currencies(db: Session, company_id: str) -> List[str]:
    """Kompaniyada uchraydigan valyutalar — eng ko'p ishlatilgani birinchi."""
    rows = (
        db.query(models.Transaction.currency, func.count(models.Transaction.id))
        .filter(models.Transaction.company_id == company_id)
        .group_by(models.Transaction.currency)
        .order_by(func.count(models.Transaction.id).desc())
        .all()
    )
    return [r[0] for r in rows]


def _resolve_currency(db: Session, company_id: str, requested: Optional[str]):
    """
    Hisobot doimo BITTA valyuta ichida yig'iladi.
    Turli valyutalarni qo'shish moliyaviy jihatdan ma'nosiz va jimgina xato beradi,
    shuning uchun bu yerda kurs bo'yicha konvertatsiya ham qilinmaydi.
    """
    available = _currencies(db, company_id)
    if requested and requested in available:
        return requested, available
    return (available[0] if available else None), available


def _direction_str(value) -> str:
    return "in" if value == IN else "out"


@router.get("/summary", response_model=schemas.DashboardSummary)
def dashboard_summary(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    active_currency, _av = _resolve_currency(db, user.company_id, currency)
    conditions = _conditions(user.company_id, date_from, date_to, active_currency)

    row = db.query(
        func.coalesce(func.sum(case((models.Transaction.direction == IN, models.Transaction.amount), else_=0)), 0),
        func.coalesce(func.sum(case((models.Transaction.direction == OUT, models.Transaction.amount), else_=0)), 0),
        func.min(models.Transaction.date),
        func.max(models.Transaction.date),
    ).filter(*conditions).one()

    cash_in, cash_out, period_start, period_end = float(row[0]), float(row[1]), row[2], row[3]
    return schemas.DashboardSummary(
        cash_in=cash_in,
        cash_out=cash_out,
        net_cash_flow=cash_in - cash_out,
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/by-category", response_model=List[schemas.CategoryBreakdownItem])
def dashboard_by_category(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    active_currency, _av = _resolve_currency(db, user.company_id, currency)
    conditions = _conditions(user.company_id, date_from, date_to, active_currency)

    # Kategoriya nomi JOIN orqali olinadi — har qatorga alohida so'rov ketmaydi
    rows = (
        db.query(
            models.Category.name,
            models.Transaction.direction,
            func.sum(models.Transaction.amount),
        )
        .outerjoin(models.Category, models.Category.id == models.Transaction.category_id)
        .filter(*conditions)
        .group_by(models.Category.name, models.Transaction.direction)
        .all()
    )

    items = [
        schemas.CategoryBreakdownItem(
            category_name=name or "Kategoriyalanmagan",
            direction=_direction_str(direction),
            amount=float(total),
        )
        for name, direction, total in rows
    ]
    return sorted(items, key=lambda i: -i.amount)


@router.get("/structure", response_model=schemas.CashFlowStructure)
def cash_flow_structure(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Pul oqimining CFO darajasidagi tuzilmasi: asosiy / investitsion / moliyaviy
    faoliyat kesimida, xarajat va tushum guruhlariga ajratilgan holda.
    Ichki ko'chirmalar alohida qatlamga chiqariladi va asosiy ko'rsatkichlarga kirmaydi.

    Natija doimo bitta valyuta ichida — `currency` berilmasa, eng ko'p
    ishlatilgani tanlanadi.
    """
    active_currency, available = _resolve_currency(db, user.company_id, currency)
    conditions = _conditions(user.company_id, date_from, date_to, active_currency)

    # Provodka + yo'nalish bo'yicha guruhlash. classify() aynan shu ikkisiga
    # bog'liq, shuning uchun guruhlangandan keyin klassifikatsiya qilish
    # qatorma-qator hisoblash bilan bir xil natija beradi.
    rows = (
        db.query(
            models.Transaction.corr_account_code,
            models.Transaction.direction,
            func.sum(models.Transaction.amount),
            func.count(models.Transaction.id),
        )
        .filter(*conditions)
        .group_by(models.Transaction.corr_account_code, models.Transaction.direction)
        .all()
    )

    buckets: dict = {}
    totals: dict = {}
    for code, direction_value, total, count in rows:
        direction = _direction_str(direction_value)
        flow_type, group = classify(code, direction)
        amount = float(total)

        entry = buckets.setdefault((flow_type, direction, group), [0.0, 0])
        entry[0] += amount
        entry[1] += count
        totals[(flow_type, direction)] = totals.get((flow_type, direction), 0.0) + amount

    def layer_total(flow_type: str, direction: str) -> float:
        return totals.get((flow_type, direction), 0.0)

    def groups_for(flow_type: str, direction: str) -> List[schemas.StructureGroup]:
        total = layer_total(flow_type, direction)
        items = [
            schemas.StructureGroup(
                group_key=key[2],
                group=group_label(key[2]),
                amount=value[0],
                share=(value[0] / total) if total else 0.0,
                transaction_count=value[1],
            )
            for key, value in buckets.items()
            if key[0] == flow_type and key[1] == direction
        ]
        return sorted(items, key=lambda g: -g.amount)

    layers = []
    for flow_type in ("operating", "investing", "financing", "internal"):
        cash_in = layer_total(flow_type, "in")
        cash_out = layer_total(flow_type, "out")
        if not cash_in and not cash_out:
            continue
        layers.append(
            schemas.StructureLayer(
                flow_type=flow_type,
                cash_in=cash_in,
                cash_out=cash_out,
                net=cash_in - cash_out,
                inflow_groups=groups_for(flow_type, "in"),
                outflow_groups=groups_for(flow_type, "out"),
            )
        )

    operating_in = layer_total("operating", "in")
    operating_out = layer_total("operating", "out")
    investing_net = layer_total("investing", "in") - layer_total("investing", "out")
    financing_net = layer_total("financing", "in") - layer_total("financing", "out")
    operating_net = operating_in - operating_out

    period = db.query(
        func.min(models.Transaction.date), func.max(models.Transaction.date)
    ).filter(*conditions).one()

    return schemas.CashFlowStructure(
        period_start=period[0],
        period_end=period[1],
        currency=active_currency,
        available_currencies=available,
        operating_in=operating_in,
        operating_out=operating_out,
        operating_net=operating_net,
        investing_net=investing_net,
        financing_net=financing_net,
        net_change=operating_net + investing_net + financing_net,
        internal_volume=layer_total("internal", "in") + layer_total("internal", "out"),
        layers=layers,
    )


@router.get("/concentration", response_model=schemas.ConcentrationOut)
def concentration(
    direction: str = Query("out", pattern="^(in|out)$"),
    limit: int = Query(10, ge=1, le=50),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Kontragentlarga bog'liqlik darajasi.

    CFO uchun savol: "agar shu yetkazib beruvchi to'xtasa, biznes qanchalik
    zarar ko'radi?" Bir kontragent aylanmaning katta qismini egallasa, bu
    muzokara kuchi va uzluksizlik bo'yicha real xavf.

    Ichki ko'chirmalar va kreditlar kirmaydi — ular kontragent emas.
    """
    active_currency, _av = _resolve_currency(db, user.company_id, currency)
    conditions = _conditions(user.company_id, date_from, date_to, active_currency)
    conditions.append(
        models.Transaction.direction == (IN if direction == "in" else OUT)
    )

    rows = (
        db.query(
            models.Transaction.counterparty,
            models.Transaction.corr_account_code,
            func.sum(models.Transaction.amount),
        )
        .filter(*conditions)
        .group_by(models.Transaction.counterparty, models.Transaction.corr_account_code)
        .all()
    )

    totals: dict = {}
    for counterparty, code, amount in rows:
        flow_type, _group = classify(code, direction)
        if flow_type != "operating":
            continue
        totals[counterparty] = totals.get(counterparty, 0.0) + float(amount)

    ranked = sorted(totals.items(), key=lambda x: -x[1])
    total = sum(totals.values())

    def share_of_top(n: int) -> float:
        if not total:
            return 0.0
        return sum(amount for _name, amount in ranked[:n]) / total

    # Necha kontragent 80% ni tashkil qiladi — konsentratsiyaning eng
    # tushunarli o'lchovi ("2 ta kontragent pulning 80% ini oladi")
    cumulative = 0.0
    counterparties_for_80 = 0
    for _name, amount in ranked:
        if total and cumulative / total >= 0.8:
            break
        cumulative += amount
        counterparties_for_80 += 1

    largest = (
        db.query(models.Transaction, models.Category.name)
        .outerjoin(models.Category, models.Category.id == models.Transaction.category_id)
        .filter(*conditions)
        .order_by(models.Transaction.amount.desc())
        .limit(5)
        .all()
    )

    return schemas.ConcentrationOut(
        direction=direction,
        currency=active_currency,
        total=total,
        counterparty_count=len(totals),
        top1_share=share_of_top(1),
        top3_share=share_of_top(3),
        top10_share=share_of_top(10),
        counterparties_for_80pct=counterparties_for_80,
        top_counterparties=[
            schemas.ConcentrationItem(
                name=name, amount=amount,
                share=(amount / total) if total else 0.0,
            )
            for name, amount in ranked[:limit]
        ],
        largest_payments=[
            schemas.LargePayment(
                date=t.date, counterparty=t.counterparty,
                amount=float(t.amount), category_name=category_name,
            )
            for t, category_name in largest
        ],
    )


@router.get("/periods", response_model=schemas.PeriodComparison)
def period_comparison(
    limit: int = Query(12, ge=2, le=60),
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Davrlar bo'yicha dinamika va oxirgi ikki davrni taqqoslash.

    Davr = import sanasi (bank ko'chirmasining davri). Bitta davr bo'lsa
    taqqoslash qaytarilmaydi — o'zi bilan o'zini solishtirish ma'nosiz.
    """
    active_currency, _av = _resolve_currency(db, user.company_id, currency)
    conditions = _conditions(user.company_id, None, None, active_currency)

    rows = (
        db.query(
            models.Transaction.date,
            models.Transaction.corr_account_code,
            models.Transaction.direction,
            func.sum(models.Transaction.amount),
            func.count(models.Transaction.id),
        )
        .filter(*conditions)
        .group_by(
            models.Transaction.date,
            models.Transaction.corr_account_code,
            models.Transaction.direction,
        )
        .all()
    )

    # Sana -> [kirim, chiqim, soni]. Ichki ko'chirmalar hisobga olinmaydi.
    buckets: dict = {}
    for period, code, direction_value, amount, count in rows:
        direction = _direction_str(direction_value)
        flow_type, _group = classify(code, direction)
        entry = buckets.setdefault(period, [0.0, 0.0, 0])
        if flow_type != "operating":
            continue
        if direction == "in":
            entry[0] += float(amount)
        else:
            entry[1] += float(amount)
        entry[2] += count

    points = [
        schemas.PeriodPoint(
            period=period,
            operating_in=values[0],
            operating_out=values[1],
            operating_net=values[0] - values[1],
            transaction_count=values[2],
        )
        for period, values in sorted(buckets.items())
    ][-limit:]

    current = points[-1] if points else None
    previous = points[-2] if len(points) >= 2 else None

    def change(now: float, before: float):
        if previous is None or not before:
            return None
        return (now - before) / abs(before)

    return schemas.PeriodComparison(
        currency=active_currency,
        periods=points,
        current=current,
        previous=previous,
        change_in=change(current.operating_in, previous.operating_in) if previous else None,
        change_out=change(current.operating_out, previous.operating_out) if previous else None,
        change_net=change(current.operating_net, previous.operating_net) if previous else None,
    )


@router.get("/top-counterparties", response_model=List[schemas.CounterpartyItem])
def top_counterparties(
    limit: int = 20,
    direction: Optional[str] = Query(None, pattern="^(in|out)$"),
    flow_type: str = Query("operating", pattern="^(operating|investing|financing|all)$"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Kontragentlar reytingi — sukut bo'yicha faqat asosiy faoliyat bo'yicha.

    Ichki ko'chirmalar hech qachon kirmaydi (o'z hisoblari orasidagi o'tkazma
    kontragent emas). Bank kreditlari ham sukut bo'yicha chiqarib tashlanadi:
    ular moliyaviy faoliyat bo'limida alohida ko'rsatiladi, aks holda bank
    reyting boshida mijozdek ko'rinadi.
    """
    active_currency, _av = _resolve_currency(db, user.company_id, currency)
    conditions = _conditions(user.company_id, date_from, date_to, active_currency)
    if direction:
        conditions.append(models.Transaction.direction == (IN if direction == "in" else OUT))

    # Kontragent + provodka + yo'nalish bo'yicha guruhlash: flow_type filtri
    # shu uchlik ustida ishlaydi, tranzaksiyalarni birma-bir yuklash shart emas.
    rows = (
        db.query(
            models.Transaction.counterparty,
            models.Transaction.corr_account_code,
            models.Transaction.direction,
            func.sum(models.Transaction.amount),
        )
        .filter(*conditions)
        .group_by(
            models.Transaction.counterparty,
            models.Transaction.corr_account_code,
            models.Transaction.direction,
        )
        .all()
    )

    totals: dict = {}
    for counterparty, code, direction_value, total in rows:
        row_flow, _group = classify(code, _direction_str(direction_value))
        if row_flow == "internal":
            continue
        if flow_type != "all" and row_flow != flow_type:
            continue
        totals[counterparty] = totals.get(counterparty, 0.0) + float(total)

    ranked = sorted(totals.items(), key=lambda x: -x[1])[:limit]
    return [schemas.CounterpartyItem(counterparty=k, amount=v) for k, v in ranked]
