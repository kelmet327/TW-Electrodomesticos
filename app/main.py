"""Páginas públicas, panel principal y estado del sistema."""

from flask import Blueprint, current_app, jsonify, render_template, request

from .db import query_db
from .decorators import vendedor_required

bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    search = request.args.get("q", "").strip()[:150]
    category_id = request.args.get("categoria", "").strip()

    categories = query_db(
        "SELECT id_categoria, nombre FROM categoria "
        "WHERE estado = TRUE ORDER BY nombre"
    )
    products = query_db(
        "SELECT p.id_producto, p.nombre, p.descripcion, p.modelo, p.precio, p.stock, "
        "       p.imagen_url, c.nombre AS categoria, m.nombre AS marca "
        "FROM producto p "
        "JOIN categoria c ON c.id_categoria = p.id_categoria "
        "JOIN marca m ON m.id_marca = p.id_marca "
        "WHERE p.estado = TRUE AND c.estado = TRUE AND m.estado = TRUE "
        "  AND (%s = '' OR p.nombre ILIKE '%%' || %s || '%%' "
        "       OR m.nombre ILIKE '%%' || %s || '%%') "
        "  AND (%s = '' OR p.id_categoria::text = %s) "
        "ORDER BY p.nombre LIMIT 48",
        (search, search, search, category_id, category_id),
    )
    return render_template(
        "main/home.html",
        titulo="Electrodomésticos para tu hogar",
        productos=products,
        categorias=categories,
        busqueda=search,
        categoria_seleccionada=category_id,
    )


@bp.get("/salud")
def health():
    try:
        query_db("SELECT 1 AS ok", one=True)
        return jsonify({"estado": "ok", "servicio": current_app.config["APP_NAME"]})
    except Exception:
        return jsonify({"estado": "error"}), 503


@bp.get("/dashboard")
@vendedor_required
def dashboard():
    daily = query_db(
        "SELECT COUNT(*) AS ventas, COALESCE(SUM(total), 0) AS ingresos "
        "FROM venta WHERE estado = 'completada' AND fecha_venta::date = CURRENT_DATE",
        one=True,
    )
    inventory = query_db(
        "SELECT COUNT(*) AS productos, "
        "       COUNT(*) FILTER (WHERE stock = 0) AS agotados, "
        "       COUNT(*) FILTER (WHERE stock BETWEEN 1 AND 10) AS stock_bajo "
        "FROM producto WHERE estado = TRUE",
        one=True,
    )
    recent_sales = query_db(
        "SELECT v.id_venta, v.fecha_venta, v.total, v.estado, "
        "       u.nombre || ' ' || u.apellido AS vendedor, "
        "       COALESCE(SUM(d.cantidad), 0) AS unidades "
        "FROM venta v "
        "JOIN usuario u ON u.id_usuario = v.id_vendedor "
        "LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta "
        "GROUP BY v.id_venta, u.nombre, u.apellido "
        "ORDER BY v.fecha_venta DESC LIMIT 8",
    )
    low_stock = query_db(
        "SELECT p.id_producto, p.nombre, p.stock, "
        "       m.nombre AS marca "
        "FROM producto p JOIN marca m ON m.id_marca = p.id_marca "
        "WHERE p.estado = TRUE AND p.stock <= 10 "
        "ORDER BY p.stock, p.nombre LIMIT 8",
    )
    top_products = query_db(
        "SELECT p.id_producto, p.nombre, SUM(d.cantidad) AS unidades, "
        "       SUM(d.subtotal) AS ingresos "
        "FROM detalle_venta d "
        "JOIN venta v ON v.id_venta = d.id_venta "
        "JOIN producto p ON p.id_producto = d.id_producto "
        "WHERE v.estado = 'completada' AND v.fecha_venta >= CURRENT_DATE - INTERVAL '30 days' "
        "GROUP BY p.id_producto, p.nombre "
        "ORDER BY unidades DESC, ingresos DESC LIMIT 5",
    )
    return render_template(
        "main/dashboard.html",
        titulo="Panel de control",
        daily=daily,
        inventory=inventory,
        recent_sales=recent_sales,
        low_stock=low_stock,
        top_products=top_products,
    )
