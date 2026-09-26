"""Servicios transaccionales: registro y anulación de ventas."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from psycopg2 import errors

from .db import get_db
from .domain import (
    PAYMENT_METHODS,
    DomainError,
    calculate_totals,
    parse_tax_rate,
    to_money,
)


class SaleError(DomainError):
    """Error de una operación de venta segura para mostrar en la interfaz."""


def _optional_id(value: Any, field_name: str) -> int | None:
    if value in (None, "", "0"):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SaleError(f"El valor de {field_name} no es válido.") from exc
    if parsed <= 0:
        raise SaleError(f"El valor de {field_name} no es válido.")
    return parsed


def create_sale(
    *,
    seller: Mapping[str, Any],
    cart: list[dict[str, int]],
    client_id: Any,
    delivery_address: str,
    payment_method: str,
    payment_reference: str,
    tax_rate: Any,
) -> dict[str, Any]:
    """Crea venta, detalles, pago y descuento de stock en una sola transacción ACID."""
    if not cart:
        raise SaleError("Agrega al menos un producto al carrito.")
    if payment_method not in PAYMENT_METHODS:
        raise SaleError("Selecciona un método de pago válido.")
    if len(delivery_address) > 200:
        raise SaleError("La dirección de entrega no puede superar 200 caracteres.")
    if len(payment_reference) > 100:
        raise SaleError("La referencia no puede superar 100 caracteres.")

    client_id = _optional_id(client_id, "cliente")
    rate = parse_tax_rate(tax_rate)
    connection = get_db()

    try:
        with connection:
            with connection.cursor() as cursor:
                if client_id is not None:
                    cursor.execute(
                        "SELECT id_usuario FROM usuario "
                        "WHERE id_usuario = %s AND rol = 'cliente' AND estado = TRUE",
                        (client_id,),
                    )
                    if cursor.fetchone() is None:
                        raise SaleError("El cliente seleccionado no existe o está inactivo.")

                product_ids = [item["id_producto"] for item in cart]
                cursor.execute(
                    "SELECT id_producto, nombre, precio, stock, estado "
                    "FROM producto WHERE id_producto = ANY(%s) ORDER BY id_producto FOR UPDATE",
                    (product_ids,),
                )
                products = {row["id_producto"]: row for row in cursor.fetchall()}

                if len(products) != len(product_ids):
                    raise SaleError("Uno de los productos seleccionados ya no está disponible.")

                priced_items: list[dict[str, Any]] = []
                for item in cart:
                    product = products[item["id_producto"]]
                    if not product["estado"]:
                        raise SaleError(f"{product['nombre']} ya no está disponible.")
                    if product["stock"] < item["cantidad"]:
                        available = max(product["stock"], 0)
                        raise SaleError(
                            f"Solo quedan {available} unidades de {product['nombre']}."
                        )
                    priced_items.append(
                        {
                            "id_producto": product["id_producto"],
                            "cantidad": item["cantidad"],
                            "precio_unitario": product["precio"],
                        }
                    )

                subtotal, tax, total = calculate_totals(priced_items, rate)
                cursor.execute(
                    "INSERT INTO venta "
                    "(id_vendedor, id_cliente, subtotal, impuesto, total, direccion_entrega, estado) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 'completada') RETURNING id_venta, fecha_venta",
                    (
                        seller["id_usuario"],
                        client_id,
                        subtotal,
                        tax,
                        total,
                        delivery_address.strip() or None,
                    ),
                )
                sale = cursor.fetchone()

                for item in priced_items:
                    unit_price = to_money(item["precio_unitario"])
                    line_total = (unit_price * item["cantidad"]).quantize(Decimal("0.01"))
                    cursor.execute(
                        "INSERT INTO detalle_venta "
                        "(id_venta, id_producto, cantidad, precio_unitario, subtotal) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (sale["id_venta"], item["id_producto"], item["cantidad"], unit_price, line_total),
                    )

                cursor.execute(
                    "INSERT INTO pago "
                    "(id_venta, metodo, monto, estado, referencia, fecha_pago) "
                    "VALUES (%s, %s, %s, 'aprobado', %s, CURRENT_TIMESTAMP)",
                    (
                        sale["id_venta"],
                        payment_method,
                        total,
                        payment_reference.strip() or None,
                    ),
                )

                return {
                    "id_venta": sale["id_venta"],
                    "fecha_venta": sale["fecha_venta"],
                    "subtotal": subtotal,
                    "impuesto": tax,
                    "total": total,
                }
    except SaleError:
        raise
    except (errors.CheckViolation, errors.ForeignKeyViolation, errors.UniqueViolation) as exc:
        raise SaleError(
            "No se pudo registrar la venta porque uno de los datos dejó de ser válido. "
            "Actualiza el carrito e inténtalo nuevamente."
        ) from exc


def cancel_sale(sale_id: int) -> int:
    """Anula una venta y reembolsa su pago; la base restaura el stock."""
    try:
        with get_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id_venta, estado FROM venta WHERE id_venta = %s FOR UPDATE",
                    (sale_id,),
                )
                sale = cursor.fetchone()
                if sale is None:
                    raise SaleError("La venta solicitada no existe.")
                if sale["estado"] == "anulada":
                    raise SaleError("La venta ya se encuentra anulada.")

                cursor.execute(
                    "UPDATE venta SET estado = 'anulada' WHERE id_venta = %s",
                    (sale_id,),
                )
                cursor.execute(
                    "UPDATE pago SET estado = 'reembolsado' WHERE id_venta = %s",
                    (sale_id,),
                )
        return sale_id
    except SaleError:
        raise
    except (errors.CheckViolation, errors.ForeignKeyViolation) as exc:
        raise SaleError("No se pudo anular la venta.") from exc
