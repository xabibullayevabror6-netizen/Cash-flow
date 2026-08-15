"""
Pul oqimi tuzilmasi — CFO darajasidagi tahlil uchun.

Har bir operatsiya Кор. счет provodkasi bo'yicha uch qatlamga ajratiladi:

  flow_type — operating / investing / financing / internal
  group_key — xarajat (yoki tushum) tuzilmasidagi bo'lim identifikatori

Guruh nomi emas, KALIT qaytariladi: interfeys uni o'z tiliga tarjima qiladi
(uz / uz-Cyrl / ru / en). Backend'da matn qattiq yozilsa, til almashtirilganda
diagramma yorliqlari o'zbekchada qolib ketadi.

Nima uchun bu yerda AI emas, qat'iy qoida ishlatiladi:
  Kategoriya (masalan "Reklama xarajati") — bu boshqaruv talqini, u AI bilan aniqlanadi.
  Pul oqimi tuzilmasi esa buxgalteriya faktidir: 7810 — bu kredit, 5110 — bu o'z hisobi.
  CFO hisoboti auditga bardosh berishi kerak, shuning uchun bu yerda taxmin qilinmaydi.

INTERNAL alohida ajratilgan: o'z hisoblari orasidagi ko'chirmalar (5xxx) na tushum,
na xarajat — ular Cash In/Out ga qo'shilsa, aylanma sun'iy ravishda shishib ketadi.
"""
from typing import Optional, Tuple

# --- Guruh kalitlari ---
G_INTERNAL = "internal.transfer"

G_LOANS = "fin.loans"
G_INTEREST = "fin.interest"
G_DIVIDENDS = "fin.dividends"
G_EQUITY = "fin.equity"

G_ADVANCE_FA = "inv.advance_fixed_assets"
G_SECURITIES = "inv.securities"
G_LOANS_ISSUED = "inv.loans_issued"
G_ASSET_DISPOSAL = "inv.asset_disposal"
G_LONG_TERM_ASSETS = "inv.long_term_assets"

G_SUPPLIERS = "op.suppliers"
G_PAYROLL = "op.payroll"
G_RENT = "op.rent"
G_UTILITIES = "op.utilities"
G_ADMIN = "op.admin"
G_TAXES = "op.taxes"
G_OTHER_PAYMENTS = "op.other_payments"

G_REVENUE = "op.revenue"
G_RELATED_PARTIES = "op.related_parties"
G_OTHER_OP_INCOME = "op.other_operating_income"
G_OTHER_INFLOWS = "op.other_inflows"

G_UNKNOWN = "unknown"

# Sukut bo'yicha (o'zbekcha) nomlar — API'ni to'g'ridan-to'g'ri o'qiyotgan
# iste'molchi uchun; interfeys group_key bo'yicha o'z tarjimasini ishlatadi.
GROUP_LABELS = {
    G_INTERNAL: "Hisoblar orasidagi ko'chirma",
    G_LOANS: "Kredit va qarzlar",
    G_INTEREST: "Foiz to'lovlari",
    G_DIVIDENDS: "Dividendlar",
    G_EQUITY: "Ustav kapitali",
    G_ADVANCE_FA: "Asosiy vositalarga avans",
    G_SECURITIES: "Qimmatli qog'ozlar",
    G_LOANS_ISSUED: "Berilgan qarzlar",
    G_ASSET_DISPOSAL: "Aktivlarni sotish",
    G_LONG_TERM_ASSETS: "Asosiy vositalar va aktivlar",
    G_SUPPLIERS: "Ta'minotchilar va xom ashyo",
    G_PAYROLL: "Ish haqi va mehnat to'lovlari",
    G_RENT: "Ijara",
    G_UTILITIES: "Kommunal xizmatlar",
    G_ADMIN: "Ma'muriy va operatsion xarajatlar",
    G_TAXES: "Soliqlar va byudjet to'lovlari",
    G_OTHER_PAYMENTS: "Boshqa operatsion to'lovlar",
    G_REVENUE: "Xaridorlardan tushum",
    G_RELATED_PARTIES: "Bog'liq korxonalardan",
    G_OTHER_OP_INCOME: "Boshqa operatsion daromadlar",
    G_OTHER_INFLOWS: "Boshqa operatsion tushumlar",
    G_UNKNOWN: "Aniqlanmagan",
}

# --- Ichki ko'chirmalar: o'z pulining bir hisobdan boshqasiga o'tishi ---
_INTERNAL = {
    "5010", "5011", "5020",           # kassa
    "5110", "5125", "5126",           # hisob-kitob raqami
    "5210", "5211", "5220",           # valyuta hisoblari
    "5510", "5520", "5530", "5580",   # maxsus hisoblar, akkreditiv, plastik
    "5610",                           # pul ekvivalentlari
    "5710", "5720",                   # yo'ldagi pul ko'chirmalari
}

# --- Moliyaviy faoliyat ---
_FINANCING = {
    "6810": G_LOANS, "6820": G_LOANS, "6830": G_LOANS, "6840": G_LOANS,
    "7810": G_LOANS, "7820": G_LOANS, "7830": G_LOANS, "7840": G_LOANS,
    "6950": G_LOANS,
    "6920": G_INTEREST, "9610": G_INTEREST, "9530": G_INTEREST,
    "6610": G_DIVIDENDS, "6620": G_DIVIDENDS, "9520": G_DIVIDENDS,
    "8310": G_EQUITY, "8320": G_EQUITY, "8330": G_EQUITY,
    "8410": G_EQUITY, "8420": G_EQUITY,
}

# --- Investitsion faoliyat ---
_INVESTING = {
    "4320": G_ADVANCE_FA,
    "5810": G_SECURITIES, "5890": G_SECURITIES,
    "5830": G_LOANS_ISSUED,
    "9210": G_ASSET_DISPOSAL, "9220": G_ASSET_DISPOSAL, "9230": G_ASSET_DISPOSAL,
}

# --- Asosiy faoliyat: xarajat tuzilmasi (chiqim) ---
_OPERATING_OUT = {
    "6010": G_SUPPLIERS, "6011": G_SUPPLIERS, "6020": G_SUPPLIERS,
    "4310": G_SUPPLIERS, "4311": G_SUPPLIERS, "4330": G_SUPPLIERS,
    "9110": G_SUPPLIERS, "9120": G_SUPPLIERS, "9130": G_SUPPLIERS, "9140": G_SUPPLIERS,

    "6710": G_PAYROLL, "6720": G_PAYROLL, "6740": G_PAYROLL, "6973": G_PAYROLL,
    "6510": G_PAYROLL, "6517": G_PAYROLL, "6970": G_PAYROLL,
    "4210": G_PAYROLL, "4220": G_PAYROLL, "4230": G_PAYROLL, "4290": G_PAYROLL,

    "6910": G_RENT, "6980": G_RENT, "7910": G_RENT, "3110": G_RENT,

    "9422": G_UTILITIES,

    "9410": G_ADMIN, "9420": G_ADMIN, "9421": G_ADMIN, "9430": G_ADMIN,
    "9440": G_ADMIN, "3120": G_ADMIN, "3190": G_ADMIN,
}

# --- Asosiy faoliyat: tushum tuzilmasi (kirim) ---
_OPERATING_IN = {
    "4010": G_REVENUE, "4011": G_REVENUE, "4012": G_REVENUE, "4020": G_REVENUE,
    "6310": G_REVENUE, "6311": G_REVENUE, "6320": G_REVENUE, "6390": G_REVENUE,
    "7310": G_REVENUE,
    "9010": G_REVENUE, "9020": G_REVENUE, "9030": G_REVENUE,
    "4110": G_RELATED_PARTIES, "4120": G_RELATED_PARTIES,
}

# Soliqlar — kirim (qaytarish) va chiqim (to'lov) uchun bir xil guruh
_TAX_PREFIXES = ("44", "64")


def _normalize(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    cleaned = str(code).strip().split(".")[0]
    return cleaned or None


def classify(corr_account_code: Optional[str], direction: str) -> Tuple[str, str]:
    """
    Returns: (flow_type, group_key)
      flow_type: 'operating' | 'investing' | 'financing' | 'internal'
      direction: 'in' yoki 'out'
    """
    code = _normalize(corr_account_code)
    if code is None:
        return "operating", G_UNKNOWN

    if code in _INTERNAL:
        return "internal", G_INTERNAL

    if code in _FINANCING:
        return "financing", _FINANCING[code]

    if code in _INVESTING:
        return "investing", _INVESTING[code]

    # Uzoq muddatli aktivlar sinfi: 0100-0899 (AV, NMA, kapital qo'yilmalar)
    if code.startswith("0") and len(code) == 4 and code[1] in "12345678":
        return "investing", G_LONG_TERM_ASSETS

    if code.startswith(_TAX_PREFIXES):
        return "operating", G_TAXES

    if direction == "out":
        if code in _OPERATING_OUT:
            return "operating", _OPERATING_OUT[code]
        return "operating", G_OTHER_PAYMENTS

    if code in _OPERATING_IN:
        return "operating", _OPERATING_IN[code]
    if code.startswith("93") or code.startswith("95"):
        return "operating", G_OTHER_OP_INCOME
    return "operating", G_OTHER_INFLOWS


def label(group_key: str) -> str:
    """Sukut bo'yicha (o'zbekcha) nom."""
    return GROUP_LABELS.get(group_key, group_key)
