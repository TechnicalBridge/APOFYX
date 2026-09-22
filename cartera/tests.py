"""
Pruebas de la cartera recibida.

Lo que se recibe y como se valida se prueba en integracion/tests.py, que es
donde vive esa logica. Aca queda lo del modelo: que el DDL y los modelos digan
lo mismo, y que las restricciones que si viajan en la migracion funcionen.

A diferencia de crm y assistant, los CHECK de estas tablas estan declarados en
los modelos (models.CheckConstraint), asi que la base de pruebas SI los tiene y
se pueden ejercitar de verdad contra el motor.
"""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import skipUnless

from django.core.management import call_command
from django.db import DataError, IntegrityError, connection, transaction
from django.test import TestCase

from crm.esquema import valores_del_enum
from crm.models import Creditor, Industry

from .models import Batch, Debt, DebtCharge, Debtor


def crear_acreedor():
    rubro = Industry.objects.create(name="Corretaje y arriendos", slug="arriendos")
    return Creditor.objects.create(
        legal_name="Patrimonio Inmuebles SpA", trade_name="Patrimonio Inmuebles",
        tax_id="76418902-7", industry=rubro, status=Creditor.Status.ACTIVE,
    )


class ElDdlYLosModelosDicenLoMismo(TestCase):
    """La misma guardia que crm, para las tablas nuevas."""

    EQUIVALENCIAS = {
        ("cartera_batch", "source"): Batch.Source,
        ("cartera_batch", "status"): Batch.Status,
        ("cartera_debtor", "kind"): Debtor.Kind,
        ("cartera_debt", "status"): Debt.Status,
        ("cartera_debt", "currency"): Debt.Currency,
    }

    def test_cada_enum_ofrece_los_mismos_valores_que_su_modelo(self):
        for (tabla, columna), opciones in self.EQUIVALENCIAS.items():
            with self.subTest(columna=f"{tabla}.{columna}"):
                en_el_ddl = valores_del_enum(tabla, columna)
                self.assertIsNotNone(en_el_ddl, f"{tabla}.{columna} no es un ENUM en el DDL.")
                self.assertEqual(
                    en_el_ddl, set(opciones.values),
                    f"\n{tabla}.{columna} y {opciones.__qualname__} no dicen lo mismo."
                    f"\n  solo en el DDL:    {sorted(en_el_ddl - set(opciones.values))}"
                    f"\n  solo en el modelo: {sorted(set(opciones.values) - en_el_ddl)}",
                )

    def test_la_moneda_del_ddl_es_la_que_acepta_el_contrato(self):
        self.assertEqual(valores_del_enum("cartera_debt", "currency"), {"CLP", "UF"})


class LaBaseRechazaLoQueNoCorresponde(TestCase):
    """
    Estas restricciones existen en la base de pruebas porque viajan en la
    migracion. Es justo lo que las tablas viejas no tienen.
    """

    def setUp(self):
        self.acreedor = crear_acreedor()
        self.lote = Batch.objects.create(
            creditor=self.acreedor, external_id="PAT-1", cut_off=date(2026, 9, 18),
            payload_hash="x" * 64,
        )

    def test_un_deudor_sin_correo_ni_telefono(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Debtor.objects.create(tax_id="16482337-7", full_name="Sin contacto")

    def test_un_rut_con_puntos(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Debtor.objects.create(
                tax_id="16.482.337-7", full_name="Con puntos", email="x@y.cl"
            )

    def test_un_estado_que_no_existe(self):
        """
        La columna es un ENUM, asi que MySQL rechaza el valor por estar fuera
        de la lista (DataError) y no por violar una restriccion
        (IntegrityError), que era como se rechazaba con el CHECK. Lo que
        importa es lo mismo: no entra.
        """
        deudor = Debtor.objects.create(
            tax_id="16482337-7", full_name="Felipe Rojas", email="f@correo.cl"
        )
        deuda = Debt.objects.create(
            creditor=self.acreedor, debtor=deudor, external_id="CTR-1",
            concept="Arriendo", first_batch=self.lote, last_batch=self.lote,
        )
        deuda.status = "inventado"
        with self.assertRaises((IntegrityError, DataError)), transaction.atomic():
            deuda.save()

    def test_el_mismo_id_de_deuda_para_el_mismo_acreedor(self):
        deudor = Debtor.objects.create(
            tax_id="16482337-7", full_name="Felipe Rojas", email="f@correo.cl"
        )
        for _ in range(2):
            crear = lambda: Debt.objects.create(  # noqa: E731
                creditor=self.acreedor, debtor=deudor, external_id="CTR-1",
                concept="Arriendo", first_batch=self.lote, last_batch=self.lote,
            )
            if Debt.objects.exists():
                with self.assertRaises(IntegrityError), transaction.atomic():
                    crear()
            else:
                crear()

    def test_un_cargo_en_cero(self):
        deudor = Debtor.objects.create(
            tax_id="16482337-7", full_name="Felipe Rojas", email="f@correo.cl"
        )
        deuda = Debt.objects.create(
            creditor=self.acreedor, debtor=deudor, external_id="CTR-1",
            concept="Arriendo", first_batch=self.lote, last_batch=self.lote,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            DebtCharge.objects.create(
                debt=deuda, concept="Arriendo", amount=Decimal("0"),
                due_date=date(2026, 8, 5),
            )


class LosTramosCalzanConElPanel(TestCase):
    """
    Los tramos son los mismos de crm_portfoliohandover. Si se separaran, la
    entrega y el panel estarian contando cosas distintas con el mismo nombre.
    """

    def test_cada_mora_cae_en_su_tramo(self):
        self.assertEqual(Debt.tramo(1), "1-30")
        self.assertEqual(Debt.tramo(30), "1-30")
        self.assertEqual(Debt.tramo(31), "31-90")
        self.assertEqual(Debt.tramo(90), "31-90")
        self.assertEqual(Debt.tramo(91), "91-120")
        self.assertEqual(Debt.tramo(120), "91-120")
        self.assertEqual(Debt.tramo(121), ">120")

    def test_los_tres_primeros_son_los_del_ddl(self):
        del_panel = valores_del_enum("crm_portfoliohandover", "overdue_bracket")
        self.assertEqual(
            {Debt.tramo(15), Debt.tramo(60), Debt.tramo(100)}, del_panel,
            "Los tramos de la cartera y los de crm_portfoliohandover se separaron.",
        )


@skipUnless(connection.vendor == "mysql", "v_deuda_features es una vista de MySQL")
class LaCarteraCodificadaParaUnModelo(TestCase):
    """
    La vista `v_deuda_features` es donde las categorias se vuelven numeros. Las
    tablas siguen guardandolas como texto: es lo legible en el panel y lo que
    el CHECK documenta. Codificar ahi tambien obligaria a traducir en cada
    consulta y en el contrato, que viaja en texto.
    """

    def setUp(self):
        self.acreedor = crear_acreedor()
        self.entrega = Batch.objects.create(
            creditor=self.acreedor, external_id="PAT-2026-09-18-01",
            cut_off=date(2026, 9, 18), source=Batch.Source.API,
        )

    def deuda(self, **extra):
        deudor = Debtor.objects.create(
            tax_id=extra.pop("rut", "16482337-7"), kind=extra.pop("kind", Debtor.Kind.PERSON),
            full_name="Felipe Rojas", email=extra.pop("email", "felipe@correo.cl"),
            phone=extra.pop("phone", "+56987654321"),
        )
        deuda = Debt.objects.create(
            creditor=self.acreedor, debtor=deudor, external_id=extra.pop("external_id", "CTR-2025-014"),
            currency=extra.pop("currency", "CLP"), concept="Arriendo mensual",
            first_batch=self.entrega, last_batch=self.entrega, **extra,
        )
        DebtCharge.objects.create(debt=deuda, concept="Arriendo agosto", period="2026-08",
                                  amount=Decimal("520000"), due_date=date(2026, 8, 5))
        return deuda

    def fila(self, deuda):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM v_deuda_features WHERE deuda_id = %s", [deuda.pk])
            columnas = [c[0] for c in cursor.description]
            valores = cursor.fetchone()
        return dict(zip(columnas, valores))

    def test_el_tramo_va_con_label_encoding_porque_tiene_orden(self):
        """Los tramos se ordenan solos: a mas tramo, mas dificil de cobrar."""
        fila = self.fila(self.deuda())
        self.assertEqual(fila["dias_mora"], 44)
        self.assertEqual(fila["tramo_orden"], 2)          # 31-90
        self.assertEqual(fila["n_cargos"], 1)
        self.assertEqual(fila["monto_total"], Decimal("520000.00"))

    def test_el_estado_va_one_hot_y_solo_uno_queda_encendido(self):
        deuda = self.deuda()
        estados = [c for c in self.fila(deuda) if c.startswith("estado_")]
        self.assertEqual(len(estados), 5)
        self.assertEqual(sum(self.fila(deuda)[c] for c in estados), 1)
        self.assertEqual(self.fila(deuda)["estado_en_gestion"], 1)

        deuda.status = Debt.Status.REPACTED
        deuda.save(update_fields=["status"])
        fila = self.fila(deuda)
        self.assertEqual((fila["estado_en_gestion"], fila["estado_en_convenio"]), (0, 1))
        self.assertEqual(sum(fila[c] for c in estados), 1, "dos estados encendidos a la vez")

    def test_la_moneda_y_el_tipo_de_deudor_tambien_van_one_hot(self):
        uf = self.fila(self.deuda(external_id="CTR-2024-007", currency="UF", rut="76991245-2",
                                  kind=Debtor.Kind.COMPANY, phone=""))
        self.assertEqual((uf["moneda_uf"], uf["moneda_clp"]), (1, 0))
        self.assertEqual((uf["deudor_empresa"], uf["deudor_persona"]), (1, 0))
        self.assertEqual((uf["tiene_correo"], uf["tiene_telefono"]), (1, 0))

    def test_una_deuda_sin_campana_no_inventa_canales(self):
        fila = self.fila(self.deuda())
        for canal in ("canal_whatsapp", "canal_correo", "canal_sms"):
            self.assertEqual(fila[canal], 0, canal)
        self.assertEqual(fila["intentos_de_contacto"], 0)

    def test_el_comando_exporta_la_matriz_en_csv(self):
        self.deuda()
        salida = Path(tempfile.mkdtemp()) / "cartera.csv"
        call_command("exportar_features", salida=str(salida), acreedor="76418902-7")

        lineas = salida.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lineas), 2, "encabezado y una deuda")
        self.assertIn("tramo_orden", lineas[0])
        self.assertIn("estado_en_gestion", lineas[0])
        self.assertEqual(len(lineas[0].split(",")), len(lineas[1].split(",")))
