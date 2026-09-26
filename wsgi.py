"""Punto de entrada WSGI para Flask y Apache httpd + mod_wsgi."""

from app import create_app

app = create_app()
