"""Reportes gerenciales y exportación CSV de ventas."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, make_response, render_template, request

from .db import query_db
from .decorators import vendedor_required
from .domain import DomainError

bp = Blueprint("reports", __name__, url_prefix="/reportes")


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DomainError("Las fechas del reporte no son válidas.") from exc


def _date_range() -> tuple[date, date, str, str]:
    today = date.today()
    try:
        date_from = _parse_date(request.args.get("desde"), today - timedelta(days=29))
        date_to = _parse_date(request.args.get("hasta"), today)
    except DomainError as exc:
        date_from, date_to = today - timedelta(days=29), today
        return date_from, date_to, str(exc), ""
    if date_from > date_to:
        return date_from, date_to, "La fecha inicial debe ser anterior a la final.", ""
    return date_from, date_to, "", ""


@bp.get("")
@vendedor_required
def index():
    date_from, date_to, error, _ = _date_range()
    params = (date_from, date_to)
    common = "FROM venta v WHERE v.estado = 'completada' AND v.fecha_venta::date BETWEEN %s AND %s"

    kpis = query_db(
        f"SELECT COUNT(*) AS ventas, COALESCE(SUM(v.total), 0) AS ingresos, "
        f"       COALESCE(AVG(v.total), 0) AS ticket_promedio "
        f"{common}",
        params,
        one=True,
    )
    units = query_db(
        "SELECT COALESCE(SUM(d.cantidad), 0) AS unidades "
        "FROM detalle_venta d JOIN venta v ON v.id_venta = d.id_venta "
        "WHERE v.estado = 'completada' AND v.fecha_venta::date BETWEEN %s AND %s",
        params,
        one=True,
    )["unidades"]

    top_products = query_db(
        "SELECT p.id_producto, p.nombre, m.nombre AS marca, "
        "       SUM(d.cantidad) AS unidades, SUM(d.subtotal) AS ingresos "
        "FROM detalle_venta d "
        "JOIN venta v ON v.id_venta = d.id_venta "
        "JOIN producto p ON p.id_producto = d.id_producto "
        "JOIN marca m ON m.id_marca = p.id_marca "
        "WHERE v.estado = 'completada' AND v.fecha_venta::date BETWEEN %s AND %s "
        "GROUP BY p.id_producto, p.nombre, m.nombre "
        "ORDER BY unidades DESC, ingresos DESC LIMIT 10",
        params,
    )
    by_category = query_db(
        "SELECT c.nombre AS categoria, SUM(d.cantidad) AS unidades, SUM(d.subtotal) AS ingresos "
        "FROM detalle_venta d "
        "JOIN venta v ON v.id_venta = d.id_venta "
        "JOIN producto p ON p.id_producto = d.id_producto "
        "JOIN categoria c ON c.id_categoria = p.id_categoria "
        "WHERE v.estado = 'completada' AND v.fecha_venta::date BETWEEN %s AND %s "
        "GROUP BY c.id_categoria, c.nombre ORDER BY ingresos DESC",
        params,
    )
    by_seller = query_db(
        "SELECT u.id_usuario, u.nombre || ' ' || u.apellido AS vendedor, "
        "       COUNT(v.id_venta) AS ventas, COALESCE(SUM(v.total), 0) AS ingresos "
        "FROM usuario u JOIN venta v ON v.id_vendedor = u.id_usuario "
        "WHERE v.estado = 'completada' AND v.fecha_venta::date BETWEEN %s AND %s "
        "GROUP BY u.id_usuario, u.nombre, u.apellido ORDER BY ingresos DESC",
        params,
    )
    by_payment = query_db(
        "SELECT p.metodo, COUNT(*) AS operaciones, COALESCE(SUM(p.monto), 0) AS ingresos "
        "FROM pago p JOIN venta v ON v.id_venta = p.id_venta "
        "WHERE v.estado = 'completada' AND v.fecha_venta::date BETWEEN %s AND %s "
        "GROUP BY p.metodo ORDER BY ingresos DESC",
        params,
    )
    daily = query_db(
        "SELECT dia::date AS dia, COUNT(v.id_venta) AS ventas, "
        "       COALESCE(SUM(v.total), 0) AS ingresos "
        "FROM generate_series(%s::date, %s::date, INTERVAL '1 day') AS dia "
        "LEFT JOIN venta v ON v.fecha_venta::date = dia::date AND v.estado = 'completada' "
        "GROUP BY dia::date ORDER BY dia::date",
        params,
    )
    return render_template(
        "reports/index.html",
        titulo="Reportes",
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        filter_error=error,
        kpis=kpis,
        units=units,
        top_products=top_products,
        by_category=by_category,
        by_seller=by_seller,
        by_payment=by_payment,
        daily=daily,
    )


@bp.get("/ventas.csv")
@vendedor_required
def export_csv():
    date_from, date_to, _, _ = _date_range()
    rows = query_db(
        "SELECT v.id_venta, v.fecha_venta, "
        "       vendedor.nombre || ' ' || vendedor.apellido AS vendedor, "
        "       COALESCE(cliente.nombre || ' ' || cliente.apellido, 'Cliente de mostrador') AS cliente, "
        "       v.subtotal, v.impuesto, v.total, v.estado, p.metodo "
        "FROM venta v "
        "JOIN usuario vendedor ON vendedor.id_usuario = v.id_vendedor "
        "LEFT JOIN usuario cliente ON cliente.id_usuario = v.id_cliente "
        "LEFT JOIN pago p ON p.id_venta = v.id_venta "
        "WHERE v.estado = 'completada' AND v.fecha_venta::date BETWEEN %s AND %s "
        "ORDER BY v.fecha_venta",
        (date_from, date_to),
    )
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Venta", "Fecha", "Vendedor", "Cliente", "Subtotal", "Impuesto",
        "Total", "Estado", "Método de pago",
    ])
    for row in rows:
        writer.writerow([
            row["id_venta"], row["fecha_venta"].strftime("%Y-%m-%d %H:%M:%S"),
            row["vendedor"], row["cliente"], f"{Decimal(row['subtotal']):.2f}",
            f"{Decimal(row['impuesto']):.2f}", f"{Decimal(row['total']):.2f}",
            row["estado"], row["metodo"],
        ])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=ventas-bears-scourge-{date_from}-{date_to}.csv"
    )
    return response
