"""
Saca la cartera como una matriz de numeros, lista para entrenar un modelo.

    python manage.py exportar_features
    python manage.py exportar_features --salida cartera.csv --acreedor 76418902-7

Lee la vista `v_deuda_features`, que es donde vive la codificacion: label
encoding para lo que tiene orden (el tramo de mora) y one-hot para lo que no
(estado, moneda, tipo de deudor, canales de la campana). Las tablas siguen
guardando las categorias como texto, que es lo legible para el panel y lo que
el CHECK documenta.

Lo que sale de aqui se abre con pandas sin tocar nada:

    import pandas as pd
    datos = pd.read_csv("cartera.csv")
    X = datos.drop(columns=["deuda_id", "acreedor_id", "campana_id", "estado_pagada"])
    y = datos["estado_pagada"]
"""

import csv
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from crm.models import Creditor
from crm.rut import es_valido, normalizar


class Command(BaseCommand):
    help = "Exporta la cartera codificada (v_deuda_features) en CSV."

    def add_arguments(self, parser):
        parser.add_argument("--salida", help="Archivo donde escribir. Sin esto, sale por pantalla.")
        parser.add_argument("--acreedor", help="Solo la cartera de ese RUT.")

    def handle(self, *args, **opciones):
        if connection.vendor != "mysql":
            raise CommandError("La vista v_deuda_features es de MySQL: corre esto contra la base real.")

        consulta = "SELECT * FROM v_deuda_features"
        parametros = []
        if opciones["acreedor"]:
            rut = normalizar(opciones["acreedor"])
            if not es_valido(rut):
                raise CommandError(f"{opciones['acreedor']} no es un RUT valido")
            acreedor = Creditor.objects.filter(tax_id=rut).first()
            if acreedor is None:
                raise CommandError(f"No hay ningun acreedor con RUT {rut}")
            consulta += " WHERE acreedor_id = %s"
            parametros.append(acreedor.pk)
        consulta += " ORDER BY deuda_id"

        with connection.cursor() as cursor:
            cursor.execute(consulta, parametros)
            columnas = [c[0] for c in cursor.description]
            filas = cursor.fetchall()

        destino = open(opciones["salida"], "w", newline="", encoding="utf-8") if opciones["salida"] else sys.stdout
        try:
            escritor = csv.writer(destino)
            escritor.writerow(columnas)
            escritor.writerows(filas)
        finally:
            if opciones["salida"]:
                destino.close()
                self.stdout.write(self.style.SUCCESS(
                    f"{len(filas)} deuda(s) y {len(columnas)} columnas en {opciones['salida']}"))
