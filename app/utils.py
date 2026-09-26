"""Utilidades de presentación sin acoplamiento a la base de datos."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping


def format_money(value: Any) -> str:
    try:
        amount = Decimal(str(value or 0))
    except Exception:
        amount = Decimal("0")
    return f"Bs. {amount:,.2f}"


def format_date(value: date | datetime | None, with_time: bool = False) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime) and with_time:
        return value.strftime("%d/%m/%Y %H:%M")
    return value.strftime("%d/%m/%Y")


def full_name(user: Mapping[str, Any] | None) -> str:
    if not user:
        return "Usuario"
    return f"{user.get('nombre', '')} {user.get('apellido', '')}".strip()
