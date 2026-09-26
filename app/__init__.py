"""Factory de la aplicación Flask de Bear's Scourge."""

from __future__ import annotations

import os
from datetime import date, timedelta

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

from .domain import PAYMENT_METHODS, PAYMENT_STATES, SALE_STATES
from .utils import format_date, format_money, full_name


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        APP_NAME="Bear's Scourge",
        SECRET_KEY=os.getenv("SECRET_KEY", "desarrollo-cambiar-esta-clave"),
        DATABASE_URL=os.getenv(
            "DATABASE_URL",
            "postgresql://bears:bears_password@localhost:5432/bears_scourge",
        ),
        TAX_RATE=os.getenv("TAX_RATE", "13"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    csrf = CSRFProtect(app)

    from . import admin, auth, main, reports, sales
    from .db import init_app as init_db_app

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(sales.bp)
    app.register_blueprint(reports.bp)
    init_db_app(app)

    @app.context_processor
    def inject_helpers() -> dict:
        return {
            "app_name": "Bear's Scourge",
            "current_year": date.today().year,
            "format_money": format_money,
            "format_date": format_date,
            "full_name": full_name,
            "payment_methods": PAYMENT_METHODS,
            "payment_states": PAYMENT_STATES,
            "sale_states": SALE_STATES,
        }

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/error.html", code=400, title="Solicitud incorrecta",
                               message="Revisa los datos enviados e inténtalo nuevamente."), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/error.html", code=403, title="Acceso denegado",
                               message="No tienes permisos para realizar esta acción."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/error.html", code=404, title="Página no encontrada",
                               message="La página solicitada no existe o fue movida."), 404

    @app.errorhandler(413)
    def request_too_large(error):
        return render_template("errors/error.html", code=413, title="Contenido demasiado grande",
                               message="El archivo o formulario enviado supera el límite permitido."), 413

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("errors/error.html", code=500, title="Error interno",
                               message="Ocurrió un problema inesperado. Inténtalo nuevamente."), 500

    return app
