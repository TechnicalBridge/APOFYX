"""
El reenvio de la cartera a DataBridge.

APOFYX recibe la cartera de sus clientes, la valida y la guarda (intake.py). Si
tiene DataBridge configurado, se la pasa con el MISMO formato —Cartera v1—
agregando lo unico que le corresponde agregar: su mandato y la campana a la
que asigno la cartera.

TRES REGLAS

1. APOFYX NO CAMBIA MONTOS NI CARGOS. La cartera que sale se arma desde lo que
   quedo guardado al recibir, que es exactamente lo que el acreedor mando y
   APOFYX acepto. Los ids de deuda viajan intactos: son lo que permite que un
   pago vuelva hasta el contrato de arriendo que lo origino.

2. LA RECEPCION NO DEPENDE DE DATABRIDGE. El reenvio se anota en una bandeja
   de salida en la misma transaccion que recibe, y se entrega despues. Si
   DataBridge esta caido, el cliente de APOFYX igual recibe su respuesta.

3. SIN CONFIGURACION NO PASA NADA. Sin URL o sin clave el reenvio esta
   apagado, y APOFYX trabaja solo, como antes.

No usa `requests` a proposito: esta instalado solo como dependencia de otra
libreria, y apoyarse en eso haria que el reenvio se rompiera el dia que esa
libreria cambie. Para un POST con JSON alcanza con la biblioteca estandar.
"""

import json
import logging
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from cartera.models import Debt, Debtor
from crm.models import Campaign

from .models import Forward

log = logging.getLogger(__name__)


def configurado():
    conf = settings.DATABRIDGE
    return bool(conf["URL"] and conf["CLAVE"])


# ---------------------------------------------------------------------------
#  Encolar
# ---------------------------------------------------------------------------

def encolar(batch):
    """
    Anota la entrega para reenviarla. Se llama dentro de la transaccion que
    la recibio, asi que si la recepcion se deshace, el reenvio tambien.

    Solo se reenvia lo que tiene algo que reenviar: una entrega totalmente
    rechazada no le interesa a DataBridge.
    """
    if not configurado() or batch.accepted_count == 0:
        return None
    forward, _ = Forward.objects.get_or_create(
        batch=batch,
        defaults={"external_id": f"APX-{batch.cut_off.isoformat()}-{batch.pk:04d}"},
    )
    if settings.DATABRIDGE["REENVIO_INMEDIATO"]:
        #  Despues del commit, no antes: si se mandara adentro de la
        #  transaccion, DataBridge podria recibir una cartera que aca todavia
        #  no existe, o que termina deshaciendose.
        transaction.on_commit(lambda: despachar(forward.pk))
    return forward


# ---------------------------------------------------------------------------
#  Armar la cartera
# ---------------------------------------------------------------------------

def campana_para(batch):
    """
    La campana a la que va la cartera.

    Si la entrega ya tiene una, esa. Si no, y el acreedor tiene exactamente
    una campana en curso, se asume esa. Con cero o con varias no se adivina:
    alguien tiene que asignarla en el panel, y mientras tanto el reenvio
    espera.
    """
    if batch.campaign_id:
        return batch.campaign
    en_curso = list(Campaign.objects.filter(
        creditor=batch.creditor, status=Campaign.Status.RUNNING
    )[:2])
    if len(en_curso) == 1:
        batch.campaign = en_curso[0]
        batch.save(update_fields=["campaign"])
        return en_curso[0]
    return None


def id_de_campana(campana):
    """Como se llama la campana de APOFYX dentro de DataBridge."""
    return f"APX-CMP-{campana.pk}"


def _monto(valor, moneda):
    """Los pesos viajan enteros; la UF, con sus decimales (contrato §5)."""
    if moneda == "CLP":
        return int(valor)
    return float(Decimal(valor).quantize(Decimal("0.01")).normalize())


def construir_cartera(forward, campana):
    batch = forward.batch
    acreedor = batch.creditor
    #  Las altas primero y los retiros al final, igual que como arma la
    #  cartera Patrimonio. Ordenar solo por id pondria el retiro de una deuda
    #  vieja antes que las altas nuevas, y la cartera que sale dejaria de ser
    #  la misma que entro.
    deudas = []
    retiros = []

    for deuda in (Debt.objects
                  .filter(last_batch=batch)
                  .select_related("debtor")
                  .prefetch_related("charges")
                  .order_by("pk")):
        if deuda.status == Debt.Status.WITHDRAWN:
            retiros.append({
                "id_externo": deuda.external_id,
                "accion": "retirar",
                "motivo_retiro": deuda.withdrawn_reason,
            })
            continue

        deudor = {
            "rut": deuda.debtor.tax_id,
            "tipo": "empresa" if deuda.debtor.kind == Debtor.Kind.COMPANY else "persona",
            "nombre": deuda.debtor.full_name,
        }
        if deuda.debtor.email:
            deudor["correo"] = deuda.debtor.email
        if deuda.debtor.phone:
            deudor["telefono"] = deuda.debtor.phone

        item = {
            "id_externo": deuda.external_id,
            "deudor": deudor,
            "moneda": deuda.currency,
            "concepto": deuda.concept,
        }
        if deuda.refs:
            item["referencias"] = deuda.refs
        item["cargos"] = [
            {
                "concepto": cargo.concept,
                **({"periodo": cargo.period} if cargo.period else {}),
                "monto": _monto(cargo.amount, deuda.currency),
                "fecha_vencimiento": cargo.due_date.isoformat(),
            }
            for cargo in deuda.charges.all().order_by("due_date", "concept")
        ]
        deudas.append(item)

    return {
        "version": "1.0",
        "lote": {
            "id_externo": forward.external_id,
            "fecha_corte": batch.cut_off.isoformat(),
            "emitido_en": timezone.now().isoformat(),
            "acreedor": {
                "rut": acreedor.tax_id,
                "razon_social": acreedor.legal_name,
            },
            "mandato": {
                "agencia_rut": settings.DATABRIDGE["RUT_AGENCIA"],
                "campana_id_externo": id_de_campana(campana),
            },
        },
        "deudas": deudas + retiros,
    }


# ---------------------------------------------------------------------------
#  Hablar con DataBridge
# ---------------------------------------------------------------------------

class ErrorDataBridge(Exception):
    """DataBridge no respondio, o respondio que no."""


class ClienteDataBridge:
    """Tres llamadas del contrato: mandato, campana y cartera."""

    def __init__(self, url=None, clave=None, timeout=None):
        conf = settings.DATABRIDGE
        self.url = (url or conf["URL"]).rstrip("/")
        self.clave = clave or conf["CLAVE"]
        self.timeout = timeout or conf["TIMEOUT_S"]

    def enviar(self, ruta, cuerpo):
        peticion = urllib.request.Request(
            self.url + ruta,
            data=json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.clave}",
            },
        )
        try:
            with urllib.request.urlopen(peticion, timeout=self.timeout) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            cuerpo_error = error.read().decode("utf-8", errors="replace")
            raise ErrorDataBridge(f"HTTP {error.code}: {cuerpo_error[:200]}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ErrorDataBridge(f"Sin respuesta de DataBridge: {error}") from error


#  El vocabulario de APOFYX no es el del contrato. Sus campanas hablan de
#  'email' y 'sms'; DataBridge manda por WhatsApp y por correo (seccion 13.2
#  del documento), y el contrato los llama 'whatsapp' y 'correo'. La
#  traduccion vive aqui, en el borde, para que ni el CRM ni DataBridge tengan
#  que conocer las palabras del otro. El SMS no tiene equivalente y se cae.
CANALES_DEL_CONTRATO = {"whatsapp": "whatsapp", "email": "correo"}


def canales_para_databridge(canales):
    traducidos = []
    for canal in canales or []:
        destino = CANALES_DEL_CONTRATO.get(canal)
        if destino and destino not in traducidos:
            traducidos.append(destino)
    return traducidos


def asegurar_mandato_y_campana(cliente, batch, campana):
    """
    Contrato 2: antes de pasar una cartera, DataBridge tiene que saber que
    APOFYX cobra por cuenta de ese acreedor y con que campana.

    Las dos llamadas son idempotentes del lado de DataBridge, asi que se
    pueden repetir en cada reenvio sin llevar la cuenta de si ya se hicieron.
    """
    cliente.enviar("/api/v1/mandatos", {
        "acreedor_rut": batch.creditor.tax_id,
        "vigente_desde": (batch.creditor.client_since or batch.cut_off).isoformat(),
        "mora_maxima_dias": settings.DATABRIDGE["MORA_MAXIMA_DIAS"],
    })
    cliente.enviar("/api/v1/campanas", {
        "id_externo": id_de_campana(campana),
        "acreedor_rut": batch.creditor.tax_id,
        "nombre": campana.name,
        "inicio": campana.starts_on.isoformat(),
        **({"fin": campana.ends_on.isoformat()} if campana.ends_on else {}),
        "canales": canales_para_databridge(campana.channels),
        "intentos": campana.contact_attempts,
    })


# ---------------------------------------------------------------------------
#  Despachar
# ---------------------------------------------------------------------------

def despachar(forward_id, cliente=None):
    """
    Intenta entregar un reenvio. Nunca lanza: si falla, lo deja programado
    para el siguiente intento, que es lo que corresponde en una bandeja.
    """
    forward = (Forward.objects
               .select_related("batch__creditor", "batch__campaign")
               .filter(pk=forward_id).first())
    if forward is None or forward.status == Forward.Status.SENT:
        return forward

    campana = campana_para(forward.batch)
    if campana is None:
        forward.status = Forward.Status.WAITING_CAMPAIGN
        forward.last_error = "La entrega no tiene campana asignada"
        forward.save(update_fields=["status", "last_error"])
        return forward

    cliente = cliente or ClienteDataBridge()
    try:
        asegurar_mandato_y_campana(cliente, forward.batch, campana)
        respuesta = cliente.enviar("/api/v1/carteras", construir_cartera(forward, campana))
        forward.entregada(respuesta)
        log.info("Cartera %s entregada a DataBridge: %s aceptadas",
                 forward.external_id, respuesta.get("aceptadas"))
    except ErrorDataBridge as error:
        forward.fallo(str(error))
        log.warning("No se pudo entregar %s (intento %s): %s",
                    forward.external_id, forward.attempts, error)
    forward.save()
    return forward


def despachar_pendientes(cliente=None):
    """Lo pendiente que ya toca reintentar, y lo que esperaba campana."""
    ahora = timezone.now()
    pendientes = Forward.objects.filter(
        status__in=[Forward.Status.PENDING, Forward.Status.WAITING_CAMPAIGN],
        next_attempt_at__lte=ahora,
    ).values_list("pk", flat=True)
    return [despachar(pk, cliente) for pk in list(pendientes)]
