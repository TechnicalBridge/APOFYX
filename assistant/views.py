"""
API JSON del asistente del sitio.

Una sola ruta: recibe el mensaje del visitante y devuelve la respuesta. El
trabajo de verdad esta en engine.py.
"""

import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from . import engine
from .models import Conversation

MAX_MENSAJE = settings.ASSISTANT.get("MAX_MENSAJE", 500)


@require_POST
def chat(request):
    """
    Turno de conversacion.

    Entra:  {"mensaje": "...", "conversacion": 12 (opcional)}
    Sale:   {"ok": true, "respuesta": "...", "origen": "rules",
             "intencion": "precios_planes", "accion": "contact_sales",
             "conversacion": 12}

    La proteccion CSRF de Django aplica: el widget manda el token en la
    cabecera X-CSRFToken.
    """
    try:
        datos = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "detalle": "El cuerpo no es JSON valido."}, status=400)

    mensaje = (datos.get("mensaje") or "").strip()
    if not mensaje:
        return JsonResponse({"ok": False, "detalle": "Falta el mensaje."}, status=400)
    if len(mensaje) > MAX_MENSAJE:
        return JsonResponse(
            {"ok": False, "detalle": f"El mensaje supera los {MAX_MENSAJE} caracteres."},
            status=400,
        )

    # La sesion es lo que permite continuar un flujo multipaso entre turnos.
    if not request.session.session_key:
        request.session.create()

    conversacion = None
    id_conversacion = datos.get("conversacion")
    if id_conversacion:
        # Solo se retoma una conversacion de esta misma sesion: el identificador
        # viaja por el navegador y no debe servir para leer la de otra persona.
        conversacion = Conversation.objects.filter(
            pk=id_conversacion, session_key=request.session.session_key
        ).first()

    resultado = engine.responder(
        mensaje=mensaje,
        sesion=request.session,
        conversacion=conversacion,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return JsonResponse({"ok": True, **resultado})
