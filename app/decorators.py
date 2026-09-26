"""Decoradores de autorización del POS."""

from functools import wraps

from flask import abort, g, redirect, request, url_for


def vendedor_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = getattr(g, "user", None)
        if user is None or not user.is_authenticated:
            return redirect(url_for("auth.login", next=request.full_path))
        if user.get("rol") != "vendedor":
            abort(403)
        return view(*args, **kwargs)

    return wrapped
