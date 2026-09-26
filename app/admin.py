"""Gestión de catálogo, inventario y usuarios del POS."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin, urlparse, urlsplit

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from psycopg2 import IntegrityError

from .db import get_db, query_db
from .decorators import vendedor_required
from .domain import DomainError, to_money

bp = Blueprint("admin", __name__)


def _text(form, field: str, max_length: int, *, required: bool = False,
          nullable: bool = True) -> str | None:
    value = form.get(field, "").strip()
    if required and not value:
        raise DomainError(f"El campo {field.replace('_', ' ')} es obligatorio.")
    if len(value) > max_length:
        raise DomainError(
            f"El campo {field.replace('_', ' ')} no puede superar {max_length} caracteres."
        )
    return value or (None if nullable else value)


def _positive_int(value: str, field: str, *, allow_zero: bool = False) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DomainError(f"{field} debe ser un número entero.") from exc
    lower = 0 if allow_zero else 1
    if parsed < lower:
        raise DomainError(f"{field} no tiene un valor válido.")
    if parsed > 2_147_483_647:
        raise DomainError(f"{field} supera el valor permitido.")
    return parsed


def _valid_image_url(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) > 255:
        raise DomainError("La URL de imagen no puede superar 255 caracteres.")
    if value.startswith("/static/"):
        return value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise DomainError("La URL de imagen debe comenzar con http:// o https://.")
    return value


def _redirect_back(default_endpoint: str, **values):
    endpoint = request.form.get("volver") or request.referrer
    if endpoint:
        host = urlsplit(request.host_url)
        target = urlsplit(urljoin(request.host_url, endpoint))
        if target.scheme in ("http", "https") and target.netloc == host.netloc:
            return redirect(target.geturl())
    return redirect(url_for(default_endpoint, **values))


@bp.get("/productos")
@vendedor_required
def products():
    search = request.args.get("q", "").strip()[:150]
    category = request.args.get("categoria", "").strip()
    brand = request.args.get("marca", "").strip()
    status = request.args.get("estado", "todos")
    page = max(request.args.get("pagina", 1, type=int) or 1, 1)
    per_page = 15

    conditions = [
        "(%s = '' OR p.nombre ILIKE '%%' || %s || '%%' OR p.modelo ILIKE '%%' || %s || '%%')",
        "(%s = '' OR p.id_categoria::text = %s)",
        "(%s = '' OR p.id_marca::text = %s)",
        "(%s = 'todos' OR (%s = 'activos' AND p.estado = TRUE) "
        "OR (%s = 'inactivos' AND p.estado = FALSE))",
    ]
    params: list[Any] = [
        search, search, search, category, category, brand, brand,
        status, status, status,
    ]
    where_sql = " AND ".join(conditions)
    count = query_db(
        f"SELECT COUNT(*) AS total FROM producto p WHERE {where_sql}", params, one=True
    )
    total_pages = max((count["total"] + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    rows = query_db(
        f"SELECT p.*, c.nombre AS categoria, m.nombre AS marca, "
        f"       COUNT(DISTINCT d.id_venta) AS ventas_count "
        f"FROM producto p "
        f"JOIN categoria c ON c.id_categoria = p.id_categoria "
        f"JOIN marca m ON m.id_marca = p.id_marca "
        f"LEFT JOIN detalle_venta d ON d.id_producto = p.id_producto "
        f"WHERE {where_sql} "
        f"GROUP BY p.id_producto, c.nombre, m.nombre "
        f"ORDER BY p.estado DESC, p.nombre LIMIT %s OFFSET %s",
        [*params, per_page, offset],
    )
    return render_template(
        "admin/products.html",
        titulo="Productos",
        productos=rows,
        categorias=query_db("SELECT * FROM categoria ORDER BY nombre"),
        marcas=query_db("SELECT * FROM marca ORDER BY nombre"),
        busqueda=search,
        categoria=category,
        marca=brand,
        estado=status,
        pagina=page,
        total_paginas=total_pages,
        total=count["total"],
    )


def _product_payload(form) -> dict[str, Any]:
    try:
        nombre = _text(form, "nombre", 150, required=True, nullable=False)
        precio = to_money(_text(form, "precio", 30, required=True, nullable=False))
        if precio > Decimal("99999999.99"):
            raise DomainError("El precio supera el límite permitido.")
        return {
            "nombre": nombre,
            "descripcion": _text(form, "descripcion", 5000),
            "modelo": _text(form, "modelo", 80),
            "precio": precio,
            "stock": _positive_int(form.get("stock", "0"), "El stock", allow_zero=True),
            "imagen_url": _valid_image_url(_text(form, "imagen_url", 255)),
            "id_categoria": _positive_int(form.get("id_categoria", ""), "La categoría"),
            "id_marca": _positive_int(form.get("id_marca", ""), "La marca"),
            "estado": form.get("estado") == "on",
        }
    except DomainError:
        raise
    except InvalidOperation as exc:
        raise DomainError("El precio ingresado no es válido.") from exc


@bp.route("/productos/nuevo", methods=("GET", "POST"))
@vendedor_required
def product_create():
    if request.method == "POST":
        try:
            data = _product_payload(request.form)
            with get_db() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO producto "
                        "(nombre, descripcion, modelo, precio, stock, imagen_url, "
                        " id_categoria, id_marca, estado) "
                        "VALUES (%(nombre)s, %(descripcion)s, %(modelo)s, %(precio)s, "
                        "        %(stock)s, %(imagen_url)s, %(id_categoria)s, "
                        "        %(id_marca)s, %(estado)s) RETURNING id_producto",
                        data,
                    )
                    product_id = cursor.fetchone()["id_producto"]
            flash("El producto fue creado correctamente.", "success")
            return redirect(url_for("admin.product_edit", product_id=product_id))
        except (DomainError, IntegrityError) as exc:
            flash(str(exc) if isinstance(exc, DomainError) else "No se pudo crear el producto.", "error")
    return render_template(
        "admin/product_form.html",
        titulo="Nuevo producto",
        producto=None,
        categorias=query_db("SELECT * FROM categoria WHERE estado = TRUE ORDER BY nombre"),
        marcas=query_db("SELECT * FROM marca WHERE estado = TRUE ORDER BY nombre"),
    )


@bp.route("/productos/<int:product_id>/editar", methods=("GET", "POST"))
@vendedor_required
def product_edit(product_id: int):
    producto = query_db("SELECT * FROM producto WHERE id_producto = %s", (product_id,), one=True)
    if producto is None:
        abort(404)

    if request.method == "POST":
        try:
            data = _product_payload(request.form)
            data["id_producto"] = product_id
            with get_db() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE producto SET nombre = %(nombre)s, descripcion = %(descripcion)s, "
                        "modelo = %(modelo)s, precio = %(precio)s, stock = %(stock)s, "
                        "imagen_url = %(imagen_url)s, id_categoria = %(id_categoria)s, "
                        "id_marca = %(id_marca)s, estado = %(estado)s "
                        "WHERE id_producto = %(id_producto)s",
                        data,
                    )
            flash("Los cambios del producto fueron guardados.", "success")
            return redirect(url_for("admin.products"))
        except (DomainError, IntegrityError) as exc:
            flash(str(exc) if isinstance(exc, DomainError) else "No se pudo guardar el producto.", "error")
    return render_template(
        "admin/product_form.html",
        titulo="Editar producto",
        producto=producto,
        categorias=query_db("SELECT * FROM categoria ORDER BY nombre"),
        marcas=query_db("SELECT * FROM marca ORDER BY nombre"),
    )


@bp.post("/productos/<int:product_id>/estado")
@vendedor_required
def product_toggle(product_id: int):
    row = query_db(
        "UPDATE producto SET estado = NOT estado WHERE id_producto = %s RETURNING estado",
        (product_id,),
        one=True,
    )
    if row is None:
        abort(404)
    with get_db():
        pass
    flash("El estado del producto fue actualizado.", "success")
    return _redirect_back("admin.products")


@bp.get("/inventario")
@vendedor_required
def inventory():
    search = request.args.get("q", "").strip()[:150]
    stock_filter = request.args.get("stock", "todos")
    rows = query_db(
        "SELECT p.id_producto, p.nombre, p.modelo, p.stock, p.precio, p.estado, "
        "       c.nombre AS categoria, m.nombre AS marca "
        "FROM producto p "
        "JOIN categoria c ON c.id_categoria = p.id_categoria "
        "JOIN marca m ON m.id_marca = p.id_marca "
        "WHERE (%s = '' OR p.nombre ILIKE '%%' || %s || '%%' OR m.nombre ILIKE '%%' || %s || '%%') "
        "  AND (%s = 'todos' OR p.estado = TRUE) "
        "  AND (%s = 'todos' OR (%s = 'agotado' AND p.stock = 0) "
        "       OR (%s = 'bajo' AND p.stock BETWEEN 1 AND 10) "
        "       OR (%s = 'disponible' AND p.stock > 10)) "
        "ORDER BY p.stock, p.nombre",
        (search, search, search, stock_filter, stock_filter, stock_filter, stock_filter, stock_filter),
    )
    summary = query_db(
        "SELECT COUNT(*) AS total, "
        "       COUNT(*) FILTER (WHERE stock = 0) AS agotados, "
        "       COUNT(*) FILTER (WHERE stock BETWEEN 1 AND 10) AS bajos, "
        "       COALESCE(SUM(stock), 0) AS unidades "
        "FROM producto WHERE estado = TRUE",
        one=True,
    )
    return render_template(
        "admin/inventory.html",
        titulo="Inventario",
        productos=rows,
        resumen=summary,
        busqueda=search,
        stock_filter=stock_filter,
    )


@bp.post("/inventario/<int:product_id>/ajustar")
@vendedor_required
def inventory_adjust(product_id: int):
    try:
        action = request.form.get("accion")
        quantity = _positive_int(
            request.form.get("cantidad", ""), "La cantidad", allow_zero=action == "establecer"
        )
        with get_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT stock, nombre FROM producto WHERE id_producto = %s FOR UPDATE",
                    (product_id,),
                )
                product = cursor.fetchone()
                if product is None:
                    raise DomainError("El producto no existe.")
                old_stock = product["stock"]
                if action == "entrada":
                    new_stock = old_stock + quantity
                elif action == "salida":
                    new_stock = old_stock - quantity
                elif action == "establecer":
                    new_stock = quantity
                else:
                    raise DomainError("Selecciona un tipo de ajuste válido.")
                if new_stock < 0:
                    raise DomainError("El ajuste dejaría el stock en un valor negativo.")
                cursor.execute(
                    "UPDATE producto SET stock = %s WHERE id_producto = %s",
                    (new_stock, product_id),
                )
        reason = request.form.get("motivo", "").strip()
        suffix = f" Motivo: {reason}" if reason else ""
        flash(
            f"Stock de {product['nombre']} ajustado de {old_stock} a {new_stock}.{suffix}",
            "success",
        )
    except DomainError as exc:
        flash(str(exc), "error")
    return _redirect_back("admin.inventory")


@bp.get("/catalogos")
@vendedor_required
def catalogs():
    categorias = query_db(
        "SELECT c.*, COUNT(p.id_producto) AS productos_count "
        "FROM categoria c LEFT JOIN producto p ON p.id_categoria = c.id_categoria "
        "GROUP BY c.id_categoria ORDER BY c.nombre"
    )
    marcas = query_db(
        "SELECT m.*, COUNT(p.id_producto) AS productos_count "
        "FROM marca m LEFT JOIN producto p ON p.id_marca = p.id_marca "
        "GROUP BY m.id_marca ORDER BY m.nombre"
    )
    return render_template(
        "admin/catalogs.html", titulo="Categorías y marcas",
        categorias=categorias, marcas=marcas
    )


@bp.post("/catalogos/categoria")
@vendedor_required
def category_create():
    try:
        nombre = _text(request.form, "nombre", 80, required=True, nullable=False)
        descripcion = _text(request.form, "descripcion", 255)
        with get_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO categoria (nombre, descripcion) VALUES (%s, %s)",
                    (nombre, descripcion),
                )
        flash("La categoría fue agregada.", "success")
    except (DomainError, IntegrityError) as exc:
        flash(str(exc) if isinstance(exc, DomainError) else "Ya existe una categoría con ese nombre.", "error")
    return _redirect_back("admin.catalogs")


@bp.post("/catalogos/marca")
@vendedor_required
def brand_create():
    try:
        nombre = _text(request.form, "nombre", 80, required=True, nullable=False)
        pais_origen = _text(request.form, "pais_origen", 80)
        with get_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO marca (nombre, pais_origen) VALUES (%s, %s)",
                    (nombre, pais_origen),
                )
        flash("La marca fue agregada.", "success")
    except (DomainError, IntegrityError) as exc:
        flash(str(exc) if isinstance(exc, DomainError) else "Ya existe una marca con ese nombre.", "error")
    return _redirect_back("admin.catalogs")


@bp.post("/catalogos/categoria/<int:category_id>/estado")
@vendedor_required
def category_toggle(category_id: int):
    row = query_db(
        "UPDATE categoria SET estado = NOT estado WHERE id_categoria = %s RETURNING estado",
        (category_id,), one=True,
    )
    if row is None:
        abort(404)
    with get_db():
        pass
    flash("El estado de la categoría fue actualizado.", "success")
    return _redirect_back("admin.catalogs")


@bp.post("/catalogos/marca/<int:brand_id>/estado")
@vendedor_required
def brand_toggle(brand_id: int):
    row = query_db(
        "UPDATE marca SET estado = NOT estado WHERE id_marca = %s RETURNING estado",
        (brand_id,), one=True,
    )
    if row is None:
        abort(404)
    with get_db():
        pass
    flash("El estado de la marca fue actualizado.", "success")
    return _redirect_back("admin.catalogs")


@bp.get("/usuarios")
@vendedor_required
def users():
    search = request.args.get("q", "").strip()[:150]
    role = request.args.get("rol", "")
    status = request.args.get("estado", "todos")
    rows = query_db(
        "SELECT id_usuario, nombre, apellido, correo, telefono, ciudad, rol, estado, fecha_registro, "
        "       (SELECT COUNT(*) FROM venta WHERE id_vendedor = usuario.id_usuario) AS ventas_count "
        "FROM usuario "
        "WHERE (%s = '' OR nombre ILIKE '%%' || %s || '%%' OR apellido ILIKE '%%' || %s || '%%' "
        "       OR correo ILIKE '%%' || %s || '%%') "
        "  AND (%s = '' OR rol = %s) "
        "  AND (%s = 'todos' OR (%s = 'activos' AND estado = TRUE) "
        "       OR (%s = 'inactivos' AND estado = FALSE)) "
        "ORDER BY estado DESC, nombre, apellido",
        (search, search, search, search, role, role, status, status, status),
    )
    summary = query_db(
        "SELECT COUNT(*) FILTER (WHERE rol = 'vendedor' AND estado) AS vendedores, "
        "       COUNT(*) FILTER (WHERE rol = 'cliente' AND estado) AS clientes, "
        "       COUNT(*) FILTER (WHERE NOT estado) AS inactivos "
        "FROM usuario",
        one=True,
    )
    return render_template(
        "admin/users.html", titulo="Usuarios", usuarios=rows,
        resumen=summary, busqueda=search, rol=role, estado=status
    )


def _validated_email(value: str) -> str:
    try:
        result = validate_email(value, check_deliverability=False)
    except EmailNotValidError as exc:
        raise DomainError("Ingresa un correo electrónico válido.") from exc
    if len(result.normalized) > 120:
        raise DomainError("El correo no puede superar 120 caracteres.")
    return result.normalized.lower()


def _user_payload(form, user_id: int | None) -> tuple[dict[str, Any], str | None]:
    try:
        nombre = _text(form, "nombre", 60, required=True, nullable=False)
        apellido = _text(form, "apellido", 60, required=True, nullable=False)
        correo = _validated_email(form.get("correo", "").strip().lower())
        rol = form.get("rol", "")
        if rol not in ("vendedor", "cliente"):
            raise DomainError("Selecciona un rol válido.")
        if user_id == g.user.id and rol != "vendedor":
            raise DomainError("No puedes quitarte a ti mismo el rol de vendedor.")
        password = form.get("contrasena", "")
        if user_id is None and len(password) < 8:
            raise DomainError("La contraseña debe tener al menos 8 caracteres.")
        if password and len(password) < 8:
            raise DomainError("La contraseña debe tener al menos 8 caracteres.")
        data = {
            "id_usuario": user_id,
            "nombre": nombre,
            "apellido": apellido,
            "correo": correo,
            "telefono": _text(form, "telefono", 20),
            "direccion": _text(form, "direccion", 200),
            "ciudad": _text(form, "ciudad", 80),
            "rol": rol,
            "estado": form.get("estado") == "on",
        }
        return data, password or None
    except DomainError:
        raise
    except EmailNotValidError as exc:
        raise DomainError("Ingresa un correo electrónico válido.") from exc


@bp.route("/usuarios/nuevo", methods=("GET", "POST"))
@vendedor_required
def user_create():
    if request.method == "POST":
        try:
            data, password = _user_payload(request.form, None)
            data["contrasena"] = generate_user_password(password)
            with get_db() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO usuario "
                        "(nombre, apellido, correo, contrasena, telefono, direccion, ciudad, rol, estado) "
                        "VALUES (%(nombre)s, %(apellido)s, %(correo)s, %(contrasena)s, "
                        "        %(telefono)s, %(direccion)s, %(ciudad)s, %(rol)s, %(estado)s) "
                        "RETURNING id_usuario",
                        data,
                    )
                    user_id = cursor.fetchone()["id_usuario"]
            flash("El usuario fue creado correctamente.", "success")
            return redirect(url_for("admin.users"))
        except (DomainError, IntegrityError) as exc:
            flash(str(exc) if isinstance(exc, DomainError) else "No se pudo guardar el usuario. Revisa el correo y el rol.", "error")
    return render_template(
        "admin/user_form.html", titulo="Nuevo usuario", usuario=None,
        roles={"vendedor": "Vendedor", "cliente": "Cliente"}
    )


@bp.route("/usuarios/<int:user_id>/editar", methods=("GET", "POST"))
@vendedor_required
def user_edit(user_id: int):
    usuario = query_db(
        "SELECT * FROM usuario WHERE id_usuario = %s", (user_id,), one=True
    )
    if usuario is None:
        abort(404)
    if request.method == "POST":
        try:
            data, password = _user_payload(request.form, user_id)
            with get_db() as connection:
                with connection.cursor() as cursor:
                    if password:
                        cursor.execute(
                            "UPDATE usuario SET nombre = %(nombre)s, apellido = %(apellido)s, "
                            "correo = %(correo)s, telefono = %(telefono)s, "
                            "direccion = %(direccion)s, ciudad = %(ciudad)s, rol = %(rol)s, "
                            "estado = %(estado)s, contrasena = %(contrasena)s "
                            "WHERE id_usuario = %(id_usuario)s",
                            {**data, "contrasena": generate_user_password(password)},
                        )
                    else:
                        cursor.execute(
                            "UPDATE usuario SET nombre = %(nombre)s, apellido = %(apellido)s, "
                            "correo = %(correo)s, telefono = %(telefono)s, "
                            "direccion = %(direccion)s, ciudad = %(ciudad)s, rol = %(rol)s, "
                            "estado = %(estado)s WHERE id_usuario = %(id_usuario)s",
                            data,
                        )
            flash("Los datos del usuario fueron actualizados.", "success")
            return redirect(url_for("admin.users"))
        except (DomainError, IntegrityError) as exc:
            flash(str(exc) if isinstance(exc, DomainError) else "No se pudo guardar el usuario. Revisa el correo y el rol.", "error")
    return render_template(
        "admin/user_form.html", titulo="Editar usuario", usuario=usuario,
        roles={"vendedor": "Vendedor", "cliente": "Cliente"}
    )


def generate_user_password(password: str) -> str:
    """Se mantiene separado para que las operaciones de escritura sean explícitas."""
    from werkzeug.security import generate_password_hash

    return generate_password_hash(password)


@bp.post("/usuarios/<int:user_id>/estado")
@vendedor_required
def user_toggle(user_id: int):
    if user_id == g.user.id:
        flash("No puedes desactivar tu propia cuenta.", "error")
        return _redirect_back("admin.users")
    row = query_db(
        "UPDATE usuario SET estado = NOT estado WHERE id_usuario = %s RETURNING estado",
        (user_id,), one=True,
    )
    if row is None:
        abort(404)
    with get_db():
        pass
    flash("El estado de la cuenta fue actualizado.", "success")
    return _redirect_back("admin.users")
