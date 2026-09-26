"""Datos de demostración idempotentes para Bear's Scourge."""

from __future__ import annotations

from psycopg2 import IntegrityError
from werkzeug.security import generate_password_hash

from .db import get_db

VENDEDOR_PASSWORD = "Vendedor123!"
CLIENTE_PASSWORD = "Cliente123!"


def _upsert_named(cursor, table: str, name: str, extra_column: str | None = None,
                  extra_value: str | None = None) -> int:
    if extra_column:
        cursor.execute(
            f"INSERT INTO {table} (nombre, {extra_column}) VALUES (%s, %s) "
            f"ON CONFLICT (nombre) DO UPDATE SET {extra_column} = EXCLUDED.{extra_column} "
            "RETURNING id_" + table,
            (name, extra_value),
        )
    else:
        cursor.execute(
            f"INSERT INTO {table} (nombre) VALUES (%s) "
            f"ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre "
            "RETURNING id_" + table,
            (name,),
        )
    return cursor.fetchone()[f"id_{table}"]


def _upsert_user(cursor, data: dict, password: str) -> int:
    cursor.execute(
        "INSERT INTO usuario "
        "(nombre, apellido, correo, contrasena, telefono, direccion, ciudad, rol, estado) "
        "VALUES (%(nombre)s, %(apellido)s, %(correo)s, %(contrasena)s, %(telefono)s, "
        "        %(direccion)s, %(ciudad)s, %(rol)s, TRUE) "
        "ON CONFLICT (correo) DO UPDATE SET nombre = EXCLUDED.nombre, "
        "apellido = EXCLUDED.apellido, telefono = EXCLUDED.telefono, "
        "direccion = EXCLUDED.direccion, ciudad = EXCLUDED.ciudad, "
        "rol = EXCLUDED.rol, estado = TRUE, contrasena = EXCLUDED.contrasena "
        "RETURNING id_usuario",
        {**data, "contrasena": generate_password_hash(password)},
    )
    return cursor.fetchone()["id_usuario"]


def seed_database() -> dict[str, str | int]:
    categories = {
        "Refrigeración": "Refrigeradores, heladeras y freezers.",
        "Cocina": "Hornos, cooktops y electrodomésticos de preparación.",
        "Lavado": "Lavalvadoras, secadoras y equipos de cuidado textil.",
        "Climatización": "Aire acondicionado, ventiladores y dispositivos de climatización.",
        "Pequeños electrodomésticos": "Electrodomésticos para el uso diario.",
    }
    brands = {
        "Samsung": "Corea del Sur",
        "LG": "Corea del Sur",
        "Bosch": "Alemania",
        "Whirlpool": "Estados Unidos",
        "Electrolux": "Suecia",
        "Philips": "Países Bajos",
    }
    products = [
        ("Refrigerador No Frost Samsung 391 L", "RT38K", "Dos puertas, sistema No Frost y control de temperatura.", 4599.00, 8, "Refrigeración", "Samsung"),
        ("Heladera Electrolux Frost Free 420 L", "DF80X", "Heladera inverter con freezer y estantes ajustables.", 4299.00, 5, "Refrigeración", "Electrolux"),
        ("Lavalvadora LG 18 kg Smart Inverter", "F4V5", "Carga frontal, vapor y 14 programas de lavado.", 3299.00, 6, "Lavado", "LG"),
        ("Horno empotrable Bosch 60 L", "HBN5170", "Horno eléctrico con convección y limpieza pirolítica.", 2899.00, 4, "Cocina", "Bosch"),
        ("Cocina Whirlpool 4 hornillas", "WRL500", "Mesa de cocina a gas con cuatro quemadores y horno.", 1899.00, 10, "Cocina", "Whirlpool"),
        ("Aire acondicionado LG 12000 BTU", "S12RW", "Split inverter para ambientes de hasta 30 m².", 3299.00, 7, "Climatización", "LG"),
        ("Microondas Electrolux 20 L", "EMS20", "Microondas compacto con cinco niveles de potencia.", 999.00, 15, "Pequeños electrodomésticos", "Electrolux"),
        ("Aspiradora Philips 2000 W", "VC2232", "Aspiradora PowerfulSuction con bolsa reutilizable.", 1199.00, 12, "Pequeños electrodomésticos", "Philips"),
    ]

    with get_db() as connection:
        with connection.cursor() as cursor:
            category_ids = {
                name: _upsert_named(
                    cursor, "categoria", name,
                    "descripcion", description,
                )
                for name, description in categories.items()
            }
            brand_ids = {
                name: _upsert_named(cursor, "marca", name, "pais_origen", country)
                for name, country in brands.items()
            }

            seller_id = _upsert_user(
                cursor,
                {
                    "nombre": "Joel", "apellido": "Vera", "correo": "vendedor@bears.local",
                    "telefono": "70000001", "direccion": "Av. Principal 100", "ciudad": "Cochabamba",
                    "rol": "vendedor",
                },
                VENDEDOR_PASSWORD,
            )
            client_id = _upsert_user(
                cursor,
                {
                    "nombre": "Andrea", "apellido": "Mendoza", "correo": "cliente@bears.local",
                    "telefono": "70123456", "direccion": "Calle Central 45", "ciudad": "Cochabamba",
                    "rol": "cliente",
                },
                CLIENTE_PASSWORD,
            )
            _upsert_user(
                cursor,
                {
                    "nombre": "Carlos", "apellido": "Reyes", "correo": "carlos@ejemplo.com",
                    "telefono": "70234567", "direccion": None, "ciudad": "La Paz",
                    "rol": "cliente",
                },
                CLIENTE_PASSWORD,
            )

            product_ids: dict[str, int] = {}
            for name, model, description, price, stock, category, brand in products:
                cursor.execute("SELECT id_producto FROM producto WHERE nombre = %s", (name,))
                row = cursor.fetchone()
                if row:
                    product_id = row["id_producto"]
                    cursor.execute(
                        "UPDATE producto SET descripcion = %s, modelo = %s, precio = %s, "
                        "stock = GREATEST(stock, %s), id_categoria = %s, id_marca = %s, estado = TRUE "
                        "WHERE id_producto = %s",
                        (description, model, price, stock, category_ids[category], brand_ids[brand], product_id),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO producto "
                        "(nombre, descripcion, modelo, precio, stock, id_categoria, id_marca) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_producto",
                        (name, description, model, price, stock, category_ids[category], brand_ids[brand]),
                    )
                    product_id = cursor.fetchone()["id_producto"]
                product_ids[name] = product_id

            cursor.execute("SELECT COUNT(*) AS total FROM venta")
            if cursor.fetchone()["total"] == 0:
                sample_sales = [
                    (product_ids["Microondas Electrolux 20 L"], client_id, 1, 999.00, "efectivo", None, 2),
                    (product_ids["Lavalvadora LG 18 kg Smart Inverter"], client_id, 1, 3299.00, "tarjeta_credito", "APROB-1042", 5),
                    (product_ids["Refrigerador No Frost Samsung 391 L"], None, 1, 4599.00, "transferencia", "TRF-8821", 8),
                ]
                for product_id, buyer_id, quantity, unit_price, method, reference, days_ago in sample_sales:
                    subtotal = unit_price * quantity
                    tax = round(subtotal * 0.13, 2)
                    total = subtotal + tax
                    cursor.execute(
                        "INSERT INTO venta "
                        "(id_vendedor, id_cliente, fecha_venta, subtotal, impuesto, total, estado) "
                        "VALUES (%s, %s, CURRENT_TIMESTAMP - (%s * INTERVAL '1 day'), "
                        "        %s, %s, %s, 'completada') RETURNING id_venta",
                        (seller_id, buyer_id, days_ago, subtotal, tax, total),
                    )
                    sale_id = cursor.fetchone()["id_venta"]
                    cursor.execute(
                        "INSERT INTO detalle_venta "
                        "(id_venta, id_producto, cantidad, precio_unitario, subtotal) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (sale_id, product_id, quantity, unit_price, subtotal),
                    )
                    cursor.execute(
                        "INSERT INTO pago "
                        "(id_venta, metodo, monto, estado, referencia, fecha_pago) "
                        "VALUES (%s, %s, %s, 'aprobado', %s, "
                        "        CURRENT_TIMESTAMP - (%s * INTERVAL '1 day'))",
                        (sale_id, method, total, reference, days_ago),
                    )

    return {
        "vendedor_correo": "vendedor@bears.local",
        "vendedor_password": VENDEDOR_PASSWORD,
        "usuario_demo_id": seller_id,
    }
