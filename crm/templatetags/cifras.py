"""
Montos como se escriben en Chile: $1.360.000 y UF 115,50.

El formato regional de Django para es-cl separa los miles con un espacio, y en
el panel se leen con punto, como en cualquier documento chileno.
"""

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _numero(valor, decimales):
    try:
        cifra = Decimal(valor)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    #  Python los escribe 1,360,000.50; en Chile es 1.360.000,50.
    return f"{cifra:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")


@register.filter
def pesos(valor):
    """1360000 -> $1.360.000"""
    numero = _numero(valor, 0)
    return f"${numero}" if numero else ""


@register.filter
def uf(valor):
    """115.5 -> UF 115,50"""
    numero = _numero(valor, 2)
    return f"UF {numero}" if numero else ""
