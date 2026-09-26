"""Autenticación de vendedores. Solo el personal autorizado accede al mostrador."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from .db import query_db
from .utils import full_name

bp = Blueprint("auth", __name__, url_prefix="/auth")


class User(dict):
    """Diccionario de sesión con propiedades similares a Flask-Login."""

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_active(self) -> bool:
        return bool(self.get("estado"))

    @property
    def id(self):
        return self.get("id_usuario")

    def get_id(self):
        return str(self.id)

    def unauthorized(self):
        return redirect(url_for("auth.login", next=request.full_path))


@bp.before_app_request
def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    user = query_db(
        "SELECT id_usuario, nombre, apellido, correo, rol, estado "
        "FROM usuario WHERE id_usuario = %s",
        (user_id,),
        one=True,
    )
    if user is None or not user["estado"]:
        session.clear()
        g.user = None
    else:
        g.user = User(user)


def _safe_next_url(target: str | None) -> str | None:
    if not target:
        return None
    host_url = urlsplit(request.host_url)
    redirect_url = urlsplit(urljoin(request.host_url, target))
    if redirect_url.scheme not in ("http", "https") or host_url.netloc != redirect_url.netloc:
        return None
    return redirect_url.path + ("?" + redirect_url.query if redirect_url.query else "")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if getattr(g, "user", None):
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        contrasena = request.form.get("contrasena", "")
        remember = request.form.get("recordarme") == "on"
        error = None

        if not correo or not contrasena:
            error = "Ingresa tu correo y contraseña."
        else:
            user = query_db(
                "SELECT * FROM usuario WHERE lower(correo) = %s",
                (correo,),
                one=True,
            )
            if user is None or not check_password_hash(user["contrasena"], contrasena):
                error = "Las credenciales son incorrectas."
            elif not user["estado"]:
                error = "Esta cuenta se encuentra inactiva."
            elif user["rol"] != "vendedor":
                error = "Esta cuenta no tiene acceso al punto de venta."

        if error:
            flash(error, "error")
        else:
            session.clear()
            session["user_id"] = user["id_usuario"]
            session.permanent = remember
            destination = _safe_next_url(request.args.get("next"))
            if destination is None:
                destination = url_for("main.dashboard")
            flash(f"Bienvenido, {full_name(user)}.", "success")
            return redirect(destination)

    return render_template("auth/login.html", titulo="Iniciar sesión")


@bp.post("/logout")
def logout():
    session.clear()
    flash("Tu sesión se cerró correctamente.", "success")
    return redirect(url_for("main.home"))
