"""
Los endpoints del contrato: por donde entra la cartera y por donde vuelven
los eventos.

Solo traducen HTTP: autentican, parsean y delegan. Las reglas viven en
intake.py y eventos.py, para que se puedan probar sin levantar un servidor.
"""

import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from cartera.models import Batch

from .eventos import TIPOS, EventoInvalido, firma_valida, recibir_evento
from .intake import CarteraInvalida, recibir_cartera
from .models import ApiKey, Subscription
from .plataforma import plataforma

NO_AUTORIZADO = {"error": {"codigo": "no_autorizado", "mensaje": "Clave de API invalida"}}


def _clave(request):
    cabecera = request.headers.get("Authorization", "")
    if cabecera.startswith("Bearer "):
        return cabecera[7:].strip()
    return ""


@csrf_exempt
@require_POST
def carteras(request):
    """POST /api/v1/carteras — recibe una Cartera v1."""
    credencial = ApiKey.autenticar(_clave(request))
    if credencial is None:
        return JsonResponse(
            {"error": {"codigo": "no_autorizado", "mensaje": "Clave de API invalida"}},
            status=401,
        )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": {"codigo": "json_invalido", "mensaje": "El cuerpo no es JSON valido"}},
            status=400,
        )

    try:
        respuesta = recibir_cartera(credencial.creditor, payload, source=Batch.Source.API)
    except CarteraInvalida as fallo:
        return JsonResponse(
            {"error": {"codigo": fallo.codigo, "mensaje": fallo.mensaje}},
            status=fallo.status,
        )
    return JsonResponse(respuesta, status=200)


@csrf_exempt
@require_POST
def eventos(request):
    """
    POST /api/v1/eventos — lo que DataBridge avisa (contrato 3).

    Responde rapido a proposito: el contrato le da al receptor 10 segundos, y
    lo que tarda de verdad —avisarle al cliente— queda en la bandeja.
    """
    secreto = plataforma()["SECRETO_EVENTOS"]
    if not secreto:
        return JsonResponse(
            {"error": {"codigo": "no_configurado",
                       "mensaje": "La recepcion de eventos no esta configurada"}},
            status=503,
        )
    if not firma_valida(secreto, request.headers.get("X-Timestamp"),
                        request.headers.get("X-Firma"), request.body):
        return JsonResponse(
            {"error": {"codigo": "firma_invalida", "mensaje": "Firma invalida o vencida"}},
            status=401,
        )
    try:
        evento = json.loads(request.body.decode("utf-8"))
        return JsonResponse(recibir_evento(evento), status=200)
    except (UnicodeDecodeError, json.JSONDecodeError):
        mensaje = "El cuerpo no es JSON valido"
    except EventoInvalido as fallo:
        mensaje = fallo.mensaje
    return JsonResponse({"error": {"codigo": "evento_invalido", "mensaje": mensaje}}, status=400)


@require_GET
def cuenta(request):
    """
    GET /api/v1/cuenta — de quien es la clave y con quien quedo conectado.

    La misma consulta, con la misma forma, que atiende DataBridge un tramo mas
    arriba: el sistema de la empresa se conecta igual a cualquiera de los dos.
    """
    credencial = ApiKey.autenticar(_clave(request))
    if credencial is None:
        return JsonResponse(NO_AUTORIZADO, status=401)
    empresa = credencial.creditor
    return JsonResponse({
        "rut": empresa.tax_id,
        "razon_social": empresa.legal_name,
        "nombre": empresa.trade_name,
        "tipo": "acreedor",
        "receptor": {"rut": settings.DATABRIDGE["RUT_AGENCIA"], "nombre": "APOFYX"},
    })


@csrf_exempt
@require_POST
def suscripciones(request):
    """
    POST /api/v1/suscripciones — la empresa registra donde recibir los avisos
    de su cartera. Registrar la misma URL otra vez devuelve el mismo secreto.
    """
    credencial = ApiKey.autenticar(_clave(request))
    if credencial is None:
        return JsonResponse(NO_AUTORIZADO, status=401)
    try:
        pedido = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": {"codigo": "json_invalido", "mensaje": "El cuerpo no es JSON valido"}}, status=400)
    url = (pedido.get("url") or "").strip() if isinstance(pedido, dict) else ""
    eventos_pedidos = pedido.get("eventos") if isinstance(pedido, dict) else None
    if not url.startswith(("http://", "https://")) or len(url) > 300:
        return JsonResponse(
            {"error": {"codigo": "url_invalida", "mensaje": "La URL tiene que partir con http:// o https://"}},
            status=400)
    if eventos_pedidos is not None and (not isinstance(eventos_pedidos, list)
                                        or any(e not in TIPOS for e in eventos_pedidos)):
        return JsonResponse(
            {"error": {"codigo": "evento_desconocido",
                       "mensaje": "Los eventos van como una lista de: " + ", ".join(TIPOS)}},
            status=400)
    suscripcion = Subscription.registrar(credencial.creditor, url, eventos_pedidos)
    return JsonResponse({
        "url": suscripcion.url,
        "eventos": suscripcion.events or "todos",
        "secreto": suscripcion.secret,
        "firma": 'X-Firma: v1=HMAC-SHA256(secreto, X-Timestamp + "." + cuerpo), en hex',
    })
