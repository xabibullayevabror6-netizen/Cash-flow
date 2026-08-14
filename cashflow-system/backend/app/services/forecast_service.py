"""
Pul oqimi prognozi — treasury amaliyotidagi to'g'ridan-to'g'ri (direct) usul.

MODEL
  Kunlik oqim ikki qismga bo'linadi va har biri alohida modellashtiriladi:

    daily(t) = level x weekday_factor(t) x random_shock

  • level          — kunlik oqimning barqaror darajasi. O'rtacha emas, MEDIANA:
                     bitta yirik to'lov o'rtachani buzadi, medianani buzmaydi.
  • weekday_factor — hafta kuni ta'siri. Amalda dushanba va payshanba oqimi
                     40% ga farq qiladi; tekis o'rtacha bu naqshni yo'qotadi.
                     Kam kuzatuv bo'lsa koeffitsient 1.0 ga tortiladi
                     (shrinkage) — aks holda tasodif naqsh deb qabul qilinadi.
  • random_shock   — tarixiy nisbatlar taqsimoti. Bootstrap orqali qayta
                     namuna olinadi.

NIMA UCHUN BOOTSTRAP
  Bitta raqamli prognoz CFO uchun xavfli: u aniqlik illyuziyasini beradi.
  Tarixiy kunlik nisbatlardan 2000 marta yo'l (path) generatsiya qilinadi va
  natijada P10 / P50 / P90 oralig'i chiqadi. Bu taqsimot shakli haqida hech
  qanday faraz qilmaydi — real ma'lumot qanday bo'lsa, shundayligicha ishlatadi.

NIMA UCHUN ISH KUNLARI
  Bank ko'chirmalari faqat ish kunlarida keladi. Kalendar kunlari bo'yicha
  o'rtacha olish dam olish kunlarini nol deb hisoblab, darajani 5/7 ga
  pasaytiradi. Shuning uchun butun model ish kunlari ustida quriladi.

QOLDIQ
  Likvidlik prognozi HAQIQIY bank qoldig'idan boshlanishi kerak. Importlardagi
  kirim-chiqim yig'indisi qoldiq emas — u faqat oqim. Qoldiq bank hisobida
  ko'rsatilmagan bo'lsa, model buni ochiq aytadi va faqat oqimni bashorat
  qiladi ("pul qachon tugaydi" savoliga javob bermaydi).

ISHONCHLILIK
  Model o'zini o'zi tekshiradi (backtest): oxirgi bir necha kun tarixdan
  olib tashlanadi, ular bashorat qilinadi va xato o'lchanadi (MAPE).
  Foydalanuvchi prognozga qanchalik ishonish mumkinligini biladi.
"""
import random
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app import models
from app.services.cash_flow_structure import classify

# Prognoz uchun minimal tarix (ish kunlari). Bundan kam bo'lsa hafta kuni
# koeffitsientlari ham, noaniqlik oralig'i ham ma'noga ega bo'lmaydi.
MIN_BUSINESS_DAYS = 15

# Bootstrap yo'llari soni. 2000 — kvantillar barqarorlashadigan, lekin
# hisoblash tez qoladigan miqdor.
BOOTSTRAP_PATHS = 2000

# Kontragent shu ulushdan ko'p kunda uchrasa "takrorlanuvchi" deb hisoblanadi
RECURRING_DAY_SHARE = 0.6

_RNG = random.Random(20260814)   # takrorlanadigan natija uchun qat'iy urug'


# --------------------------------------------------------------------------
# Yordamchi funksiyalar
# --------------------------------------------------------------------------

def _is_business_day(day: date) -> bool:
    return day.weekday() < 5


def _next_business_days(start_after: date, count: int) -> List[date]:
    days = []
    cursor = start_after
    while len(days) < count:
        cursor += timedelta(days=1)
        if _is_business_day(cursor):
            days.append(cursor)
    return days


def _median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else 0.0


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    """Chiziqli interpolyatsiyali kvantil."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = q * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    weight = position - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def _weekday_factors(series: Dict[date, float], level: float) -> Dict[int, float]:
    """
    Hafta kuni koeffitsientlari, kam kuzatuvda 1.0 ga tortilgan holda.

    Shrinkage: lambda = n / (n + 2). Ikki kuzatuv bilan koeffitsient yarim
    kuchda qo'llanadi, oltita bilan deyarli to'liq. Bu tasodifiy chetlanishni
    "mavsumiylik" deb qabul qilishdan saqlaydi.
    """
    if level <= 0:
        return {w: 1.0 for w in range(5)}

    by_weekday: Dict[int, List[float]] = defaultdict(list)
    for day, value in series.items():
        by_weekday[day.weekday()].append(value)

    factors = {}
    for weekday in range(5):
        observations = by_weekday.get(weekday, [])
        if not observations:
            factors[weekday] = 1.0
            continue
        raw = _median(observations) / level
        shrink = len(observations) / (len(observations) + 2)
        factors[weekday] = 1.0 + shrink * (raw - 1.0)
    return factors


def _daily_series(
    transactions: Sequence[models.Transaction],
    direction: models.Direction,
) -> Dict[date, float]:
    """Kunlik yig'indi. Ichki ko'chirmalar chiqarib tashlanadi."""
    series: Dict[date, float] = defaultdict(float)
    business_days = set()

    for t in transactions:
        if not _is_business_day(t.date):
            continue
        business_days.add(t.date)
        if t.direction != direction:
            continue
        flow_type, _group = classify(
            t.corr_account_code,
            "in" if t.direction == models.Direction.in_ else "out",
        )
        if flow_type == "internal":
            continue
        series[t.date] += float(t.amount)

    # Operatsiyasi bo'lmagan ish kuni ham ma'lumot — nol oqim
    for day in business_days:
        series.setdefault(day, 0.0)
    return dict(series)


def _fit(series: Dict[date, float]) -> dict:
    """Daraja, hafta kuni koeffitsientlari va shok taqsimotini aniqlaydi."""
    values = list(series.values())
    level = _median(values)

    factors = _weekday_factors(series, level)

    # Shoklar — kutilgan qiymatga nisbatan haqiqiy qiymat
    shocks = []
    if level > 0:
        for day, value in series.items():
            expected = level * factors.get(day.weekday(), 1.0)
            if expected > 0:
                shocks.append(value / expected)
    if not shocks:
        shocks = [1.0]

    return {"level": level, "factors": factors, "shocks": shocks}


def _simulate(fit: dict, horizon_days: Sequence[date], paths: int) -> List[List[float]]:
    """
    Bootstrap: har bir yo'l uchun kunlik qiymatlarni generatsiya qiladi.
    Returns: paths x len(horizon_days) matritsa.
    """
    level = fit["level"]
    factors = fit["factors"]
    shocks = fit["shocks"]

    if level <= 0:
        return [[0.0] * len(horizon_days) for _ in range(paths)]

    result = []
    for _ in range(paths):
        path = []
        for day in horizon_days:
            expected = level * factors.get(day.weekday(), 1.0)
            path.append(expected * _RNG.choice(shocks))
        result.append(path)
    return result


def _backtest(series: Dict[date, float], holdout: int) -> Optional[float]:
    """
    Modelni o'z tarixida sinaydi: oxirgi `holdout` kun olib tashlanadi,
    bashorat qilinadi va MAPE (o'rtacha absolyut foiz xato) o'lchanadi.

    None qaytarsa — sinash uchun ma'lumot yetarli emas.
    """
    ordered = sorted(series.items())
    if len(ordered) < MIN_BUSINESS_DAYS + holdout:
        return None

    train = dict(ordered[:-holdout])
    test = ordered[-holdout:]

    fit = _fit(train)
    if fit["level"] <= 0:
        return None

    errors = []
    for day, actual in test:
        predicted = fit["level"] * fit["factors"].get(day.weekday(), 1.0)
        if actual > 0:
            errors.append(abs(predicted - actual) / actual)
    return (sum(errors) / len(errors)) if errors else None


def _recurring_counterparties(
    transactions: Sequence[models.Transaction],
    direction: models.Direction,
    business_day_count: int,
) -> List[dict]:
    """
    Muntazam takrorlanadigan to'lovlar — prognozning eng ishonchli qismi.
    Ular ko'p kunda uchraydi, shuning uchun kelasi kunlarda ham kutiladi.
    """
    if business_day_count <= 0:
        return []

    by_counterparty: Dict[str, Dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for t in transactions:
        if t.direction != direction or not _is_business_day(t.date):
            continue
        flow_type, _group = classify(
            t.corr_account_code,
            "in" if direction == models.Direction.in_ else "out",
        )
        if flow_type == "internal":
            continue
        by_counterparty[t.counterparty][t.date] += float(t.amount)

    recurring = []
    for counterparty, per_day in by_counterparty.items():
        day_share = len(per_day) / business_day_count
        if day_share < RECURRING_DAY_SHARE:
            continue
        amounts = list(per_day.values())
        recurring.append({
            "counterparty": counterparty,
            "day_share": day_share,
            "median_amount": _median(amounts),
            "days_seen": len(per_day),
        })

    recurring.sort(key=lambda r: -r["median_amount"] * r["day_share"])
    return recurring[:10]


# --------------------------------------------------------------------------
# Asosiy funksiya
# --------------------------------------------------------------------------

def generate_forecast(
    db: Session,
    company_id: str,
    weeks: int = 13,
    currency: Optional[str] = None,
    collections_factor: float = 1.0,
) -> dict:
    """
    Args:
        weeks: prognoz ufqi (haftalarda). Ish kunlari bo'yicha hisoblanadi.
        collections_factor: stsenariy tutqichi — tushumni shu koeffitsientga
            ko'paytiradi (0.8 = tushum 20% sekinlashsa).
    """
    lookback_start = date.today() - timedelta(days=365)

    q = db.query(models.Transaction).filter(
        models.Transaction.company_id == company_id,
        models.Transaction.date >= lookback_start,
    )
    if currency:
        q = q.filter(models.Transaction.currency == currency)
    transactions = q.all()

    empty = {
        "items": [],
        "sufficient": False,
        "business_days_of_history": 0,
        "min_days_required": MIN_BUSINESS_DAYS,
        "currency": currency,
        "avg_daily_in": 0.0,
        "avg_daily_out": 0.0,
        "weekday_factors": {},
        "opening_balance": None,
        "has_opening_balance": False,
        "accuracy_mape": None,
        "recurring_inflows": [],
        "recurring_outflows": [],
        "minimum_balance_date": None,
        "minimum_balance": None,
        "history_start": None,
        "history_end": None,
        "collections_factor": collections_factor,
    }
    if not transactions:
        return empty

    inflow = _daily_series(transactions, models.Direction.in_)
    outflow = _daily_series(transactions, models.Direction.out)
    all_days = sorted(set(inflow) | set(outflow))

    result = dict(
        empty,
        business_days_of_history=len(all_days),
        history_start=all_days[0] if all_days else None,
        history_end=all_days[-1] if all_days else None,
    )
    if len(all_days) < MIN_BUSINESS_DAYS:
        return result

    # Ikkala yo'nalish bir xil kunlar to'plamida bo'lishi kerak
    for day in all_days:
        inflow.setdefault(day, 0.0)
        outflow.setdefault(day, 0.0)

    fit_in = _fit(inflow)
    fit_out = _fit(outflow)

    horizon_days = _next_business_days(all_days[-1], weeks * 5)
    paths_in = _simulate(fit_in, horizon_days, BOOTSTRAP_PATHS)
    paths_out = _simulate(fit_out, horizon_days, BOOTSTRAP_PATHS)

    # --- Boshlang'ich qoldiq ---
    accounts = db.query(models.BankAccount).filter(
        models.BankAccount.company_id == company_id
    )
    if currency:
        accounts = accounts.filter(models.BankAccount.currency == currency)

    opening_total = 0.0
    has_opening = False
    for account in accounts:
        if account.opening_balance is None or account.opening_balance_date is None:
            continue
        has_opening = True
        # Qoldiq sanasidan keyingi haqiqiy oqim qo'shiladi
        movement = sum(
            (float(t.amount) if t.direction == models.Direction.in_ else -float(t.amount))
            for t in transactions
            if t.bank_account_id == account.id and t.date >= account.opening_balance_date
        )
        opening_total += float(account.opening_balance) + movement

    starting_balance = opening_total if has_opening else 0.0

    # --- Kumulyativ yo'llar va kvantillar ---
    horizon_length = len(horizon_days)
    cumulative_paths = []
    for path_index in range(BOOTSTRAP_PATHS):
        running = starting_balance
        path = []
        for day_index in range(horizon_length):
            net = (paths_in[path_index][day_index] * collections_factor
                   - paths_out[path_index][day_index])
            running += net
            path.append(running)
        cumulative_paths.append(path)

    # Haftalik nuqtalarga siqamiz — CFO haftada bir qaraydi, kunlik shovqin kerak emas
    items = []
    minimum_balance = None
    minimum_balance_date = None

    for week_index in range(weeks):
        last_day_index = min((week_index + 1) * 5 - 1, horizon_length - 1)
        if last_day_index < 0:
            break
        week_days = horizon_days[week_index * 5:(week_index + 1) * 5]
        if not week_days:
            break

        balances = sorted(p[last_day_index] for p in cumulative_paths)
        week_in = statistics.median(
            sum(p[week_index * 5:(week_index + 1) * 5]) for p in paths_in
        ) * collections_factor
        week_out = statistics.median(
            sum(p[week_index * 5:(week_index + 1) * 5]) for p in paths_out
        )

        p50 = _quantile(balances, 0.50)
        item = {
            "forecast_week_start": week_days[0],
            "predicted_cash_in": round(week_in, 2),
            "predicted_cash_out": round(week_out, 2),
            "predicted_balance": round(p50, 2),
            "balance_p10": round(_quantile(balances, 0.10), 2),
            "balance_p90": round(_quantile(balances, 0.90), 2),
        }
        items.append(item)

        if minimum_balance is None or p50 < minimum_balance:
            minimum_balance = p50
            minimum_balance_date = week_days[0]

    holdout = max(3, min(5, len(all_days) // 5))
    accuracy = _backtest(outflow, holdout)

    result.update({
        "items": items,
        "sufficient": True,
        "avg_daily_in": round(fit_in["level"], 2),
        "avg_daily_out": round(fit_out["level"], 2),
        "weekday_factors": {
            str(w): round(fit_out["factors"].get(w, 1.0), 3) for w in range(5)
        },
        "opening_balance": round(starting_balance, 2) if has_opening else None,
        "has_opening_balance": has_opening,
        "accuracy_mape": round(accuracy, 4) if accuracy is not None else None,
        "recurring_inflows": _recurring_counterparties(
            transactions, models.Direction.in_, len(all_days)),
        "recurring_outflows": _recurring_counterparties(
            transactions, models.Direction.out, len(all_days)),
        "minimum_balance": round(minimum_balance, 2) if minimum_balance is not None else None,
        "minimum_balance_date": minimum_balance_date,
    })
    return result


def save_forecast(db: Session, company_id: str, forecasts: List[dict]) -> None:
    for f in forecasts:
        existing = (
            db.query(models.Forecast)
            .filter(
                models.Forecast.company_id == company_id,
                models.Forecast.forecast_week_start == f["forecast_week_start"],
            )
            .first()
        )
        if existing:
            existing.predicted_cash_in = f["predicted_cash_in"]
            existing.predicted_cash_out = f["predicted_cash_out"]
            existing.predicted_balance = f["predicted_balance"]
        else:
            db.add(models.Forecast(
                company_id=company_id,
                forecast_week_start=f["forecast_week_start"],
                predicted_cash_in=f["predicted_cash_in"],
                predicted_cash_out=f["predicted_cash_out"],
                predicted_balance=f["predicted_balance"],
            ))
    db.commit()
