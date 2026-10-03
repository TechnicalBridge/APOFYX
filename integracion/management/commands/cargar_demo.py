"""
Carga la historia de la demo: la cartera de tres clientes de rubros distintos,
con cada deudor en una situacion distinta.

    python manage.py cargar_demo
    python manage.py cargar_demo --reemplazar

Es la misma historia que cuentan los datos de ejemplo de DataBridge (y, para
Patrimonio, los suyos), vista desde APOFYX. DataBridge cobra desde 30 dias de
mora: a la deuda con menos la rechaza, y APOFYX la gestiona por su cuenta.

Patrimonio Inmuebles (arriendos) entrego dos carteras, la del corte del 18 de
agosto y la del 18 de septiembre. APOFYX las recibio, se las paso a DataBridge
el dia en que empezaba la campana de cada mes, y DataBridge le fue avisando lo
que hacia cada deudor:

    Felipe          acepto 6 cuotas y lleva 3 pagadas            en convenio
    Valentina       debe 13 dias: DataBridge no la tomo          en gestion
    Comercial Nandu debe tres meses en UF                        en gestion
    Tomas           pago en la oficina y Patrimonio lo retiro    retirada
    Rodrigo         debe cuatro meses                            en gestion
    Carolina        pago todo de una vez                         pagada
    La Espiga       acepto 3 cuotas en UF y pago la primera      en convenio
    Ignacio         dejo el depto, acepto 6 cuotas y no pago     en convenio
    Daniela         acepto 3 cuotas y las pago juntas            pagada

Instituto Andes (aranceles) subio su planilla al portal con el corte del 18 de
septiembre, y Clinica Dental Sonrisa Norte (tratamientos de un solo cargo)
entrego la suya por API:

    Benjamin        debe tres aranceles                          en gestion
    Antonia         debe 8 dias: DataBridge no la tomo           en gestion
    Josefina        pago sus dos aranceles con Webpay            pagada
    Patricio        debe una ortodoncia de julio                 en gestion
    Fernanda        acepto 6 cuotas por un implante y pago una   en convenio

Todo pasa por el mismo codigo que una cartera de verdad: recibir_cartera valida
y guarda, recibir_evento pone al dia cada estado. La unica diferencia es que no
se reenvia nada, ni a DataBridge ni al cliente: es historia, ya ocurrio.

Cada cliente se carga solo si no tiene cartera en APOFYX. Si ya tiene una (la
de una corrida de la cadena completa, por ejemplo), no se toca, salvo con
--reemplazar. Patrimonio tiene que estar entre los clientes; Instituto Andes y
Sonrisa Norte vienen en sql/AphofyxDB.sql, y si faltan, su parte se omite.
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
RUT_ANDES = "77812341-K"
RUT_SONRISA = "76998877-7"
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

def _poca_mora(dias):
    """DataBridge cobra desde 30 dias de mora: con menos, la deuda se rechaza sola."""
    return [{"campo": "cargos", "codigo": "bajo_umbral_mora",
             "mensaje": f"Tiene {dias} dias de mora: DataBridge recibe deudas desde 30 dias de mora"}]


UN_MES = _poca_mora(13)


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


def _evento(cuando, tipo, lote, rut=RUT_PATRIMONIO, **datos):
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
        "acreedor_rut": rut,
        "lote_id_externo": lote,
        "datos": datos,
    }


def _convenio(cuando, lote, contrato, cuotas, monto, moneda, primera, rut=RUT_PATRIMONIO):
    return _evento(cuando, "repactacion.aceptada", lote, rut, deuda_id_externo=contrato, cuotas=cuotas,
                   monto_cuota=monto, moneda=moneda, primera_cuota=primera)


def _pago(cuando, contrato, pago_id, monto, medio, moneda="CLP", monto_clp=None, valor_uf=None,
          lote=LOTE_SEPTIEMBRE, rut=RUT_PATRIMONIO):
    datos = {"deuda_id_externo": contrato, "pago_id": pago_id, "monto": monto, "moneda": moneda,
             "monto_clp": monto if monto_clp is None else monto_clp}
    if valor_uf is not None:
        datos["valor_uf"] = valor_uf
    datos.update(medio=medio, pagado_en=_hora(cuando).isoformat())
    return _evento(cuando, "pago.confirmado", lote, rut, **datos)


def _saldada(cuando, contrato, lote=LOTE_SEPTIEMBRE, rut=RUT_PATRIMONIO):
    return _evento(cuando, "deuda.saldada", lote, rut, deuda_id_externo=contrato,
                   saldada_en=_hora(cuando).isoformat())


def _procesado(cuando, lote, corte, respuesta, tramos, rut=RUT_PATRIMONIO):
    return _evento(cuando, "lote.procesado", lote, rut, periodo=corte[:7], fecha_corte=corte,
                   recibidas=respuesta["recibidas"], aceptadas=respuesta["aceptadas"],
                   rechazadas=respuesta["rechazadas"], tramos=tramos)


# ---------------------------------------------------------------------------
#  La historia, en el orden en que paso
# ---------------------------------------------------------------------------

CAMPANA_AGOSTO = "Patrimonio - Arriendos - Agosto 2026"
CAMPANA_SEPTIEMBRE = "Patrimonio - Arriendos - Septiembre 2026"

class Entrega(NamedTuple):
    """El cliente entrega una cartera. APOFYX la recibe y anota el reenvio."""
    cuando: str
    cartera: dict
    lote_en_databridge: str
    origen: str = Batch.Source.API


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


# ---------------------------------------------------------------------------
#  Instituto Andes: aranceles mensuales, por la planilla del portal
# ---------------------------------------------------------------------------

def _estudiante(matricula, deudor, carrera, aranceles):
    return {
        "id_externo": matricula,
        "deudor": deudor,
        "moneda": "CLP",
        "concepto": f"Arancel {carrera}",
        "referencias": {"matricula": matricula, "carrera": carrera},
        "cargos": [
            {"concepto": f"Arancel {MESES[mes]}", "periodo": mes, "monto": 185000,
             "fecha_vencimiento": f"{mes}-10"}
            for mes in aranceles
        ],
    }


BENJAMIN = {"rut": "21345678-4", "tipo": "persona", "nombre": "Benjamín Araya Toro",
            "correo": "benjamin.araya@correo.cl", "telefono": "+56944120387"}
ANTONIA = {"rut": "21987654-8", "tipo": "persona", "nombre": "Antonia Reyes Lagos",
           "correo": "antonia.reyes@correo.cl", "telefono": "+56930218865"}
JOSEFINA = {"rut": "20876543-4", "tipo": "persona", "nombre": "Josefina Vidal Cortés",
            "correo": "josefina.vidal@correo.cl", "telefono": "+56977345120"}

#  El portal arma el numero del lote con la fecha de corte.
ANDES_SEPTIEMBRE = {
    "version": "1.0",
    "lote": {"id_externo": "CSV-2026-09-18-1", "fecha_corte": "2026-09-18",
             "acreedor": {"rut": RUT_ANDES, "razon_social": "Instituto Profesional Andes Ltda.",
                          "nombre_fantasia": "Instituto Andes"}},
    "deudas": [
        _estudiante("AND-2025-0412", BENJAMIN, "Técnico en Enfermería", ["2026-07", "2026-08", "2026-09"]),
        _estudiante("AND-2026-0087", ANTONIA, "Técnico en Párvulos", ["2026-09"]),
        _estudiante("AND-2024-0931", JOSEFINA, "Ingeniería en Informática", ["2026-08", "2026-09"]),
    ],
}
LOTE_ANDES = "APX-2026-09-19-005"
CAMPANA_ANDES = "Andes - Aranceles - Septiembre 2026"
RESPUESTA_ANDES = _respuesta(LOTE_ANDES, [
    _entro("AND-2025-0412", "registrada", 70),
    {"id_externo": "AND-2026-0087", "resultado": "rechazada", "errores": _poca_mora(8)},
    _entro("AND-2024-0931", "registrada", 39),
])

HISTORIA_ANDES = [
    Entrega("2026-09-18 11:20:04", ANDES_SEPTIEMBRE, LOTE_ANDES, Batch.Source.FILE),
    Reenvio("2026-09-19 10:20:00", ANDES_SEPTIEMBRE, CAMPANA_ANDES, RESPUESTA_ANDES),
    _procesado("2026-09-19 10:20", LOTE_ANDES, "2026-09-18", RESPUESTA_ANDES,
               [{"tramo": "31-90", "deudas": 2, "promedio_clp": 462500}], rut=RUT_ANDES),
    _pago("2026-09-22 20:10", "AND-2024-0931", "121", 370000, "webpay", lote=LOTE_ANDES, rut=RUT_ANDES),
    _saldada("2026-09-22 20:10", "AND-2024-0931", lote=LOTE_ANDES, rut=RUT_ANDES),
]


# ---------------------------------------------------------------------------
#  Sonrisa Norte: tratamientos dentales de un solo cargo, por API
# ---------------------------------------------------------------------------

def _tratamiento(presupuesto, deudor, tratamiento, cargo, monto, vence):
    return {
        "id_externo": presupuesto,
        "deudor": deudor,
        "moneda": "CLP",
        "concepto": tratamiento,
        "referencias": {"presupuesto": presupuesto, "tratamiento": tratamiento},
        "cargos": [{"concepto": cargo, "monto": monto, "fecha_vencimiento": vence}],
    }


PATRICIO = {"rut": "13579246-2", "tipo": "persona", "nombre": "Patricio Muñoz Salas",
            "correo": "patricio.munoz@correo.cl", "telefono": "+56951287734"}
FERNANDA = {"rut": "16789012-1", "tipo": "persona", "nombre": "Fernanda Silva Rojas",
            "correo": "fernanda.silva@correo.cl", "telefono": "+56962054418"}

SONRISA_SEPTIEMBRE = {
    "version": "1.0",
    "lote": {"id_externo": "SN-2026-09-18", "fecha_corte": "2026-09-18",
             "acreedor": {"rut": RUT_SONRISA, "razon_social": "Servicios Dentales Sonrisa Norte SpA",
                          "nombre_fantasia": "Clínica Dental Sonrisa Norte"}},
    "deudas": [
        _tratamiento("SN-2026-118", PATRICIO, "Tratamiento de ortodoncia", "Ortodoncia, saldo del presupuesto",
                     890000, "2026-07-05"),
        _tratamiento("SN-2026-093", FERNANDA, "Implante dental", "Implante dental", 1450000, "2026-06-20"),
    ],
}
LOTE_SONRISA = "APX-2026-09-19-006"
CAMPANA_SONRISA = "Sonrisa Norte - Tratamientos - Septiembre 2026"
#  Dos deudas de un solo cargo: con la regla de meses impagos se habrian rechazado.
RESPUESTA_SONRISA = _respuesta(LOTE_SONRISA, [
    _entro("SN-2026-118", "registrada", 75),
    _entro("SN-2026-093", "registrada", 90),
])

HISTORIA_SONRISA = [
    Entrega("2026-09-18 16:40:11", SONRISA_SEPTIEMBRE, LOTE_SONRISA),
    Reenvio("2026-09-19 10:25:00", SONRISA_SEPTIEMBRE, CAMPANA_SONRISA, RESPUESTA_SONRISA),
    _procesado("2026-09-19 10:25", LOTE_SONRISA, "2026-09-18", RESPUESTA_SONRISA,
               [{"tramo": "31-90", "deudas": 2, "promedio_clp": 1170000}], rut=RUT_SONRISA),
    _convenio("2026-09-21 11:00", LOTE_SONRISA, "SN-2026-093", 6, 241666, "CLP", "2026-10-21", rut=RUT_SONRISA),
    _pago("2026-09-21 11:05", "SN-2026-093", "117", 241666, "khipu", lote=LOTE_SONRISA, rut=RUT_SONRISA),
]


# ---------------------------------------------------------------------------
#  Los tres clientes de la demo
# ---------------------------------------------------------------------------

class Demo(NamedTuple):
    rut: str
    nombre: str
    historia: list
    #  Las campanas que usa la historia, por si la base no las trae.
    campanas: dict
    #  Sin Patrimonio no hay demo; sin los otros, solo falta su parte.
    obligatoria: bool = False

    @property
    def entregas(self):
        return [paso.cartera for paso in self.historia if isinstance(paso, Entrega)]


DEMOS = [
    Demo(RUT_PATRIMONIO, "Patrimonio Inmuebles", HISTORIA, {
        CAMPANA_AGOSTO: {"starts_on": date(2026, 8, 19), "ends_on": date(2026, 9, 18),
                         "status": Campaign.Status.FINISHED, "channels": ["whatsapp", "email"],
                         "contact_attempts": 5},
        CAMPANA_SEPTIEMBRE: {"starts_on": date(2026, 9, 19), "status": Campaign.Status.RUNNING,
                             "channels": ["whatsapp", "email"], "contact_attempts": 5},
    }, obligatoria=True),
    Demo(RUT_ANDES, "Instituto Andes", HISTORIA_ANDES, {
        CAMPANA_ANDES: {"starts_on": date(2026, 9, 19), "status": Campaign.Status.RUNNING,
                        "channels": ["whatsapp", "email"], "contact_attempts": 3},
    }),
    Demo(RUT_SONRISA, "Sonrisa Norte", HISTORIA_SONRISA, {
        CAMPANA_SONRISA: {"starts_on": date(2026, 9, 4), "status": Campaign.Status.RUNNING,
                          "channels": ["whatsapp", "sms"], "contact_attempts": 3},
    }),
]

#  Lo que tarda un aviso de DataBridge en llegar: su bandeja sale cada pocos segundos.
DEMORA_DEL_AVISO = timedelta(seconds=4)


class Command(BaseCommand):
    help = "Carga la cartera de la demo: tres clientes de rubros distintos, cada deudor en otra situacion."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reemplazar", action="store_true",
            help="Borra la cartera que los clientes de la demo tengan en APOFYX (entregas, deudas, "
                 "reenvios y eventos) y carga la de la demo en su lugar.",
        )

    def handle(self, *args, **opciones):
        patrimonio = DEMOS[0]
        if not Creditor.objects.filter(tax_id=patrimonio.rut).exists():
            raise CommandError(
                f"Patrimonio Inmuebles ({RUT_PATRIMONIO}) no esta entre los clientes. Viene en "
                "sql/AphofyxDB.sql; en una base anterior, corre "
                "sql/migraciones/2026-09-19-patrimonio-como-acreedor.sql"
            )

        for demo in DEMOS:
            acreedor = Creditor.objects.filter(tax_id=demo.rut).first()
            if acreedor is None:
                self.stdout.write(f"{demo.nombre} ({demo.rut}) no esta entre los clientes: su parte se omite.")
                continue
            with transaction.atomic():
                entregas = Batch.objects.filter(creditor=acreedor)
                if entregas.exists():
                    if not opciones["reemplazar"]:
                        self._no_se_toca(demo, entregas)
                        continue
                    self._borrar(demo, acreedor)
                self._cargar(demo, acreedor)
            self._resumen(demo, acreedor)

    # ------------------------------------------------------------------

    def _no_se_toca(self, demo, entregas):
        suyas = {cartera["lote"]["id_externo"]: huella(cartera) for cartera in demo.entregas}
        if dict(entregas.values_list("external_id", "payload_hash")) == suyas:
            self.stdout.write(f"La demo de {demo.nombre} ya estaba cargada.")
            return
        self.stdout.write(
            f"{demo.nombre} ya tiene cartera en APOFYX ({entregas.count()} entrega(s)) y no se toca.\n"
            "Para cambiarla por la de la demo: python manage.py cargar_demo --reemplazar"
        )

    def _borrar(self, demo, acreedor):
        """Todo lo de la cartera del cliente. Lo demas (campanas, claves, cuentas) queda."""
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
        self.stdout.write(f"Borrada la cartera anterior de {demo.nombre}: {cuantas} deuda(s).")

    def _cargar(self, demo, acreedor):
        for paso in demo.historia:
            desde = timezone.now()
            if isinstance(paso, Entrega):
                self._recibir(acreedor, paso)
                cuando = _hora(paso.cuando)
            elif isinstance(paso, Reenvio):
                self._reenviar(demo, acreedor, paso)
                cuando = _hora(paso.cuando)
            else:
                recibir_evento(paso, reenviar=False)
                cuando = datetime.fromisoformat(paso["ocurrido_en"]) + DEMORA_DEL_AVISO
            _fechar(acreedor, desde, cuando)

    def _recibir(self, acreedor, paso):
        respuesta = recibir_cartera(acreedor, paso.cartera, source=paso.origen, reenviar=False)
        if respuesta["rechazadas"]:
            #  Una demo a medias contaria otra historia: mejor no cargarla.
            raise CommandError(f"La cartera {respuesta['lote']} de la demo no entro completa: "
                               f"{respuesta['resultados']}")
        #  El reenvio queda anotado al recibir, esperando la campana del mes.
        Forward.objects.create(batch=_entrega(acreedor, paso.cartera),
                               external_id=paso.lote_en_databridge,
                               status=Forward.Status.WAITING_CAMPAIGN)

    def _reenviar(self, demo, acreedor, paso):
        entrega = _entrega(acreedor, paso.cartera)
        entrega.campaign = _campana(acreedor, paso.campana, demo.campanas[paso.campana])
        entrega.save(update_fields=["campaign"])
        Forward.objects.filter(batch=entrega).update(
            status=Forward.Status.SENT, sent_at=_hora(paso.cuando), response=paso.respuesta,
        )

    def _resumen(self, demo, acreedor):
        deudas = Debt.objects.filter(creditor=acreedor).select_related("debtor")
        self.stdout.write(self.style.SUCCESS(
            f"Cartera de {demo.nombre} cargada: {Batch.objects.filter(creditor=acreedor).count()} entregas, "
            f"{deudas.count()} deudas y "
            f"{InboundEvent.objects.filter(payload__acreedor_rut=acreedor.tax_id).count()} avisos de DataBridge."
        ))
        for estado, rotulo in Debt.Status.choices:
            nombres = [d.debtor.full_name for d in deudas if d.status == estado]
            if nombres:
                self.stdout.write(f"    {rotulo:<26}{len(nombres)}   {', '.join(sorted(nombres))}")


def _entrega(acreedor, cartera):
    return Batch.objects.get(creditor=acreedor, external_id=cartera["lote"]["id_externo"])


def _campana(acreedor, nombre, como):
    """
    La campana del mes. Algunas vienen en sql/AphofyxDB.sql (la de septiembre
    de Patrimonio y la de Sonrisa Norte); las demas las trae la demo.
    """
    campana, _ = Campaign.objects.get_or_create(creditor=acreedor, name=nombre, defaults=como)
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
