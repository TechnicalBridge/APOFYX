"""
Recepcion de una Cartera v1.

Implementa TB_web/docs/integracion/README.md §6. Las reglas que el esquema JSON
no puede expresar se aplican aca: digito verificador del RUT, cargos vencidos,
ids repetidos dentro del lote y el limite de mora del mandato.

DOS PRINCIPIOS QUE EXPLICAN CASI TODO EL ARCHIVO

1. **Aceptacion parcial.** Una deuda mal formada se rechaza sola, con su
   motivo, y las demas entran igual. Un RUT mal escrito no puede bloquear las
   otras 4.999.

2. **Idempotencia.** El mismo lote enviado dos veces devuelve la misma
   respuesta sin volver a procesar nada. El mismo id con otro contenido se
   rechaza: un numero de lote no se reutiliza.
"""

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from cartera.models import Batch, Debt, DebtCharge, Debtor
from crm.rut import es_valido, normalizar

#  Pasada esta mora APOFYX devuelve el caso al acreedor (docs §2.2). El limite
#  es de APOFYX, no del contrato: otra agencia podria usar otro.
MORA_MAXIMA_DIAS = 120

MOTIVOS_DE_RETIRO = {"pago_directo", "acuerdo_directo", "error", "disputa_resuelta", "otro"}

CAMPOS_DEUDA = {
    "id_externo", "accion", "motivo_retiro", "deudor", "moneda", "concepto",
    "referencias", "cargos",
}
CAMPOS_CARGO = {"concepto", "periodo", "monto", "fecha_vencimiento"}


class CarteraInvalida(Exception):
    """El lote completo no se puede procesar. Nada de el entra."""

    def __init__(self, codigo, mensaje, status=400):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.status = status


def huella(payload):
    """Huella estable del contenido, para distinguir un reenvio de un cambio."""
    texto = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _error(campo, codigo, mensaje):
    return {"campo": campo, "codigo": codigo, "mensaje": mensaje}


def _fecha(valor):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


def _monto(valor, moneda):
    """Devuelve el monto como Decimal, o None si no sirve."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    try:
        monto = Decimal(str(valor))
    except InvalidOperation:
        return None
    if monto <= 0:
        return None
    if moneda == "CLP" and monto != monto.to_integral_value():
        return None
    if monto.as_tuple().exponent < -2:
        return None
    return monto


def _validar_deuda(deuda, corte, vistos):
    """
    Revisa una deuda y devuelve (errores, datos_utiles).

    Devolver los datos ya convertidos evita volver a parsear fechas y montos
    mas abajo, que es donde se cuelan las diferencias entre lo validado y lo
    guardado.
    """
    errores = []
    id_externo = deuda.get("id_externo")
    if not id_externo:
        return [_error("id_externo", "id_externo_faltante", "La deuda no trae id_externo")], None
    if id_externo in vistos:
        return [_error("id_externo", "id_duplicado_en_lote",
                       f"{id_externo} viene dos veces en el mismo lote")], None

    accion = deuda.get("accion", "registrar")
    if accion not in ("registrar", "retirar"):
        errores.append(_error("accion", "accion_invalida", "La accion va como registrar o retirar"))
        return errores, None

    if accion == "retirar":
        motivo = deuda.get("motivo_retiro")
        if motivo not in MOTIVOS_DE_RETIRO:
            errores.append(_error("motivo_retiro", "motivo_invalido",
                                  "Un retiro necesita un motivo valido"))
        return errores, {"accion": "retirar", "motivo": deuda.get("motivo_retiro")}

    deudor = deuda.get("deudor") or {}
    rut = normalizar(deudor.get("rut"))
    if not es_valido(rut):
        errores.append(_error("deudor.rut", "rut_invalido",
                              "El RUT no cumple el formato o el digito verificador no corresponde"))
    if not (deudor.get("correo") or deudor.get("telefono")):
        errores.append(_error("deudor", "sin_canal_contacto",
                              "El deudor no trae ni correo ni telefono"))
    if deudor.get("tipo") not in ("persona", "empresa"):
        errores.append(_error("deudor.tipo", "tipo_invalido", "El tipo va como persona o empresa"))
    if not deudor.get("nombre"):
        errores.append(_error("deudor.nombre", "nombre_faltante", "El deudor no trae nombre"))

    moneda = deuda.get("moneda")
    if moneda not in ("CLP", "UF"):
        errores.append(_error("moneda", "moneda_invalida", "La moneda va como CLP o UF"))
    if not deuda.get("concepto"):
        errores.append(_error("concepto", "concepto_faltante", "La deuda no trae concepto"))

    cargos, vencimientos = [], []
    crudos = deuda.get("cargos")
    if not isinstance(crudos, list) or not crudos:
        errores.append(_error("cargos", "sin_cargos", "La deuda no trae cargos"))
    else:
        for i, cargo in enumerate(crudos):
            monto = _monto(cargo.get("monto"), moneda)
            if monto is None:
                errores.append(_error(f"cargos[{i}].monto", "monto_invalido",
                                      "Monto menor o igual a cero, con decimales en pesos, "
                                      "o con mas de dos decimales en UF"))
                continue
            vence = _fecha(cargo.get("fecha_vencimiento"))
            if vence is None:
                errores.append(_error(f"cargos[{i}].fecha_vencimiento", "fecha_invalida",
                                      "La fecha va como 2026-09-05"))
                continue
            if vence >= corte:
                errores.append(_error(f"cargos[{i}].fecha_vencimiento", "cargo_no_vencido",
                                      f"Vence el {vence} y el corte es el {corte}: todavia no es mora"))
                continue
            if not cargo.get("concepto"):
                errores.append(_error(f"cargos[{i}].concepto", "concepto_faltante",
                                      "El cargo no trae concepto"))
                continue
            vencimientos.append(vence)
            cargos.append({
                "concepto": cargo["concepto"], "periodo": cargo.get("periodo"),
                "monto": monto, "vence": vence,
            })

    mora = (corte - min(vencimientos)).days if vencimientos else 0
    if mora > MORA_MAXIMA_DIAS:
        errores.append(_error("cargos", "mora_fuera_de_mandato",
                              f"{mora} dias de mora: pasados los {MORA_MAXIMA_DIAS} "
                              "el caso vuelve al acreedor"))

    if errores:
        return errores, None
    return [], {
        "accion": "registrar", "rut": rut, "deudor": deudor, "moneda": moneda,
        "concepto": deuda["concepto"], "referencias": deuda.get("referencias") or {},
        "cargos": cargos, "mora": mora,
    }


def _campos_ignorados(payload):
    """Lo que vino y no se conoce. El receptor es tolerante, pero lo avisa."""
    sobras = set(payload) - {"version", "lote", "deudas"}
    sobras |= {f"lote.{c}" for c in set(payload.get("lote") or {})
               - {"id_externo", "fecha_corte", "emitido_en", "acreedor", "mandato"}}
    for deuda in payload.get("deudas") or []:
        if isinstance(deuda, dict):
            sobras |= {f"deudas[].{c}" for c in set(deuda) - CAMPOS_DEUDA}
            for cargo in deuda.get("cargos") or []:
                if isinstance(cargo, dict):
                    sobras |= {f"deudas[].cargos[].{c}" for c in set(cargo) - CAMPOS_CARGO}
    return sorted(sobras)


@transaction.atomic
def recibir_cartera(creditor, payload, source=Batch.Source.API):
    """
    Procesa una Cartera v1 y devuelve la respuesta del contrato (§6.5).

    `creditor` sale de la credencial, no del cuerpo: un campo del cuerpo se
    puede falsificar, la clave no.
    """
    if not isinstance(payload, dict):
        raise CarteraInvalida("cuerpo_invalido", "El cuerpo tiene que ser un objeto JSON")
    if payload.get("version") != "1.0":
        raise CarteraInvalida("version_no_soportada",
                              "Esta version del contrato es la 1.0")

    lote = payload.get("lote") or {}
    id_externo = lote.get("id_externo")
    corte = _fecha(lote.get("fecha_corte"))
    if not id_externo or corte is None:
        raise CarteraInvalida("lote_incompleto", "El lote necesita id_externo y fecha_corte")

    rut_declarado = normalizar((lote.get("acreedor") or {}).get("rut"))
    if rut_declarado != creditor.tax_id:
        raise CarteraInvalida(
            "acreedor_no_coincide",
            f"La cartera dice ser de {rut_declarado} y la clave es de {creditor.tax_id}",
            status=403,
        )

    deudas = payload.get("deudas")
    if not isinstance(deudas, list) or not deudas:
        raise CarteraInvalida("sin_deudas", "El lote no trae deudas")

    # ---- Idempotencia ----
    firma = huella(payload)
    anterior = Batch.objects.filter(creditor=creditor, external_id=id_externo).first()
    if anterior:
        if anterior.payload_hash == firma:
            return {**anterior.response, "repetido": True}
        raise CarteraInvalida(
            "lote_id_reutilizado",
            f"El lote {id_externo} ya se recibio con otro contenido",
            status=409,
        )

    batch = Batch.objects.create(
        creditor=creditor, external_id=id_externo, cut_off=corte,
        source=source, payload_hash=firma, received_count=len(deudas),
    )

    resultados = []
    vistos = set()
    aceptadas = 0

    for deuda in deudas:
        if not isinstance(deuda, dict):
            resultados.append({"id_externo": None, "resultado": "rechazada",
                               "errores": [_error("", "deuda_invalida", "La deuda no es un objeto")]})
            continue

        errores, datos = _validar_deuda(deuda, corte, vistos)
        id_deuda = deuda.get("id_externo")
        if id_deuda:
            vistos.add(id_deuda)
        if errores:
            resultados.append({"id_externo": id_deuda, "resultado": "rechazada", "errores": errores})
            continue

        existente = Debt.objects.filter(creditor=creditor, external_id=id_deuda).first()
        if existente and existente.status == Debt.Status.PAID:
            resultados.append({
                "id_externo": id_deuda, "resultado": "rechazada",
                "errores": [_error("id_externo", "deuda_saldada",
                                   "Esa deuda ya se pago y no se puede modificar")],
            })
            continue

        if datos["accion"] == "retirar":
            if not existente:
                resultados.append({
                    "id_externo": id_deuda, "resultado": "rechazada",
                    "errores": [_error("id_externo", "deuda_no_encontrada",
                                       "No hay ninguna deuda con ese id para retirar")],
                })
                continue
            existente.status = Debt.Status.WITHDRAWN
            existente.withdrawn_reason = datos["motivo"]
            existente.last_batch = batch
            existente.save(update_fields=["status", "withdrawn_reason", "last_batch", "updated_at"])
            aceptadas += 1
            resultados.append({"id_externo": id_deuda, "resultado": "retirada"})
            continue

        resultado = _guardar_deuda(creditor, batch, id_deuda, datos, existente)
        aceptadas += 1
        resultados.append({
            "id_externo": id_deuda, "resultado": resultado,
            "mora_dias": datos["mora"], "tramo": Debt.tramo(datos["mora"]),
        })

    batch.accepted_count = aceptadas
    batch.rejected_count = len(deudas) - aceptadas
    batch.status = Batch.Status.PROCESSED if aceptadas else Batch.Status.REJECTED
    respuesta = {
        "lote": id_externo,
        "repetido": False,
        "recibidas": len(deudas),
        "aceptadas": aceptadas,
        "rechazadas": batch.rejected_count,
        "resultados": resultados,
        "campos_ignorados": _campos_ignorados(payload),
    }
    batch.response = respuesta
    batch.save(update_fields=["accepted_count", "rejected_count", "status", "response"])

    #  Si DataBridge esta configurado, la entrega queda en la bandeja para
    #  pasarsela. Dentro de esta misma transaccion: si la recepcion se
    #  deshace, el reenvio tambien.
    from .reenvio import encolar
    encolar(batch)
    return respuesta


SE_CONSERVAN = (Debt.Status.OPEN, Debt.Status.REPACTED, Debt.Status.DISPUTED)


def _guardar_deuda(creditor, batch, id_deuda, datos, existente):
    """Crea o actualiza la deuda y reemplaza sus cargos."""
    deudor_datos = datos["deudor"]
    deudor, _ = Debtor.objects.update_or_create(
        tax_id=datos["rut"],
        defaults={
            "kind": Debtor.Kind.PERSON if deudor_datos["tipo"] == "persona" else Debtor.Kind.COMPANY,
            "full_name": deudor_datos["nombre"],
            "email": deudor_datos.get("correo") or None,
            "phone": deudor_datos.get("telefono") or None,
        },
    )

    nuevos = [
        (c["concepto"], c["periodo"], c["monto"], c["vence"])
        for c in sorted(datos["cargos"], key=lambda c: (c["vence"], c["concepto"]))
    ]

    if existente is None:
        deuda = Debt.objects.create(
            creditor=creditor, debtor=deudor, external_id=id_deuda,
            currency=datos["moneda"], concept=datos["concepto"],
            refs=datos["referencias"], first_batch=batch, last_batch=batch,
        )
        _reemplazar_cargos(deuda, nuevos)
        return "registrada"

    actuales = [
        (c.concept, c.period, c.amount, c.due_date)
        for c in existente.charges.order_by("due_date", "concept")
    ]
    #  Un convenio o una disputa no se borran porque el acreedor vuelva a mandar
    #  la deuda en la cartera del mes: se entero de ellos por los eventos, y
    #  reenviar la cartera no es una decision sobre ese deudor. Solo un retiro
    #  se deshace al volver a registrar.
    estado = existente.status if existente.status in SE_CONSERVAN else Debt.Status.OPEN
    sin_cambios = (
        actuales == nuevos
        and existente.debtor_id == deudor.id
        and existente.concept == datos["concepto"]
        and existente.currency == datos["moneda"]
        and existente.status == estado
    )
    existente.debtor = deudor
    existente.currency = datos["moneda"]
    existente.concept = datos["concepto"]
    existente.refs = datos["referencias"]
    existente.status = estado
    existente.withdrawn_reason = None
    existente.last_batch = batch
    existente.save()
    if not sin_cambios:
        _reemplazar_cargos(existente, nuevos)
    return "sin_cambios" if sin_cambios else "actualizada"


def _reemplazar_cargos(deuda, cargos):
    """
    Los cargos se reemplazan, no se acumulan.

    El acreedor manda lo que se debe HOY. Si pago una parte en la oficina,
    reenvia la deuda con el saldo menor, y conservar los cargos viejos dejaria
    a APOFYX cobrando un monto que ya no existe.
    """
    deuda.charges.all().delete()
    DebtCharge.objects.bulk_create([
        DebtCharge(debt=deuda, concept=concepto, period=periodo, amount=monto, due_date=vence)
        for concepto, periodo, monto, vence in cargos
    ])
