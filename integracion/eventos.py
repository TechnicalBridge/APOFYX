"""
Los eventos de vuelta: DataBridge -> APOFYX -> el cliente (contrato 3).

Cuando un deudor paga o acepta un plan en DataBridge, DataBridge le avisa a
APOFYX, que fue quien le paso la cartera. APOFYX hace dos cosas con el aviso:

1. PONE AL DIA SU CARTERA. Una deuda saldada deja de estar en gestion; una
   repactada pasa a convenio. APOFYX sigue sin tablas de pagos: el dinero es de
   DataBridge, y a APOFYX le basta con saber en que estado quedo cada deuda.

2. SE LO REPORTA AL CLIENTE, con el mismo formato. El evento que sale es
   nuevo —id propio, firmado con el secreto del cliente— y lleva el lote del
   cliente en vez del de APOFYX. El id de la deuda no cambia: siempre fue el
   del cliente. Patrimonio no sabe ni necesita saber que detras hay DataBridge.

Los dos lados funcionan solos: sin secreto de DataBridge el endpoint responde
que la recepcion no esta configurada, y sin suscripcion del cliente el evento
pone al dia la cartera pero no sale a ninguna parte.
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from cartera.models import Debt
from crm.models import Campaign, CampaignFunnelSnapshot, Creditor
from crm.rut import normalizar

from .models import InboundEvent, OutboundEvent

log = logging.getLogger(__name__)

# El receptor descarta lo que difiera mas de esto de su reloj (contrato 8.1).
MAX_DESFASE_S = 5 * 60

# Lo que cada evento le hace a la deuda. pago.confirmado no esta: un abono no
# cambia el estado, solo el saldo, y el saldo vive en DataBridge.
ESTADO_POR_EVENTO = {
    "repactacion.aceptada": Debt.Status.REPACTED,
    "deuda.saldada": Debt.Status.PAID,
    "deuda.disputada": Debt.Status.DISPUTED,
    "deuda.retirada": Debt.Status.WITHDRAWN,
}

# Los eventos no llegan en orden garantizado. Una deuda pagada o retirada no
# vuelve atras porque despues llegue un aviso de repactacion que ocurrio antes.
FINALES = {Debt.Status.PAID, Debt.Status.WITHDRAWN}


class EventoInvalido(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


# ---------------------------------------------------------------------------
#  Firma
# ---------------------------------------------------------------------------

def firmar(secreto, marca, cuerpo):
    """v1= + HMAC-SHA256(secreto, timestamp + "." + cuerpo), en hex."""
    mensaje = f"{marca}.".encode("utf-8") + cuerpo
    return "v1=" + hmac.new(secreto.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


def firma_valida(secreto, marca, firma, cuerpo, ahora=None):
    """
    Recalcula la firma sobre el cuerpo tal como llego, byte a byte. Si se
    firmara el JSON ya parseado y vuelto a serializar, cualquier diferencia de
    espacios haria fallar un evento legitimo.
    """
    try:
        marca = int(marca)
    except (TypeError, ValueError):
        return False
    ahora = time.time() if ahora is None else ahora
    if abs(ahora - marca) > MAX_DESFASE_S:
        return False
    return hmac.compare_digest(firmar(secreto, marca, cuerpo), str(firma or ""))


# ---------------------------------------------------------------------------
#  Recibir
# ---------------------------------------------------------------------------

def recibir_evento(evento, reenviar=True):
    """
    Guarda el evento, pone al dia la deuda y lo deja listo para el cliente.

    Con `reenviar=False` no se le avisa al cliente. Es para la demo, que carga
    eventos de dias pasados: avisarlos hoy seria contarle al cliente algo que,
    en la historia, ya supo.
    """
    if not isinstance(evento, dict) or not evento.get("id") or not evento.get("tipo"):
        raise EventoInvalido("Al evento le falta id o tipo")
    datos = evento.get("datos") if isinstance(evento.get("datos"), dict) else {}

    with transaction.atomic():
        visto = InboundEvent.objects.filter(event_id=evento["id"]).first()
        if visto:
            return {"repetido": True, "resultado": visto.result}

        acreedor = Creditor.objects.filter(tax_id=normalizar(evento.get("acreedor_rut", ""))).first()
        deuda = None
        if acreedor and datos.get("deuda_id_externo"):
            deuda = (Debt.objects.select_related("last_batch")
                     .filter(creditor=acreedor, external_id=datos["deuda_id_externo"]).first())

        resultado = _aplicar(evento["tipo"], deuda, acreedor, datos)
        recibido = InboundEvent.objects.create(
            event_id=evento["id"],
            type=evento["tipo"][:30],
            occurred_at=_fecha(evento.get("ocurrido_en")),
            debt=deuda,
            payload=evento,
            result=resultado[:80],
        )
        avisados = _encolar_para_el_cliente(recibido, evento, acreedor, deuda) if reenviar else 0

    return {"repetido": False, "resultado": resultado, "avisados": avisados}


def _fecha(texto):
    """La fecha y hora en que ocurrio algo: '2026-09-22T14:03:11-03:00'."""
    try:
        return parse_datetime(str(texto or ""))
    except ValueError:
        return None


def _dia(texto):
    """Un dia sin hora: '2026-09-22'."""
    try:
        return parse_date(str(texto or ""))
    except ValueError:
        return None


def _aplicar(tipo, deuda, acreedor, datos):
    if acreedor is None:
        return "acreedor desconocido"
    if tipo == "campana.avance":
        return _guardar_avance(acreedor, datos)
    if datos.get("deuda_id_externo") is None:
        return "anotado"
    if deuda is None:
        return "deuda desconocida"

    nuevo = ESTADO_POR_EVENTO.get(tipo)
    if nuevo is None:
        return "pago anotado" if tipo == "pago.confirmado" else "anotado"
    if deuda.status == nuevo:
        return "sin cambios"
    if deuda.status in FINALES and nuevo not in FINALES:
        return f"se mantiene {deuda.get_status_display().lower()}"

    anterior = deuda.get_status_display().lower()
    deuda.status = nuevo
    if nuevo == Debt.Status.WITHDRAWN and datos.get("motivo"):
        deuda.withdrawn_reason = str(datos["motivo"])[:30]
    deuda.save(update_fields=["status", "withdrawn_reason", "updated_at"])
    return f"{anterior} -> {deuda.get_status_display().lower()}"


def _campana_de(acreedor, id_externo):
    """El id con que APOFYX presenta sus campanas: APX-CMP-<id>."""
    if not str(id_externo or "").startswith("APX-CMP-"):
        return None
    numero = str(id_externo)[len("APX-CMP-"):]
    if not numero.isdigit():
        return None
    return Campaign.objects.filter(pk=int(numero), creditor=acreedor).first()


def _guardar_avance(acreedor, datos):
    """
    El embudo de la campana, con lo que APOFYX no podia medir sola: cuantos
    pagaron y cuanto se recupero (docs 11.3).

    Solo se escriben las columnas que el evento trae. Un campo ausente no es
    un cero: es algo que DataBridge todavia no mide, y ponerle cero seria
    afirmar que no paso.
    """
    campana = _campana_de(acreedor, datos.get("campana_id_externo"))
    if campana is None:
        return "campana desconocida"
    corte = _dia(datos.get("fecha_corte"))
    if corte is None:
        return "sin fecha de corte"

    columnas = {
        "enviados": "messages_sent",
        "ingresos_portal": "link_clicks",
        "disputas": "debt_disputes",
        "pagos": "payments",
        "recuperado_clp": "recovered_clp",
        "recuperado_uf": "recovered_uf",
    }
    valores = {columna: datos[campo] for campo, columna in columnas.items() if datos.get(campo) is not None}
    CampaignFunnelSnapshot.objects.update_or_create(
        campaign=campana, measured_on=corte,
        defaults=valores,
    )
    return f"embudo al {datos.get('fecha_corte')}: {valores.get('payments', 0)} pago(s)"


def _encolar_para_el_cliente(recibido, evento, acreedor, deuda):
    """
    Un evento nuevo por cada suscripcion del cliente. Sin deuda conocida no se
    reenvia: no habria de donde sacar el lote del cliente.
    """
    if acreedor is None or deuda is None:
        return 0
    suscripciones = [s for s in acreedor.subscriptions.filter(active=True) if s.quiere(recibido.type)]
    if not suscripciones:
        return 0

    saliente = {
        "id": f"evt_{uuid.uuid4()}",
        "tipo": evento["tipo"],
        "version": "1",
        "ocurrido_en": evento.get("ocurrido_en"),
        "acreedor_rut": acreedor.tax_id,
        "lote_id_externo": deuda.last_batch.external_id,
        "datos": evento.get("datos") or {},
    }
    pendientes = [
        OutboundEvent.objects.create(
            event_id=saliente["id"], subscription=s, origin=recibido,
            type=recibido.type, payload=saliente,
        )
        for s in suscripciones
    ]
    if settings.DATABRIDGE["REENVIO_INMEDIATO"]:
        #  Despues del commit: avisarle al cliente de algo que aca todavia
        #  puede deshacerse seria peor que avisarle tarde.
        ids = [p.pk for p in pendientes]
        transaction.on_commit(lambda: [despachar_evento(pk) for pk in ids])
    return len(pendientes)


# ---------------------------------------------------------------------------
#  Avisar al cliente
# ---------------------------------------------------------------------------

def despachar_evento(pk):
    """Intenta entregar un evento al cliente. Nunca lanza."""
    pendiente = OutboundEvent.objects.select_related("subscription").filter(pk=pk).first()
    if pendiente is None or pendiente.status != OutboundEvent.Status.PENDING:
        return pendiente

    destino = pendiente.subscription
    cuerpo = json.dumps(pendiente.payload, ensure_ascii=False).encode("utf-8")
    marca = int(time.time())
    peticion = urllib.request.Request(
        destino.url, data=cuerpo, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Evento": pendiente.type,
            "X-Evento-Id": pendiente.event_id,
            "X-Timestamp": str(marca),
            "X-Firma": firmar(destino.secret, marca, cuerpo),
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=settings.DATABRIDGE["TIMEOUT_S"]):
            pass
        pendiente.entregado()
        log.info("Evento %s %s entregado a %s", pendiente.type, pendiente.event_id, destino.url)
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")[:200]
        pendiente.fallo(f"HTTP {error.code}: {detalle}")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        pendiente.fallo(f"Sin respuesta del cliente: {error}")
    if pendiente.status != OutboundEvent.Status.DELIVERED:
        log.warning("No se pudo avisar %s a %s (intento %s): %s", pendiente.event_id,
                    destino.url, pendiente.attempts, pendiente.last_error)
    pendiente.save()
    return pendiente


def despachar_eventos_pendientes():
    ids = list(OutboundEvent.objects.filter(
        status=OutboundEvent.Status.PENDING, next_attempt_at__lte=timezone.now(),
    ).order_by("pk").values_list("pk", flat=True))
    return [despachar_evento(pk) for pk in ids]
