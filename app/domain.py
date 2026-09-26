"""Reglas de negocio puras y validaciones reutilizables del POS."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

CENT = Decimal("0.01")
MAX_QUANTITY = 999

PAYMENT_METHODS = {
    "tarjeta_credito": "Tarjeta de crédito",
    "tarjeta_debito": "Tarjeta de débito",
    "transferencia": "Transferencia",
    "efectivo": "Efectivo",
    "paypal": "PayPal",
}

SALE_STATES = {
    "pendiente": "Pendiente",
    "completada": "Completada",
    "anulada": "Anulada",
}

PAYMENT_STATES = {
    "pendiente": "Pendiente",
    "aprobado": "Aprobado",
    "rechazado": "Rechazado",
    "reembolsado": "Reembolsado",
}


class DomainError(ValueError):
    """Error de validación que puede mostrarse al usuario."""


def to_money(value: Any) -> Decimal:
    """Convierte un valor a Decimal monetario con dos decimales."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DomainError("El importe ingresado no es válido.") from exc
    if not amount.is_finite():
        raise DomainError("El importe ingresado no es válido.")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_tax_rate(value: Any) -> Decimal:
    """Acepta 13 como porcentaje o 0.13 como fracción."""
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DomainError("La tasa de impuesto configurada no es válida.") from exc
    rate = raw / Decimal("100") if raw > 1 else raw
    if rate < 0 or rate > 1:
        raise DomainError("La tasa de impuesto debe estar entre 0 y 100 %.")
    return rate


def calculate_totals(
    items: Iterable[Mapping[str, Any]], tax_rate: Any
) -> tuple[Decimal, Decimal, Decimal]:
    """Calcula subtotal, impuesto y total a partir de líneas confiables del servidor."""
    rate = parse_tax_rate(tax_rate)
    subtotal = Decimal("0.00")
    for item in items:
        quantity = int(item["cantidad"])
        unit_price = to_money(item["precio_unitario"])
        if quantity <= 0 or quantity > MAX_QUANTITY:
            raise DomainError("Las cantidades deben estar entre 1 y 999.")
        if unit_price < 0:
            raise DomainError("Los precios no pueden ser negativos.")
        subtotal += (unit_price * quantity).quantize(CENT, rounding=ROUND_HALF_UP)

    if subtotal <= 0:
        raise DomainError("La venta debe incluir al menos un producto.")
    if subtotal > Decimal("99999999.99"):
        raise DomainError("El subtotal supera el límite permitido.")

    tax = (subtotal * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    total = (subtotal + tax).quantize(CENT, rounding=ROUND_HALF_UP)
    return subtotal, tax, total


def extract_cart(form: Mapping[str, Any]) -> list[dict[str, int]]:
    """Lee y normaliza los campos productos[] y cantidades[] del formulario POS."""
    product_ids = form.getlist("producto_id")
    quantities = form.getlist("cantidad")

    if not product_ids or len(product_ids) != len(quantities):
        raise DomainError("El carrito no contiene una lista de productos válida.")

    cart: dict[int, int] = {}
    for raw_id, raw_quantity in zip(product_ids, quantities, strict=True):
        try:
            product_id = int(raw_id)
            quantity = int(raw_quantity)
        except (TypeError, ValueError) as exc:
            raise DomainError("El carrito contiene datos no válidos.") from exc
        if product_id <= 0:
            raise DomainError("El carrito contiene un producto no válido.")
        if quantity <= 0 or quantity > MAX_QUANTITY:
            raise DomainError("Las cantidades deben estar entre 1 y 999.")
        cart[product_id] = min(MAX_QUANTITY, cart.get(product_id, 0) + quantity)

    if not cart:
        raise DomainError("Agrega al menos un producto al carrito.")
    return [
        {"id_producto": product_id, "cantidad": quantity}
        for product_id, quantity in cart.items()
    ]
