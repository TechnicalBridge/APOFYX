"""
Carga la historia de la demo: la cartera de Patrimonio Inmuebles, con cada
deudor en una situacion distinta.

    python manage.py cargar_demo
    python manage.py cargar_demo --reemplazar

Es la misma historia que cuentan los datos de ejemplo de Patrimonio y de
DataBridge, vista desde APOFYX. Patrimonio entrego dos carteras, la del corte
del 18 de agosto y la del 18 de septiembre. APOFYX las recibio, se las paso a
DataBridge el dia en que empezaba la campana de cada mes, y DataBridge le fue
avisando lo que hacia cada deudor:

    Felipe          acepto 6 cuotas y lleva 3 pagadas            en convenio
    Valentina       debe un mes: DataBridge no la tomo           en gestion
    Comercial Nandu debe tres meses en UF                        en gestion
    Tomas           pago en la oficina y Patrimonio lo retiro    retirada
    Rodrigo         debe cuatro meses                            en gestion
    Carolina        pago todo de una vez                         pagada
    La Espiga       acepto 3 cuotas en UF y pago la primera      en convenio
    Ignacio         dejo el depto, acepto 6 cuotas y no pago     en convenio
    Daniela         acepto 3 cuotas y las pago juntas            pagada

Todo pasa por el mismo codigo que una cartera de verdad: recibir_cartera valida
y guarda, recibir_evento pone al dia cada estado. La unica diferencia es que no
se reenvia nada, ni a DataBridge ni a Patrimonio: es historia, ya ocurrio.

Solo se carga si Patrimonio no tiene cartera en APOFYX. Si ya tiene una (la de
una corrida de la cadena completa, por ejemplo), no se toca, salvo con
--reemplazar.
"""

import uuid
from datetime import date, datetime, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from cartera.models import Batch, Debt, DebtCharge, Debtor
from crm.models import Campaign, Creditor

from ...eventos import recibir_evento
from ...intake import huella, recibir_cartera
from ...models import Forward, InboundEvent, OutboundEvent

RUT_PATRIMONIO = "76418902-7"
CHILE = ZoneInfo("America/Santiago")


def _hora(texto):
    """'2026-09-21 18:45' en hora de Chile."""
    return datetime.fromisoformat(texto).replace(tzinfo=CHILE)


# ---------------------------------------------------------------------------
#  Lo que mando Patrimonio
# ---------------------------------------------------------------------------

FELIPE = {"rut": "16482337-7", "tipo": "persona", "nombre": "Felipe Rojas Muñoz",
          "correo": "felipe.rojas@correo.cl", "telefono": "+56987654321"}
VALENTINA = {"rut": "18905214-6", "tipo": "persona", "nombre": "Valentina Soto Pizarro",
             "correo": "valentina.soto@correo.cl", "telefono": "+56912348765"}
NANDU = {"rut": "76991245-2", "tipo": "empresa", "nombre": "Comercial Ñandú SpA",
         "correo": "administracion@nandu.cl"}
TOMAS = {"rut": "15227640-0", "tipo": "persona", "nombre": "Tomás Fuentes Leiva",
         "correo": "tomas.fuentes@correo.cl", "telefono": "+56955512340"}
RODRIGO = {"rut": "14583206-3", "tipo": "persona", "nombre": "Rodrigo Pérez Contreras",
           "correo": "rodrigo.perez@correo.cl", "telefono": "+56961238890"}
CAROLINA = {"rut": "19230418-0", "tipo": "persona", "nombre": "Carolina Muñoz Vera",
            "correo": "carolina.munoz@correo.cl", "telefono": "+56978812034"}
LA_ESPIGA = {"rut": "76284519-9", "tipo": "empresa", "nombre": "Panadería La Espiga Ltda.",
             "correo": "contacto@laespiga.cl", "telefono": "+56229876543"}
IGNACIO = {"rut": "17893456-2", "tipo": "persona", "nombre": "Ignacio Tapia Rojas",
           "correo": "ignacio.tapia@correo.cl", "telefono": "+56987120045"}
DANIELA = {"rut": "18642975-3", "tipo": "persona", "nombre": "Daniela Cáceres Flores",
           "correo": "daniela.caceres@correo.cl", "telefono": "+56954410987"}

#  Contrato -> (deudor, moneda, concepto, propiedad, renta del mes)
CONTRATOS = {
    "CTR-2025-014": (FELIPE, "CLP", "Arriendo mensual", "Depto 1204, Av. Irarrázaval 2450, Ñuñoa", 520000),
    "CTR-2026-031": (VALENTINA, "CLP", "Arriendo mensual", "Depto 305, Los Leones 1180, Providencia", 410000),
    "CTR-2024-007": (NANDU, "UF", "Arriendo local comercial", "Local 3, Av. Italia 1320, Providencia", 38.5),
    "CTR-2025-022": (TOMAS, "CLP", "Arriendo mensual", "Los Castaños 455, La Florida", 680000),
    "CTR-2025-019": (RODRIGO, "CLP", "Arriendo mensual", "Depto 1507, Santa Isabel 470, Santiago", 450000),
    "CTR-2026-012": (CAROLINA, "CLP", "Arriendo mensual", "Depto 42, Av. Pajaritos 2810, Maipú", 380000),
    "CTR-2024-019": (LA_ESPIGA, "UF", "Arriendo local comercial",
                     "Local 12, Gran Avenida José Miguel Carrera 5540, San Miguel", 24),
    "CTR-2025-027": (IGNACIO, "CLP", "Arriendo mensual", "Depto 204, Portugal 48, Santiago", 350000),
    "CTR-2026-015": (DANIELA, "CLP", "Arriendo mensual", "Depto 713, Av. Vicuña Mackenna 4860, Macul", 300000),
}

MESES = {"2026-06": "junio", "2026-07": "julio", "2026-08": "agosto", "2026-09": "septiembre"}


def _deuda(contrato, impagos):
    """Una deuda como la arma Patrimonio: un cargo por cada mes impago."""
    deudor, moneda, concepto, propiedad, renta = CONTRATOS[contrato]
    return {
        "id_externo": contrato,
        "deudor": deudor,
        "moneda": moneda,
        "concepto": concepto,
        "referencias": {"contrato": contrato, "propiedad": propiedad},
        "cargos": [
            {"concepto": f"Arriendo {MESES[mes]}", "periodo": mes, "monto": renta,
             "fecha_vencimiento": f"{mes}-05"}
            for mes in impagos
        ],
    }


def _cartera(id_externo, corte, emitida, deudas):
    return {
        "version": "1.0",
        "lote": {
            "id_externo": id_externo,
            "fecha_corte": corte,
            "emitido_en": emitida,
            "acreedor": {"rut": RUT_PATRIMONIO, "razon_social": "Patrimonio Inmuebles SpA",
                         "nombre_fantasia": "Patrimonio Inmuebles"},
        },
        "deudas": deudas,
    }


#  Felipe y Carolina debian un mes; Valentina estaba al dia.
AGOSTO = _cartera("PAT-2026-08-18-01", "2026-08-18", "2026-08-18T14:05:00.000Z", [
    _deuda("CTR-2025-014", ["2026-08"]),
    _deuda("CTR-2024-007", ["2026-07", "2026-08"]),
    _deuda("CTR-2025-022", ["2026-07", "2026-08"]),
    _deuda("CTR-2025-019", ["2026-06", "2026-07", "2026-08"]),
    _deuda("CTR-2026-012", ["2026-08"]),
    _deuda("CTR-2024-019", ["2026-07", "2026-08"]),
    _deuda("CTR-2025-027", ["2026-06", "2026-07", "2026-08"]),
    _deuda("CTR-2026-015", ["2026-07", "2026-08"]),
])

#  Ignacio ya no viene: su contrato termino el 31 de agosto. Tomas se puso al
#  dia en la oficina y va como retiro, al final, como los manda Patrimonio.
SEPTIEMBRE = _cartera("PAT-2026-09-18-01", "2026-09-18", "2026-09-18T13:05:00.000Z", [
    _deuda("CTR-2025-014", ["2026-08", "2026-09"]),
    _deuda("CTR-2026-031", ["2026-09"]),
    _deuda("CTR-2024-007", ["2026-07", "2026-08", "2026-09"]),
    _deuda("CTR-2025-019", ["2026-06", "2026-07", "2026-08", "2026-09"]),
    _deuda("CTR-2026-012", ["2026-08", "2026-09"]),
    _deuda("CTR-2024-019", ["2026-07", "2026-08", "2026-09"]),
    _deuda("CTR-2026-015", ["2026-07", "2026-08", "2026-09"]),
    {"id_externo": "CTR-2025-022", "accion": "retirar", "motivo_retiro": "pago_directo"},
])


# ---------------------------------------------------------------------------
#  Lo que respondio DataBridge
# ---------------------------------------------------------------------------

#  Los ids con que DataBridge conoce cada cartera que le paso APOFYX. Son los
#  mismos de sus datos de ejemplo, para que las dos demos cuenten lo mismo.
LOTE_AGOSTO = "APX-2026-08-19-003"
LOTE_SEPTIEMBRE = "APX-2026-09-19-004"

#  DataBridge cobra desde dos meses impagos: con uno, la deuda se rechaza sola.
UN_MES = [{"campo": "cargos", "codigo": "bajo_umbral_mora",
           "mensaje": "Tiene 1 mes impago: DataBridge recibe deudas desde 2 meses impagos"}]


def _entro(contrato, resultado, mora):
    tramo = "31-90" if mora <= 90 else "91-120"
    return {"id_externo": contrato, "resultado": resultado, "mora_dias": mora, "tramo": tramo}


def _respuesta(lote, resultados):
    rechazadas = sum(1 for r in resultados if r["resultado"] == "rechazada")
    return {
        "lote": lote, "repetido": False, "recibidas": len(resultados),
        "aceptadas": len(resultados) - rechazadas, "rechazadas": rechazadas,
        "resultados": resultados, "campos_ignorados": [],
    }


RESPUESTA_AGOSTO = _respuesta(LOTE_AGOSTO, [
    {"id_externo": "CTR-2025-014", "resultado": "rechazada", "errores": UN_MES},
    _entro("CTR-2024-007", "registrada", 44),
    _entro("CTR-2025-022", "registrada", 44),
    _entro("CTR-2025-019", "registrada", 74),
    {"id_externo": "CTR-2026-012", "resultado": "rechazada", "errores": UN_MES},
    _entro("CTR-2024-019", "registrada", 44),
    _entro("CTR-2025-027", "registrada", 74),
    _entro("CTR-2026-015", "registrada", 44),
])

RESPUESTA_SEPTIEMBRE = _respuesta(LOTE_SEPTIEMBRE, [
    _entro("CTR-2025-014", "registrada", 44),
    _entro("CTR-2024-007", "actualizada", 75),
    _entro("CTR-2025-019", "actualizada", 105),
    _entro("CTR-2026-012", "registrada", 44),
    _entro("CTR-2024-019", "actualizada", 75),
    _entro("CTR-2026-015", "actualizada", 75),
    {"id_externo": "CTR-2026-031", "resultado": "rechazada", "errores": UN_MES},
    {"id_externo": "CTR-2025-022", "resultado": "retirada"},
])


def _evento(cuando, tipo, lote, **datos):
    """
    Un evento como lo arma DataBridge. El id sale de su contenido, asi que es
    siempre el mismo y la deduplicacion de recibir_evento sirve tambien aca.
    """
    ocurrido = _hora(cuando).isoformat()
    marca = f"{tipo}|{datos.get('deuda_id_externo', lote)}|{ocurrido}"
    return {
        "id": f"evt_{uuid.uuid5(uuid.NAMESPACE_URL, 'apofyx-demo/' + marca)}",
        "tipo": tipo,
        "version": "1",
        "ocurrido_en": ocurrido,
        "acreedor_rut": RUT_PATRIMONIO,
        "lote_id_externo": lote,
        "datos": datos,
    }


def _convenio(cuando, lote, contrato, cuotas, monto, moneda, primera):
    return _evento(cuando, "repactacion.aceptada", lote, deuda_id_externo=contrato, cuotas=cuotas,
                   monto_cuota=monto, moneda=moneda, primera_cuota=primera)


def _pago(cuando, contrato, pago_id, monto, medio, moneda="CLP", monto_clp=None, valor_uf=None):
    datos = {"deuda_id_externo": contrato, "pago_id": pago_id, "monto": monto, "moneda": moneda,
             "monto_clp": monto if monto_clp is None else monto_clp}
    if valor_uf is not None:
        datos["valor_uf"] = valor_uf
    datos.update(medio=medio, pagado_en=_hora(cuando).isoformat())
    return _evento(cuando, "pago.confirmado", LOTE_SEPTIEMBRE, **datos)


def _saldada(cuando, contrato):
    return _evento(cuando, "deuda.saldada", LOTE_SEPTIEMBRE, deuda_id_externo=contrato,
                   saldada_en=_hora(cuando).isoformat())


def _procesado(cuando, lote, corte, respuesta, tramos):
    return _evento(cuando, "lote.procesado", lote, periodo=corte[:7], fecha_corte=corte,
                   recibidas=respuesta["recibidas"], aceptadas=respuesta["aceptadas"],
                   rechazadas=respuesta["rechazadas"], tramos=tramos)


# ---------------------------------------------------------------------------
#  La historia, en el orden en que paso
# ---------------------------------------------------------------------------

CAMPANA_AGOSTO = "Patrimonio - Arriendos - Agosto 2026"
CAMPANA_SEPTIEMBRE = "Patrimonio - Arriendos - Septiembre 2026"

class Entrega(NamedTuple):
    """Patrimonio entrega una cartera. APOFYX la recibe y anota el reenvio."""
    cuando: str
    cartera: dict
    lote_en_databridge: str


class Reenvio(NamedTuple):
    """Empieza la campana del mes y APOFYX le pasa la cartera a DataBridge."""
    cuando: str
    cartera: dict
    campana: str
    respuesta: dict


#  Lo que no es una entrega ni un reenvio es un aviso de DataBridge.
HISTORIA = [
    Entrega("2026-08-18 10:05:03", AGOSTO, LOTE_AGOSTO),
    Reenvio("2026-08-19 10:12:00", AGOSTO, CAMPANA_AGOSTO, RESPUESTA_AGOSTO),
    _procesado("2026-08-19 10:12", LOTE_AGOSTO, "2026-08-18", RESPUESTA_AGOSTO,
               [{"tramo": "31-90", "deudas": 6, "promedio_clp": 1090000}]),
    _convenio("2026-08-20 17:05", LOTE_AGOSTO, "CTR-2025-027", 6, 175000, "CLP", "2026-09-20"),

    Entrega("2026-09-18 10:05:02", SEPTIEMBRE, LOTE_SEPTIEMBRE),
    Reenvio("2026-09-19 10:05:00", SEPTIEMBRE, CAMPANA_SEPTIEMBRE, RESPUESTA_SEPTIEMBRE),
    _evento("2026-09-19 10:05", "deuda.retirada", LOTE_SEPTIEMBRE,
            deuda_id_externo="CTR-2025-022", motivo="pago_directo"),
    _procesado("2026-09-19 10:05", LOTE_SEPTIEMBRE, "2026-09-18", RESPUESTA_SEPTIEMBRE,
               [{"tramo": "31-90", "deudas": 5, "promedio_clp": 900000},
                {"tramo": "91-120", "deudas": 1, "promedio_clp": 1800000}]),
    _convenio("2026-09-20 09:10", LOTE_SEPTIEMBRE, "CTR-2026-015", 3, 300000, "CLP", "2026-10-20"),
    _convenio("2026-09-20 11:40", LOTE_SEPTIEMBRE, "CTR-2025-014", 6, 173333, "CLP", "2026-10-20"),
    _pago("2026-09-21 18:45", "CTR-2026-012", "118", 760000, "khipu"),
    _saldada("2026-09-21 18:45", "CTR-2026-012"),
    _pago("2026-09-21 20:14", "CTR-2025-014", "119", 173333, "webpay"),
    _convenio("2026-09-22 10:15", LOTE_SEPTIEMBRE, "CTR-2024-019", 3, 24, "UF", "2026-10-22"),
    #  En UF DataBridge cobra en pesos, con la UF del dia, y avisa cual uso.
    _pago("2026-09-23 12:30", "CTR-2024-019", "123", 24, "mercadopago",
          moneda="UF", monto_clp=957037, valor_uf=39876.54),
    _pago("2026-09-23 13:02", "CTR-2025-014", "124", 346666, "mercadopago"),
    _pago("2026-09-24 21:05", "CTR-2026-015", "131", 900000, "webpay"),
    _saldada("2026-09-24 21:05", "CTR-2026-015"),
]

#  Lo que tarda un aviso de DataBridge en llegar: su bandeja sale cada pocos segundos.
DEMORA_DEL_AVISO = timedelta(seconds=4)


class Command(BaseCommand):
    help = "Carga la cartera de Patrimonio de la demo, con cada deudor en una situacion distinta."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reemplazar", action="store_true",
            help="Borra la cartera que Patrimonio tenga en APOFYX (entregas, deudas, reenvios y "
                 "eventos) y carga la de la demo en su lugar.",
        )

    def handle(self, *args, **opciones):
        acreedor = Creditor.objects.filter(tax_id=RUT_PATRIMONIO).first()
        if acreedor is None:
            raise CommandError(
                f"Patrimonio Inmuebles ({RUT_PATRIMONIO}) no esta entre los clientes. Viene en "
                "sql/AphofyxDB.sql; en una base anterior, corre "
                "sql/migraciones/2026-09-19-patrimonio-como-acreedor.sql"
            )

        with transaction.atomic():
            entregas = Batch.objects.filter(creditor=acreedor)
            if entregas.exists():
                if not opciones["reemplazar"]:
                    self._no_se_toca(entregas)
                    return
                self._borrar(acreedor)
            self._cargar(acreedor)
        self._resumen(acreedor)

    # ------------------------------------------------------------------

    def _no_se_toca(self, entregas):
        demo = {AGOSTO["lote"]["id_externo"]: huella(AGOSTO), SEPTIEMBRE["lote"]["id_externo"]: huella(SEPTIEMBRE)}
        if dict(entregas.values_list("external_id", "payload_hash")) == demo:
            self.stdout.write("La demo ya estaba cargada.")
            return
        self.stdout.write(
            f"Patrimonio ya tiene cartera en APOFYX ({entregas.count()} entrega(s)) y no se toca.\n"
            "Para cambiarla por la de la demo: python manage.py cargar_demo --reemplazar"
        )

    def _borrar(self, acreedor):
        """Todo lo de la cartera de Patrimonio. Lo demas del cliente (campanas, claves) queda."""
        deudas = Debt.objects.filter(creditor=acreedor)
        deudores = list(deudas.values_list("debtor_id", flat=True))
        OutboundEvent.objects.filter(subscription__creditor=acreedor).delete()
        InboundEvent.objects.filter(payload__acreedor_rut=acreedor.tax_id).delete()
        cuantas = deudas.count()
        deudas.delete()
        #  Los reenvios se van con sus entregas.
        Batch.objects.filter(creditor=acreedor).delete()
        #  Un deudor es uno solo aunque le deba a varios clientes: se va solo
        #  si ya no le debe a nadie.
        Debtor.objects.filter(pk__in=deudores, debts__isnull=True).delete()
        self.stdout.write(f"Borrada la cartera anterior de Patrimonio: {cuantas} deuda(s).")

    def _cargar(self, acreedor):
        for paso in HISTORIA:
            desde = timezone.now()
            if isinstance(paso, Entrega):
                self._recibir(acreedor, paso)
                cuando = _hora(paso.cuando)
            elif isinstance(paso, Reenvio):
                self._reenviar(acreedor, paso)
                cuando = _hora(paso.cuando)
            else:
                recibir_evento(paso, reenviar=False)
                cuando = datetime.fromisoformat(paso["ocurrido_en"]) + DEMORA_DEL_AVISO
            _fechar(acreedor, desde, cuando)

    def _recibir(self, acreedor, paso):
        respuesta = recibir_cartera(acreedor, paso.cartera, reenviar=False)
        if respuesta["rechazadas"]:
            #  Una demo a medias contaria otra historia: mejor no cargarla.
            raise CommandError(f"La cartera {respuesta['lote']} de la demo no entro completa: "
                               f"{respuesta['resultados']}")
        #  El reenvio queda anotado al recibir, esperando la campana del mes.
        Forward.objects.create(batch=_entrega(acreedor, paso.cartera),
                               external_id=paso.lote_en_databridge,
                               status=Forward.Status.WAITING_CAMPAIGN)

    def _reenviar(self, acreedor, paso):
        entrega = _entrega(acreedor, paso.cartera)
        entrega.campaign = _campana(acreedor, paso.campana)
        entrega.save(update_fields=["campaign"])
        Forward.objects.filter(batch=entrega).update(
            status=Forward.Status.SENT, sent_at=_hora(paso.cuando), response=paso.respuesta,
        )

    def _resumen(self, acreedor):
        deudas = Debt.objects.filter(creditor=acreedor).select_related("debtor")
        self.stdout.write(self.style.SUCCESS(
            f"Cartera de Patrimonio cargada: {Batch.objects.filter(creditor=acreedor).count()} entregas, "
            f"{deudas.count()} deudas y "
            f"{InboundEvent.objects.filter(payload__acreedor_rut=acreedor.tax_id).count()} avisos de DataBridge."
        ))
        for estado, rotulo in Debt.Status.choices:
            nombres = [d.debtor.full_name for d in deudas if d.status == estado]
            if nombres:
                self.stdout.write(f"    {rotulo:<26}{len(nombres)}   {', '.join(sorted(nombres))}")


def _entrega(acreedor, cartera):
    return Batch.objects.get(creditor=acreedor, external_id=cartera["lote"]["id_externo"])


def _campana(acreedor, nombre):
    """
    La campana del mes. La de septiembre viene en sql/AphofyxDB.sql; la de
    agosto, ya cerrada, la trae la demo.
    """
    agosto = nombre == CAMPANA_AGOSTO
    campana, _ = Campaign.objects.get_or_create(
        creditor=acreedor, name=nombre,
        defaults={
            "starts_on": date(2026, 8, 19) if agosto else date(2026, 9, 19),
            "ends_on": date(2026, 9, 18) if agosto else None,
            "status": Campaign.Status.FINISHED if agosto else Campaign.Status.RUNNING,
            "channels": ["whatsapp", "email"],
            "contact_attempts": 5,
        },
    )
    return campana


def _fechar(acreedor, desde, cuando):
    """
    Lo que se escribio desde `desde` queda con la fecha en que paso en la
    historia. Sin esto todo diria que ocurrio hoy, y el admin mostraria la
    cartera de agosto recibida en septiembre.
    """
    deudas = Debt.objects.filter(creditor=acreedor)
    filas = (
        (Batch.objects.filter(creditor=acreedor), ("received_at",)),
        (deudas, ("created_at", "updated_at")),
        (Debtor.objects.filter(pk__in=deudas.values("debtor_id")), ("created_at", "updated_at")),
        (DebtCharge.objects.filter(debt__in=deudas), ("created_at",)),
        (Forward.objects.filter(batch__creditor=acreedor), ("created_at", "next_attempt_at")),
        (InboundEvent.objects.filter(payload__acreedor_rut=acreedor.tax_id), ("received_at",)),
        (Campaign.objects.filter(creditor=acreedor), ("created_at", "updated_at")),
    )
    for consulta, campos in filas:
        for campo in campos:
            consulta.filter(**{f"{campo}__gte": desde}).update(**{campo: cuando})
