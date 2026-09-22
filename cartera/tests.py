"""
Pruebas de la cartera recibida.

Lo que se recibe y como se valida se prueba en integracion/tests.py, que es
donde vive esa logica. Aca queda lo del modelo: que el DDL y los modelos digan
lo mismo, y que las restricciones que si viajan en la migracion funcionen.

A diferencia de crm y assistant, los CHECK de estas tablas estan declarados en
los modelos (models.CheckConstraint), asi que la base de pruebas SI los tiene y
se pueden ejercitar de verdad contra el motor.
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from crm.esquema import valores_del_check
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
        "ck_batch_source": Batch.Source,
        "ck_batch_status": Batch.Status,
        "ck_debtor_kind": Debtor.Kind,
        "ck_debt_status": Debt.Status,
    }

    def test_cada_check_ofrece_los_mismos_valores_que_su_modelo(self):
        for nombre, opciones in self.EQUIVALENCIAS.items():
            with self.subTest(check=nombre):
                en_el_ddl = valores_del_check(nombre)
                self.assertIsNotNone(en_el_ddl, f"El DDL no tiene el CHECK {nombre}.")
                self.assertEqual(
                    en_el_ddl, set(opciones.values),
                    f"\n{nombre} y {opciones.__qualname__} no dicen lo mismo."
                    f"\n  solo en el DDL:    {sorted(en_el_ddl - set(opciones.values))}"
                    f"\n  solo en el modelo: {sorted(set(opciones.values) - en_el_ddl)}",
                )

    def test_la_moneda_del_ddl_es_la_que_acepta_el_contrato(self):
        self.assertEqual(valores_del_check("ck_debt_currency"), {"CLP", "UF"})


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
        deudor = Debtor.objects.create(
            tax_id="16482337-7", full_name="Felipe Rojas", email="f@correo.cl"
        )
        deuda = Debt.objects.create(
            creditor=self.acreedor, debtor=deudor, external_id="CTR-1",
            concept="Arriendo", first_batch=self.lote, last_batch=self.lote,
        )
        deuda.status = "inventado"
        with self.assertRaises(IntegrityError), transaction.atomic():
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
        del_panel = valores_del_check("ck_handover_bracket")
        self.assertEqual(
            {Debt.tramo(15), Debt.tramo(60), Debt.tramo(100)}, del_panel,
            "Los tramos de la cartera y los de crm_portfoliohandover se separaron.",
        )
