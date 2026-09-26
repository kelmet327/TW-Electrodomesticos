"""Flujo de mostrador: creación, consulta y anulación de ventas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from .db import query_db
from .decorators import vendedor_required
from .domain import DomainError, extract_cart
from .services import SaleError, cancel_sale, create_sale

bp = Blueprint("sales", __name__, url_prefix="/ventas")


def _optional_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise DomainError("Las fechas indicadas no son válidas.") from exc


@bp.get("")
@vendedor_required
def index():
    search = request.args.get("q", "").strip()[:150]
    state = request.args.get("estado", "")
    if state not in ("", "pendiente", "completada", "anulada"):
        state = ""
    try:
        date_from = _optional_date(request.args.get("desde"))
        date_to = _optional_date(request.args.get("hasta"))
    except DomainError as exc:
        flash(str(exc), "error")
        date_from = date_to = None

    page = max(request.args.get("pagina", 1, type=int) or 1, 1)
    per_page = 15
    conditions = [
        "(%s IS NULL OR v.estado = %s)",
        "(%s::date IS NULL OR v.fecha_venta::date >= %s::date)",
        "(%s::date IS NULL OR v.fecha_venta::date <= %s::date)",
        "(%s = '' OR v.id_venta::text ILIKE '%%' || %s || '%%' "
        " OR u.nombre ILIKE '%%' || %s || '%%' OR u.apellido ILIKE '%%' || %s || '%%')",
    ]
    params: list[Any] = [
        state, state,
        date_from, date_from,
        date_to, date_to,
        search, search, search, search,
    ]
    where_sql = " AND ".join(conditions)
    base = (
        "FROM venta v "
        "JOIN usuario u ON u.id_usuario = v.id_vendedor "
        "LEFT JOIN usuario cliente ON cliente.id_usuario = v.id_cliente "
    )
    count = query_db(f"SELECT COUNT(*) AS total {base} WHERE {where_sql}", params, one=True)
    total_pages = max((count["total"] + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    rows = query_db(
        f"SELECT v.id_venta, v.fecha_venta, v.subtotal, v.impuesto, v.total, v.estado, "
        f"       u.nombre || ' ' || u.apellido AS vendedor, "
        f"       CASE WHEN cliente.id_usuario IS NULL THEN 'Cliente de mostrador' "
        f"            ELSE cliente.nombre || ' ' || cliente.apellido END AS cliente, "
        f"       p.metodo AS metodo_pago, COALESCE(SUM(d.cantidad), 0) AS unidades "
        f"{base} "
        f"LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta "
        f"LEFT JOIN pago p ON p.id_venta = v.id_venta "
        f"WHERE {where_sql} "
        f"GROUP BY v.id_venta, u.nombre, u.apellido, cliente.id_usuario, "
        f"         cliente.nombre, cliente.apellido, p.metodo "
        f"ORDER BY v.fecha_venta DESC LIMIT %s OFFSET %s",
        [*params, per_page, (page - 1) * per_page],
    )
    return render_template(
        "sales/index.html",
        titulo="Ventas",
        ventas=rows,
        busqueda=search,
        estado=state,
        fecha_desde=request.args.get("desde", ""),
        fecha_hasta=request.args.get("hasta", ""),
        pagina=page,
        total_paginas=total_pages,
        total=count["total"],
    )


def _pos_context() -> dict[str, Any]:
    return {
        "productos": query_db(
            "SELECT p.id_producto, p.nombre, p.modelo, p.precio, p.stock, p.imagen_url, "
            "       c.nombre AS categoria, m.nombre AS marca "
            "FROM producto p "
            "JOIN categoria c ON c.id_categoria = p.id_categoria "
            "JOIN marca m ON m.id_marca = p.id_marca "
            "WHERE p.estado = TRUE AND c.estado = TRUE AND m.estado = TRUE "
            "ORDER BY c.nombre, p.nombre"
        ),
        "clientes": query_db(
            "SELECT id_usuario, nombre, apellido, correo FROM usuario "
            "WHERE rol = 'cliente' AND estado = TRUE ORDER BY apellido, nombre"
        ),
    }


@bp.route("/nueva", methods=("GET", "POST"))
@vendedor_required
def create():
    if request.method == "POST":
        try:
            cart = extract_cart(request.form)
            sale = create_sale(
                seller=g.user,
                cart=cart,
                client_id=request.form.get("id_cliente"),
                delivery_address=request.form.get("direccion_entrega", "").strip(),
                payment_method=request.form.get("metodo", ""),
                payment_reference=request.form.get("referencia", "").strip(),
                tax_rate=current_app.config["TAX_RATE"],
            )
            flash(
                f"Venta N.° {sale['id_venta']} registrada por {format_money_local(sale['total'])}.",
                "success",
            )
            return redirect(url_for("sales.detail", sale_id=sale["id_venta"]))
        except (DomainError, SaleError) as exc:
            flash(str(exc), "error")
            context = _pos_context()
            context.update(
                titulo="Nueva venta",
                form_data=request.form,
                tax_rate=current_app.config["TAX_RATE"],
            )
            return render_template("sales/create.html", **context), 400

    context = _pos_context()
    context.update(
        titulo="Nueva venta",
        form_data={},
        tax_rate=current_app.config["TAX_RATE"],
    )
    return render_template("sales/create.html", **context)


def format_money_local(value: Any) -> str:
    from .utils import format_money

    return format_money(value)


@bp.get("/<int:sale_id>")
@vendedor_required
def detail(sale_id: int):
    sale = query_db(
        "SELECT v.*, "
        "       vendedor.nombre || ' ' || vendedor.apellido AS vendedor, "
        "       vendedor.correo AS vendedor_correo, "
        "       CASE WHEN cliente.id_usuario IS NULL THEN NULL "
        "            ELSE cliente.nombre || ' ' || cliente.apellido END AS cliente, "
        "       cliente.correo AS cliente_correo, p.metodo, p.estado AS pago_estado, "
        "       p.referencia, p.fecha_pago "
        "FROM venta v "
        "JOIN usuario vendedor ON vendedor.id_usuario = v.id_vendedor "
        "LEFT JOIN usuario cliente ON cliente.id_usuario = v.id_cliente "
        "LEFT JOIN pago p ON p.id_venta = v.id_venta "
        "WHERE v.id_venta = %s",
        (sale_id,),
        one=True,
    )
    if sale is None:
        abort(404)
    details = query_db(
        "SELECT d.*, p.nombre, p.modelo, m.nombre AS marca "
        "FROM detalle_venta d "
        "JOIN producto p ON p.id_producto = d.id_producto "
        "JOIN marca m ON m.id_marca = p.id_marca "
        "WHERE d.id_venta = %s ORDER BY d.id_detalle_venta",
        (sale_id,),
    )
    return render_template("sales/detail.html", titulo=f"Venta N.° {sale_id}", venta=sale, detalles=details)


@bp.post("/<int:sale_id>/anular")
@vendedor_required
def cancel(sale_id: int):
    try:
        cancel_sale(sale_id)
        flash(
            f"La venta N.° {sale_id} fue anulada y las unidades regresaron al inventario.",
            "success",
        )
    except SaleError as exc:
        flash(str(exc), "error")
    return redirect(url_for("sales.detail", sale_id=sale_id))
