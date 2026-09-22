"""
El endpoint por donde entra la cartera.

Solo traduce HTTP: autentica, parsea y delega. Las reglas viven en intake.py,
para que se puedan probar sin levantar un servidor.
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cartera.models import Batch

from .intake import CarteraInvalida, recibir_cartera
from .models import ApiKey


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
