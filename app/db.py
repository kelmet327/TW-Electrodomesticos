"""Conexión PostgreSQL por solicitud y comandos de inicialización."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import click
import psycopg2
import psycopg2.extras
from flask import current_app, g


def get_db():
    """Obtiene una conexión psycopg2 asociada a la solicitud actual."""
    if "db" not in g:
        g.db = psycopg2.connect(
            current_app.config["DATABASE_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return g.db


def close_db(error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is None:
        return
    if error is not None:
        connection.rollback()
    connection.close()


def query_db(query: str, params: Sequence[Any] | dict[str, Any] | None = None,
             one: bool = False):
    with get_db().cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute_db(query: str, params: Sequence[Any] | dict[str, Any] | None = None) -> int:
    with get_db().cursor() as cursor:
        cursor.execute(query, params)
        return cursor.rowcount


def _schema_path() -> Path:
    return Path(current_app.root_path).parent / "sql" / "schema.sql"


@click.command("init-db")
def init_db_command() -> None:
    """Crea las tablas, restricciones, índices y disparadores del POS."""
    schema = _schema_path().read_text(encoding="utf-8")
    connection = psycopg2.connect(current_app.config["DATABASE_URL"])
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(schema)
        click.echo("Base de datos inicializada correctamente.")
    except psycopg2.Error as exc:
        connection.rollback()
        raise click.ClickException(f"No se pudo inicializar la base de datos: {exc}") from exc
    finally:
        connection.close()


@click.command("seed-db")
def seed_db_command() -> None:
    """Carga datos iniciales idempotentes y usuarios de demostración."""
    from .seed import seed_database

    try:
        result = seed_database()
    except psycopg2.Error as exc:
        get_db().rollback()
        raise click.ClickException(f"No se pudieron cargar los datos: {exc}") from exc
    click.echo(
        "Datos de demostración listos. "
        f"Vendedor: {result['vendedor_correo']} / {result['vendedor_password']}. "
        "Las fichas de cliente se administran desde el panel de usuarios."
    )


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)
