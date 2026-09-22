"""
Motor del asistente del sitio.

Es hibrido y en ese orden: primero reglas contra el catalogo que vive en MySQL,
y solo si el puntaje no alcanza el umbral se recurre a un modelo de lenguaje.
Si tampoco hay modelo disponible, responde la intencion 'fallback'. El sitio
nunca se queda sin responder.

Precios, plazos y tratamiento de datos son declaraciones comerciales y legales
de la empresa: salen del catalogo, revisadas, y NO se generan nunca.

Nota de atribucion: esta capa conversacional la aporta DataBridge, el software
de Technical Bridge. APOFYX es una operacion de cobranza y no construye
inteligencia artificial (ver docs/APOFYX.md seccion 7.3 y 13.2).
"""

import logging
import re
import time
import unicodedata

from django.conf import settings
from django.db.models import Prefetch

from .models import Conversation, Intent, IntentPattern, IntentResponse, Message

log = logging.getLogger(__name__)

AJUSTES = settings.ASSISTANT

# Los patrones del catalogo estan guardados ya normalizados. Esto deja el
# mensaje del visitante en la misma forma para poder compararlos.
_NO_ALFANUMERICO = re.compile(r"[^a-z0-9\s]")
_ESPACIOS = re.compile(r"\s+")


def normalizar(texto):
    """minusculas, sin tildes, sin signos y con los espacios colapsados."""
    if not texto:
        return ""
    texto = texto.lower()
    # NFD separa la letra del acento; luego se descartan los acentos sueltos.
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = _NO_ALFANUMERICO.sub(" ", texto)
    return _ESPACIOS.sub(" ", texto).strip()


# --------------------------------------------------------------------------
#  Reconocimiento por reglas
# --------------------------------------------------------------------------

def puntuar_intenciones(mensaje):
    """
    Devuelve [(intencion, puntaje), ...] ordenado de mayor a menor.

    Cada patron que aparece en el mensaje suma su peso. Un patron de 3.00 es
    una frase completa e inequivoca; uno de 1.00 es una palabra suelta que
    puede aparecer en varias intenciones.
    """
    normalizado = normalizar(mensaje)
    if not normalizado:
        return []

    intenciones = (
        Intent.objects.filter(is_active=True)
        .prefetch_related(Prefetch("patterns", queryset=IntentPattern.objects.all()))
    )

    puntajes = []
    for intencion in intenciones:
        if intencion.slug == "fallback":
            continue  # es la red de seguridad, no compite por puntaje
        total = sum(
            float(p.match_weight) for p in intencion.patterns.all()
            if p.pattern_text and p.pattern_text in normalizado
        )
        if total > 0:
            puntajes.append((intencion, total))

    # A igual puntaje gana la de menor prioridad numerica.
    puntajes.sort(key=lambda par: (-par[1], par[0].tiebreak_priority))
    return puntajes


def respuesta_de(intencion):
    """Primera respuesta activa de la intencion, o None si no tiene."""
    return (
        IntentResponse.objects.filter(intent=intencion, is_active=True)
        .order_by("display_order")
        .first()
    )


def respuesta_fallback():
    """La red de seguridad: se usa cuando nada mas alcanza."""
    intencion = Intent.objects.filter(slug="fallback").first()
    if intencion:
        respuesta = respuesta_de(intencion)
        if respuesta:
            return intencion, respuesta.response_text, respuesta.suggested_action
    return None, (
        "No estoy seguro de haber entendido. Puedo ayudarlo con que es APOFYX, "
        "como funciona el servicio, o ponerlo en contacto con el equipo comercial."
    ), "show_menu"


# --------------------------------------------------------------------------
#  Flujo multipaso: agendar una demostracion
# --------------------------------------------------------------------------

PASOS_DEMO = [
    ("full_name",      "Perfecto. ¿Cuál es su nombre completo?"),
    ("company_name",   "Gracias. ¿Cómo se llama su empresa?"),
    ("email",          "¿A qué correo lo contactamos?"),
    ("estimated_debtor_count", "Por último, ¿cuántos deudores tiene aproximadamente? "
                       "Un número redondo basta, o escriba «no sé»."),
]

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def iniciar_demo():
    """Estado inicial del flujo, para guardar en la sesion."""
    return {"paso": 0, "datos": {}}


def avanzar_demo(estado, mensaje):
    """
    Procesa una respuesta dentro del flujo.

    Devuelve (estado_nuevo, texto, accion, lead_creado). Si estado_nuevo es
    None, el flujo termino y hay que sacarlo de la sesion.
    """
    from crm.models import Lead

    texto = (mensaje or "").strip()
    normalizado = normalizar(texto)

    if normalizado in {"cancelar", "cancela", "olvidalo", "salir", "no gracias"}:
        return None, "Listo, lo dejamos hasta aquí. Si cambia de idea, avíseme.", None, False

    campo, _ = PASOS_DEMO[estado["paso"]]

    # Validaciones minimas: solo lo que impide contactar a la persona.
    if campo == "email" and not _CORREO.match(texto):
        return estado, "Ese correo no parece válido. ¿Me lo escribe de nuevo?", None, False
    if campo in {"full_name", "company_name"} and len(texto) < 2:
        return estado, "No alcancé a leerlo. ¿Me lo repite?", None, False

    if campo == "estimated_debtor_count":
        digitos = re.sub(r"[^\d]", "", texto)
        estado["datos"][campo] = int(digitos) if digitos else None
    else:
        estado["datos"][campo] = texto

    estado["paso"] += 1

    if estado["paso"] < len(PASOS_DEMO):
        return estado, PASOS_DEMO[estado["paso"]][1], None, False

    # Fin del flujo: el lead se graba en MySQL, igual que el del formulario.
    datos = estado["datos"]
    Lead.objects.create(
        full_name=datos.get("full_name", "")[:120],
        company_name=datos.get("company_name", "")[:160],
        email=datos.get("email", "")[:254],
        estimated_debtor_count=datos.get("estimated_debtor_count"),
        source=Lead.Source.ASSISTANT,
        inquiry_message="Solicitud tomada por el asistente del sitio.",
    )
    cierre = (
        f"Listo, {datos.get('full_name', '').split(' ')[0]}. Quedó registrado y el "
        "equipo comercial le escribirá dentro de un día hábil. ¿Le ayudo con algo más?"
    )
    return None, cierre, None, True


# --------------------------------------------------------------------------
#  Respaldo con modelo de lenguaje
# --------------------------------------------------------------------------

def _contexto_para_modelo():
    """
    Lo que el modelo puede decir sale de la base, no de su memoria: se le pasa
    el catalogo de respuestas aprobadas como unica fuente.
    """
    lineas = []
    for intencion in Intent.objects.filter(is_active=True).prefetch_related("responses"):
        respuesta = intencion.responses.filter(is_active=True).order_by("display_order").first()
        if respuesta:
            lineas.append(f"- {intencion.name}: {respuesta.response_text}")
    return "\n".join(lineas)


INSTRUCCION = """Eres el asistente automatico del sitio web de APOFYX, una empresa
chilena de cobranza extrajudicial para carteras masivas de monto bajo.

REGLAS QUE NO PUEDES ROMPER:
1. Responde SOLO sobre APOFYX y su servicio. Cualquier otro tema, declina con
   amabilidad y ofrece volver al tema.
2. NUNCA inventes precios, plazos, porcentajes ni cifras. APOFYX no publica
   tarifas: si preguntan cuanto cuesta, deriva al formulario de contacto.
3. NUNCA converses sobre la deuda concreta de una persona, ni pidas RUT, claves
   ni datos bancarios. Si alguien dice que recibio un mensaje de cobranza,
   explicale que verifique directamente con la empresa acreedora.
4. Te identificas como asistente automatico si te preguntan. No finges ser
   humano ni tienes nombre de persona.
5. Responde en espanol de Chile, en tono directo y sobrio. Maximo 4 frases.

La informacion de abajo es tu UNICA fuente. Si la respuesta no esta ahi, dilo y
ofrece el formulario de contacto.

INFORMACION APROBADA:
{contexto}"""


def consultar_modelo(mensaje):
    """
    Consulta a Gemini. Devuelve el texto o None si no se pudo.

    Nunca lanza: si falta la clave, el modelo esta saturado, se acaba la cuota o
    la red falla, el motor sigue hacia la respuesta de fallback y el visitante
    igual recibe algo.

    Dos cosas aprendidas probando contra la API real:

    1. TIEMPO DE ESPERA. Sin limite, el SDK reintenta solo ante un 503 y una
       consulta puede tardar mas de 50 segundos. En un chat eso es inaceptable.
       El minimo que acepta la API son 10 s, asi que se usa un poco mas.

    2. MODELOS QUE RAZONAN. Los flash recientes gastan el presupuesto de salida
       en razonamiento interno: con un tope de 300 tokens, gemini-3.6-flash uso
       286 pensando y devolvio 10 de respuesta, o sea una frase cortada a la
       mitad. Por eso el modelo por defecto es un "lite", que no razona, y por
       eso se descarta toda respuesta truncada en vez de mostrarla.
    """
    clave = AJUSTES.get("GEMINI_API_KEY")
    if not clave:
        return None

    try:
        from google import genai
        from google.genai import types

        cliente = genai.Client(
            api_key=clave,
            http_options=types.HttpOptions(
                timeout=AJUSTES.get("GEMINI_TIMEOUT_MS", 12000)
            ),
        )
        respuesta = cliente.models.generate_content(
            model=AJUSTES.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            contents=mensaje,
            config=types.GenerateContentConfig(
                system_instruction=INSTRUCCION.format(contexto=_contexto_para_modelo()),
                max_output_tokens=AJUSTES.get("GEMINI_MAX_TOKENS", 400),
                temperature=0.3,
            ),
        )

        # Una respuesta cortada por tope de tokens es peor que ninguna: se ve
        # como una frase a medio terminar. Se descarta y cae en fallback.
        candidatos = getattr(respuesta, "candidates", None) or []
        if candidatos:
            motivo = str(getattr(candidatos[0], "finish_reason", "") or "")
            if "MAX_TOKENS" in motivo.upper():
                log.warning("Respuesta truncada por tope de tokens; se descarta.")
                return None

        texto = (respuesta.text or "").strip()
        return texto or None
    except Exception as error:
        log.warning("El respaldo con modelo no respondio: %s", error)
        return None


# --------------------------------------------------------------------------
#  Punto de entrada
# --------------------------------------------------------------------------

def responder(mensaje, sesion, conversacion=None, user_agent=""):
    """
    Resuelve un turno completo y lo registra.

    Devuelve un dict con la respuesta, el origen ('rules' / 'llm' / 'fallback'),
    la intencion detectada y la accion sugerida para la interfaz.
    """
    inicio = time.monotonic()

    if conversacion is None:
        conversacion = Conversation.objects.create(
            session_key=sesion.session_key or "",
            user_agent=(user_agent or "")[:255],
        )

    Message.objects.create(
        conversation=conversacion, speaker=Message.Speaker.VISITOR, message_text=mensaje[:2000]
    )

    intencion = None
    accion = None
    confianza = None

    # 1. ¿Hay un flujo multipaso abierto? Tiene prioridad sobre todo lo demas.
    estado = sesion.get("flujo_demo")
    if estado:
        estado, texto, accion, creado = avanzar_demo(estado, mensaje)
        sesion["flujo_demo"] = estado
        sesion.modified = True
        origen = Message.AnswerEngine.RULES
        if creado:
            conversacion.is_resolved = True
            conversacion.save(update_fields=["is_resolved"])
    else:
        # 2. Reglas.
        puntajes = puntuar_intenciones(mensaje)
        umbral = AJUSTES.get("UMBRAL_CONFIANZA", 2.5)

        if puntajes and puntajes[0][1] >= umbral:
            intencion, puntaje = puntajes[0]
            confianza = min(puntaje / 6.0, 1.0)

            if intencion.slug == "agendar_demo":
                sesion["flujo_demo"] = iniciar_demo()
                sesion.modified = True
                texto = PASOS_DEMO[0][1]
                accion = None
            else:
                respuesta = respuesta_de(intencion)
                texto = respuesta.response_text if respuesta else respuesta_fallback()[1]
                accion = respuesta.suggested_action if respuesta else None

            origen = Message.AnswerEngine.RULES

            if not conversacion.inferred_audience:
                conversacion.inferred_audience = intencion.audience
                conversacion.save(update_fields=["inferred_audience"])
        else:
            # 3. Respaldo con modelo.
            texto = consultar_modelo(mensaje)
            if texto:
                origen = Message.AnswerEngine.LLM
            else:
                # 4. Red de seguridad.
                intencion, texto, accion = respuesta_fallback()
                origen = Message.AnswerEngine.FALLBACK

    latencia = int((time.monotonic() - inicio) * 1000)

    Message.objects.create(
        conversation=conversacion,
        speaker=Message.Speaker.ASSISTANT,
        message_text=texto[:2000],
        intent=intencion,
        match_confidence=round(confianza, 4) if confianza is not None else None,
        answer_engine=origen,
        response_time_ms=latencia,
    )

    return {
        "respuesta": texto,
        "origen": origen,
        "intencion": intencion.slug if intencion else None,
        "accion": accion,
        "conversacion": conversacion.pk,
    }
