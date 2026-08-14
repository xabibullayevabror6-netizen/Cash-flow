"""
Provodka klassifikatori — tizimning eng muhim mantiq qismi.
Bu yerda xato bo'lsa, CFO noto'g'ri raqamga qarab qaror qabul qiladi.
"""
import pytest

from app.services.cash_flow_structure import classify


@pytest.mark.parametrize("code,direction,expected_flow,expected_group", [
    # Ichki ko'chirmalar — na tushum, na xarajat
    ("5110", "in", "internal", "internal.transfer"),
    ("5010", "out", "internal", "internal.transfer"),
    ("5710", "in", "internal", "internal.transfer"),
    ("5530", "out", "internal", "internal.transfer"),

    # Moliyaviy faoliyat — kredit daromad emas
    ("7810", "in", "financing", "fin.loans"),
    ("7810", "out", "financing", "fin.loans"),
    ("6810", "in", "financing", "fin.loans"),
    ("9610", "out", "financing", "fin.interest"),
    ("6610", "out", "financing", "fin.dividends"),
    ("8310", "in", "financing", "fin.equity"),

    # Investitsion
    ("0120", "out", "investing", "inv.long_term_assets"),
    ("4320", "out", "investing", "inv.advance_fixed_assets"),
    ("5810", "out", "investing", "inv.securities"),

    # Asosiy faoliyat — xarajat tuzilmasi
    ("4310", "out", "operating", "op.suppliers"),
    ("6010", "out", "operating", "op.suppliers"),
    ("6973", "out", "operating", "op.payroll"),
    ("6710", "out", "operating", "op.payroll"),
    ("6980", "out", "operating", "op.rent"),
    ("9422", "out", "operating", "op.utilities"),
    ("9430", "out", "operating", "op.admin"),
    ("6410", "out", "operating", "op.taxes"),
    ("4410", "out", "operating", "op.taxes"),

    # Asosiy faoliyat — tushum
    ("6310", "in", "operating", "op.revenue"),
    ("4010", "in", "operating", "op.revenue"),
])
def test_classification(code, direction, expected_flow, expected_group):
    flow, group = classify(code, direction)
    assert flow == expected_flow
    assert group == expected_group


def test_unknown_code_falls_back_to_operating():
    """Notanish kod hisobotdan tushib qolmasligi kerak."""
    assert classify("9999", "out") == ("operating", "op.other_payments")
    assert classify("9999", "in") == ("operating", "op.other_inflows")


def test_missing_code_is_handled():
    assert classify(None, "out")[0] == "operating"
    assert classify("", "in")[0] == "operating"


def test_code_with_subaccount_suffix():
    """1C ba'zan '4310.1' kabi kod beradi — asosiy hisob bo'yicha aniqlanishi kerak."""
    assert classify("4310.1", "out") == ("operating", "op.suppliers")
    assert classify("5110.01", "in") == ("internal", "internal.transfer")


def test_same_code_differs_by_direction():
    """Kirim va chiqim bir xil kodda turli guruhga tushishi mumkin."""
    assert classify("4310", "out")[1] == "op.suppliers"
    assert classify("4310", "in")[1] == "op.other_inflows"
