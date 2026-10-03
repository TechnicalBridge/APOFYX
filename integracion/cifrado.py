"""
Los secretos que APOFYX tiene que poder leer de vuelta.

Son tres: la clave que DataBridge le emitio a APOFYX (hay que PRESENTARLA en
cada llamada), el secreto con que DataBridge firma sus avisos (hay que
verificar con el) y el secreto con que APOFYX firma los avisos a sus clientes
(hay que FIRMAR con el). Una huella no sirve para ninguna de las tres cosas, asi
que se guardan cifrados con AES-256-GCM. La llave viene de CIFRADO_LLAVE y nunca
toca la base: quien se lleve un respaldo no se lleva los secretos.

Un valor cifrado empieza con "enc:v1:", seguido de base64(iv | etiqueta |
cifrado). Uno sin ese prefijo es de antes de cifrar: se lee tal cual, y la
migracion 0007 los cifra.
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import models

PREFIJO = "enc:v1:"


def _llave():
    return hashlib.sha256(settings.CIFRADO_LLAVE.encode()).digest()


def esta_cifrado(valor):
    return isinstance(valor, str) and valor.startswith(PREFIJO)


def cifrar(valor):
    """El valor cifrado. Vacio o ya cifrado, se devuelve igual."""
    if not valor or esta_cifrado(valor):
        return valor
    iv = os.urandom(12)
    #  AESGCM deja la etiqueta al final; se guarda delante del cifrado, como
    #  en Patrimonio y DataBridge.
    sellado = AESGCM(_llave()).encrypt(iv, str(valor).encode(), None)
    return PREFIJO + base64.b64encode(iv + sellado[-16:] + sellado[:-16]).decode()


def descifrar(valor):
    """El valor original. Si no estaba cifrado, se devuelve igual."""
    if not esta_cifrado(valor):
        return valor
    datos = base64.b64decode(valor[len(PREFIJO):])
    iv, etiqueta, cifrado = datos[:12], datos[12:28], datos[28:]
    return AESGCM(_llave()).decrypt(iv, cifrado + etiqueta, None).decode()


class Cifrado(models.CharField):
    """
    Texto que se guarda cifrado y se lee en claro: el modelo nunca ve el valor
    cifrado. No sirve para buscar (`filter(secret=...)`): cada vez que se cifra
    sale distinto.
    """

    def from_db_value(self, value, expression, connection):
        return descifrar(value)

    def get_prep_value(self, value):
        return cifrar(super().get_prep_value(value))
