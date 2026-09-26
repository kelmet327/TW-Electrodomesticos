import os

import pytest
from psycopg2 import OperationalError

from app import create_app
from app.db import query_db


@pytest.fixture
def database_app():
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
    try:
        with app.app_context():
            query_db("SELECT 1", one=True)
    except OperationalError:
        pytest.skip("PostgreSQL no está disponible para el smoke test")
    yield app


def test_public_catalog_and_health(database_app):
    client = database_app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/auth/login").status_code == 200
    health = client.get("/salud")
    assert health.status_code == 200
    assert health.get_json()["estado"] == "ok"


def test_client_registration_and_purchases_are_gone(database_app):
    client = database_app.test_client()
    assert client.get("/auth/register").status_code == 404
    assert client.get("/mis-compras").status_code == 404


def test_client_account_cannot_log_in(database_app):
    client = database_app.test_client()
    response = client.post(
        "/auth/login",
        data={"correo": "cliente@bears.local", "contrasena": "Cliente123!"},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "no tiene acceso al punto de venta" in body
    # La sesión no quedó abierta: el panel sigue protegido.
    assert client.get("/dashboard").status_code == 302


def test_seller_routes_render_with_seeded_data(database_app):
    client = database_app.test_client()
    response = client.post(
        "/auth/login",
        data={"correo": "vendedor@bears.local", "contrasena": "Vendedor123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Panel de control" in response.get_data(as_text=True)
    for path in ("/ventas/nueva", "/productos", "/inventario", "/catalogos", "/usuarios", "/reportes"):
        assert client.get(path).status_code == 200, path


def test_protected_route_redirects_anonymous_user():
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
    response = app.test_client().get("/ventas")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
