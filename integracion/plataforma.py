"""
La conexion con la plataforma de pagos (DataBridge), venga de donde venga.

Lo normal es hacerla desde el panel del personal: se pega la direccion y la
clave que la plataforma le emitio a APOFYX, y `conectar` comprueba la clave,
se suscribe a los avisos y guarda el secreto en la base (PlatformConnection).
Desde ese momento vale, sin reiniciar nada.

Si nunca se conecto desde el panel, vale lo que diga la configuracion
(DATABRIDGE en settings). Es lo que usan las pruebas, y un despliegue que
prefiera variables de entorno sigue funcionando igual.
"""

import os
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.utils import timezone

from .models import PlatformConnection

#  Desde un contenedor, estos nombres son el propio contenedor y no el equipo.
LOCALES = {"localhost", "127.0.0.1", "::1"}


def en_docker():
    """Si APOFYX corre dentro de un contenedor (Docker deja este archivo)."""
    return os.path.exists("/.dockerenv")


def direccion_de_avisos(request):
    """
    Donde le pide APOFYX a la plataforma que le avise los pagos: su propio
    /api/v1/eventos. Si corre en Docker y el panel se abrio desde localhost, la
    plataforma no lo encontraria ahi (para ella localhost es ella misma), asi
    que se propone host.docker.internal, que es el equipo visto desde Docker.
    """
    url = request.build_absolute_uri("/api/v1/eventos")
    partes = urlsplit(url)
    if en_docker() and partes.hostname in LOCALES:
        equipo = "host.docker.internal" + (f":{partes.port}" if partes.port else "")
        return urlunsplit(partes._replace(netloc=equipo))
    return url


def _pista(url):
    """Lo que hay que corregir cuando la plataforma no responde en localhost."""
    partes = urlsplit(url)
    if partes.hostname not in LOCALES:
        return ""
    puerto = f":{partes.port}" if partes.port else ""
    return (f" APOFYX corre en un contenedor, y ahi «{partes.hostname}» es el propio contenedor: "
            f"usa http://host.docker.internal{puerto}." if en_docker() else
            f" Si APOFYX corre en Docker, «{partes.hostname}» es el propio contenedor: "
            f"usa http://host.docker.internal{puerto}.")


def plataforma():
    """La configuracion del reenvio, con la conexion del panel encima de la de settings."""
    conf = dict(settings.DATABRIDGE)
    conf.setdefault("NOMBRE", "")
    fila = PlatformConnection.objects.filter(pk=1).first()
    if fila is not None:
        conf.update(URL=fila.url, CLAVE=fila.api_key, SECRETO_EVENTOS=fila.events_secret or "",
                    NOMBRE=fila.platform_name or "")
    return conf


def conexion():
    """La conexion hecha desde el panel, o None."""
    return PlatformConnection.objects.filter(pk=1).first()


class ConexionFallida(Exception):
    """La plataforma no respondio, o respondio que no."""


def conectar(url, clave, url_avisos, cliente=None):
    """
    Conecta APOFYX a la plataforma de pagos. Tres pasos, los mismos del contrato:

    1. `GET /api/v1/cuenta`: la clave sirve y es de APOFYX, no de otra empresa.
    2. `POST /api/v1/suscripciones`: la plataforma avisara los pagos a `url_avisos`.
    3. Se guarda todo, con el secreto de esos avisos.

    Si algo falla no se guarda nada: una conexion a medias dejaria a APOFYX
    reenviando carteras sin poder recibir los pagos de vuelta.
    """
    from .reenvio import ClienteDataBridge, ErrorDataBridge

    url = (url or "").strip().rstrip("/")
    clave = (clave or "").strip()
    url_avisos = (url_avisos or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ConexionFallida("La dirección tiene que partir con http:// o https://")
    if not clave:
        raise ConexionFallida("Falta la clave de API")
    if not url_avisos.startswith(("http://", "https://")):
        raise ConexionFallida("La dirección de los avisos tiene que partir con http:// o https://")

    cliente = cliente or ClienteDataBridge(url=url, clave=clave)
    try:
        cuenta = cliente.consultar("/api/v1/cuenta")
    except ErrorDataBridge as error:
        sin_respuesta = str(error).startswith("Sin respuesta")
        raise ConexionFallida(f"La plataforma no aceptó la clave: {error}."
                              + (_pista(url) if sin_respuesta else "")) from error
    propio = settings.DATABRIDGE["RUT_AGENCIA"]
    if cuenta.get("rut") != propio:
        raise ConexionFallida(f"Esa clave es de {cuenta.get('nombre') or cuenta.get('rut')}, no de APOFYX ({propio})")
    try:
        suscripcion = cliente.enviar("/api/v1/suscripciones", {"url": url_avisos})
    except ErrorDataBridge as error:
        raise ConexionFallida(f"La plataforma no aceptó la suscripción a los avisos: {error}") from error

    receptor = cuenta.get("receptor") or {}
    fila, _ = PlatformConnection.objects.update_or_create(pk=1, defaults={
        "url": url,
        "api_key": clave,
        "events_secret": suscripcion.get("secreto"),
        "platform_rut": receptor.get("rut"),
        "platform_name": receptor.get("nombre") or url,
        "connected_at": timezone.now(),
        "last_error": None,
    })
    return fila


def desconectar():
    """Borra la conexion. Lo que ya se reenvio queda; lo nuevo espera a que se vuelva a conectar."""
    PlatformConnection.objects.filter(pk=1).delete()
