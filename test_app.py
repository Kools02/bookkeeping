import os
os.environ.setdefault("SECRET_KEY", "test-secret")

from app import compute_vat_and_cost, normalize_tin, normalize_category, to_decimal


def test_tin_normalization():
    assert normalize_tin(" 123-456-789 ") == "123456789"


def test_category_normalization():
    assert normalize_category("ds grocery") == "D/S-GROCERY"


def test_vat_calculation():
    vat, cost = compute_vat_and_cost(to_decimal("112.00"))
    assert vat == to_decimal("12.00")
    assert cost == to_decimal("100.00")


def test_negative_invoice_rejected():
    try:
        compute_vat_and_cost(to_decimal("-1.00"))
    except ValueError:
        pass
    else:
        raise AssertionError("Negative invoices must be rejected")
