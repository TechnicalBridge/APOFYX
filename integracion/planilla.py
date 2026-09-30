"""
La variante CSV de la Cartera v1 (contrato, seccion 6.6), convertida al JSON
del contrato.

Es para la empresa sin sistema propio: la sube desde su portal. No hay una
segunda ingesta: la planilla se traduce y entra por `recibir_cartera`, con las
mismas validaciones, la misma aceptacion parcial y la misma idempotencia que
una cartera por API. Son las mismas reglas del lector de DataBridge.

Lo que se rechaza aca es solo lo estructural —columnas que faltan, una deuda
cuyas filas no coinciden—, con el numero de fila, porque quien lo arregla esta
mirando una planilla. Lo de negocio (RUT, montos, mora) lo decide la ingesta,
deuda por deuda.
"""

import csv
import io
from decimal import Decimal, InvalidOperation

from .intake import CarteraInvalida

COLUMNAS = [
    "deuda_id", "accion", "motivo_retiro", "deudor_rut", "deudor_tipo", "deudor_nombre",
    "deudor_correo", "deudor_telefono", "moneda", "concepto", "referencias",
    "cargo_concepto", "cargo_periodo", "cargo_monto", "cargo_vencimiento",
]
#  Tienen que repetirse iguales en cada fila de los cargos de una deuda.
DE_LA_DEUDA = [
    "accion", "deudor_rut", "deudor_tipo", "deudor_nombre", "deudor_correo",
    "deudor_telefono", "moneda", "concepto", "referencias",
]
#  Una fila con las cuatro vacias es un cliente al dia.
DEL_CARGO = ["cargo_concepto", "cargo_periodo", "cargo_monto", "cargo_vencimiento"]
MAX_FILAS = 50_000


def _invalido(mensaje):
    return CarteraInvalida("csv_invalido", mensaje)


def leer(contenido, lote_id, fecha_corte, acreedor_rut):
    """La planilla como una Cartera v1. `contenido` son los bytes del archivo."""
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise _invalido("El archivo no esta en UTF-8. En Excel: Guardar como > CSV UTF-8.") from error

    filas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    filas = [f for f in filas if any(celda.strip() for celda in f)]
    if not filas:
        raise _invalido("El archivo esta vacio")
    encabezado = [c.strip().lower() for c in filas[0]]
    faltan = [c for c in COLUMNAS if c not in encabezado]
    if faltan:
        raise _invalido("Faltan columnas del contrato: " + ", ".join(faltan)
                        + ". Use la plantilla, separada por punto y coma.")
    if len(filas) - 1 > MAX_FILAS:
        raise _invalido(f"El archivo tiene mas de {MAX_FILAS} filas: dividalo en varios lotes")
    indice = {nombre: i for i, nombre in enumerate(encabezado)}

    def celda(fila, nombre):
        i = indice[nombre]
        return fila[i].strip() if i < len(fila) else ""

    deudas, primera_fila, columnas_de, al_dia = {}, {}, {}, set()
    for n, fila in enumerate(filas[1:], start=2):     # como la numera Excel, con el encabezado en la 1
        id_deuda = celda(fila, "deuda_id")
        if not id_deuda:
            raise _invalido(f"Fila {n}: falta deuda_id")

        if celda(fila, "accion") == "retirar":
            if id_deuda in deudas:
                raise _invalido(f"Fila {n}: la deuda {id_deuda} ya aparece en la fila {primera_fila[id_deuda]}; "
                                "un retiro va en una sola fila")
            deudas[id_deuda] = {"id_externo": id_deuda, "accion": "retirar",
                                "motivo_retiro": celda(fila, "motivo_retiro")}
            primera_fila[id_deuda] = n
            continue

        suyas = [celda(fila, c) for c in DE_LA_DEUDA]
        con_cargo = any(celda(fila, c) for c in DEL_CARGO)
        deuda = deudas.get(id_deuda)
        if deuda is None:
            deuda = _nueva_deuda(id_deuda, fila, celda)
            deudas[id_deuda] = deuda
            primera_fila[id_deuda] = n
            columnas_de[id_deuda] = suyas
            if not con_cargo:
                al_dia.add(id_deuda)
                continue
        elif id_deuda in al_dia:
            raise _invalido(f"Fila {n}: la deuda {id_deuda} esta al dia en la fila {primera_fila[id_deuda]} "
                            "(sin cargos) y no puede traer cargos en otra")
        elif not con_cargo:
            raise _invalido(f"Fila {n}: la deuda {id_deuda} no trae el cargo. Un cliente al dia va en una sola "
                            "fila, sin columnas de cargo")
        elif "cargos" not in deuda:
            raise _invalido(f"Fila {n}: la deuda {id_deuda} se retira en la fila {primera_fila[id_deuda]} "
                            "y no puede traer cargos")
        elif suyas != columnas_de[id_deuda]:
            cual = next(c for c, a, b in zip(DE_LA_DEUDA, suyas, columnas_de[id_deuda]) if a != b)
            raise _invalido(f"Fila {n}: la deuda {id_deuda} tiene otro {cual} que en la fila "
                            f"{primera_fila[id_deuda]}. Las columnas de la deuda se repiten iguales en cada cargo")
        deuda["cargos"].append(_cargo(fila, celda, n, deuda["moneda"]))

    return {
        "version": "1.0",
        "lote": {"id_externo": lote_id, "fecha_corte": fecha_corte, "acreedor": {"rut": acreedor_rut}},
        "deudas": list(deudas.values()),
    }


def _nueva_deuda(id_deuda, fila, celda):
    deudor = {"rut": celda(fila, "deudor_rut"), "tipo": celda(fila, "deudor_tipo"),
              "nombre": celda(fila, "deudor_nombre")}
    for campo, columna in (("correo", "deudor_correo"), ("telefono", "deudor_telefono")):
        if celda(fila, columna):
            deudor[campo] = celda(fila, columna)
    deuda = {"id_externo": id_deuda, "deudor": deudor, "moneda": celda(fila, "moneda"),
             "concepto": celda(fila, "concepto")}
    referencias = {}
    for par in celda(fila, "referencias").split("|"):
        clave, _, valor = par.partition("=")
        if clave.strip() and valor:
            referencias[clave.strip()] = valor.strip()
    if referencias:
        deuda["referencias"] = referencias
    deuda["cargos"] = []
    return deuda


def _cargo(fila, celda, n, moneda):
    texto = celda(fila, "cargo_monto")
    if moneda == "CLP" and ("." in texto or "," in texto):
        #  520.000 se leeria como 520: en pesos no hay decimales, asi que un
        #  punto o una coma solo puede ser un separador de miles.
        raise _invalido(f"Fila {n}: el monto '{texto}' en pesos va sin puntos ni comas: 520000")
    try:
        valor = Decimal(texto.replace(",", "."))
    except InvalidOperation as error:
        raise _invalido(f"Fila {n}: el monto '{texto}' no es un numero. Sin separador de miles: "
                        "520000, o en UF 38,5") from error
    cargo = {"concepto": celda(fila, "cargo_concepto"),
             "monto": int(valor) if valor == valor.to_integral_value() else float(valor),
             "fecha_vencimiento": celda(fila, "cargo_vencimiento")}
    if celda(fila, "cargo_periodo"):
        cargo["periodo"] = celda(fila, "cargo_periodo")
    return cargo
