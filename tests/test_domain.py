from decimal import Decimal

import pytest
from werkzeug.datastructures import MultiDict

from app.domain import DomainError, calculate_totals, extract_cart, parse_tax_rate, to_money


def test_parse_tax_rate_accepts_percentage_and_fraction():
    assert parse_tax_rate("13") == Decimal("0.13")
    assert parse_tax_rate("0.13") == Decimal("0.13")
    assert parse_tax_rate(0) == Decimal("0")


def test_calculate_totals_rounds_money_and_tax():
    subtotal, tax, total = calculate_totals(
        [{"cantidad": 3, "precio_unitario": "10.00"}], "13"
    )
    assert subtotal == Decimal("30.00")
    assert tax == Decimal("3.90")
    assert total == Decimal("33.90")


def test_calculate_totals_rejects_empty_cart():
    with pytest.raises(DomainError, match="al menos un producto"):
        calculate_totals([], "13")


def test_extract_cart_merges_duplicate_products():
    form = MultiDict([
        ("producto_id", "4"), ("cantidad", "2"),
        ("producto_id", "4"), ("cantidad", "3"),
        ("producto_id", "9"), ("cantidad", "1"),
    ])
    assert extract_cart(form) == [
        {"id_producto": 4, "cantidad": 5},
        {"id_producto": 9, "cantidad": 1},
    ]


def test_extract_cart_rejects_mismatched_arrays():
    with pytest.raises(DomainError, match="lista de productos"):
        extract_cart(MultiDict([("producto_id", "4"), ("cantidad", "1"), ("cantidad", "2")]))


def test_to_money_rejects_non_finite_values():
    with pytest.raises(DomainError):
        to_money("NaN")
