"""
Pruebas de la recepcion de cartera.

La prueba que importa es la primera: APOFYX tiene que aceptar, sin tocarlo, el
archivo que Patrimonio Inmuebles genera. Si esa pasa, los dos sistemas hablan
el mismo idioma; si falla, da lo mismo que todo lo demas este bien.

El archivo vive en fixtures/ como copia del ejemplo publicado del contrato
(TB_web/docs/integracion/ejemplos/). La copia es a proposito: este repositorio
tiene que poder probarse solo. `LaCopiaDelContratoEstaAlDia` avisa si el
original cambio, cuando el otro repositorio esta al lado.
"""

import copy
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings as ajustes
from django.test import TestCase
from django.urls import reverse

from cartera.models import Batch, Debt, DebtCharge, Debtor
from crm.models import Campaign, CampaignFunnelSnapshot, Creditor

from .intake import CarteraInvalida, recibir_cartera
from .models import ApiKey

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cartera-v1-patrimonio.json"
RUT_PATRIMONIO = "76418902-7"


def cartera_de_ejemplo():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def crear_acreedor(tax_id=RUT_PATRIMONIO, nombre="Patrimonio Inmuebles"):
    return Creditor.objects.create(
        legal_name=f"{nombre} SpA", trade_name=nombre, tax_id=tax_id,
        status=Creditor.Status.ACTIVE,
    )


def lote_de_agosto():
    """
    La entrega del mes anterior.

    Existe para que el retiro de septiembre tenga contra que compararse: solo
    se puede retirar una deuda que antes se entrego.
    """
    return {
        "version": "1.0",
        "lote": {
            "id_externo": "PAT-2026-08-18-01",
            "fecha_corte": "2026-08-18",
            "acreedor": {"rut": RUT_PATRIMONIO},
        },
        "deudas": [{
            "id_externo": "CTR-2025-022",
            "deudor": {
                "rut": "15227640-0", "tipo": "persona", "nombre": "Tomás Fuentes Leiva",
                "correo": "tomas.fuentes@correo.cl", "telefono": "+56955512340",
            },
            "moneda": "CLP",
            "concepto": "Arriendo mensual",
            "cargos": [
                {"concepto": "Arriendo julio", "periodo": "2026-07",
                 "monto": 680000, "fecha_vencimiento": "2026-07-05"},
                {"concepto": "Arriendo agosto", "periodo": "2026-08",
                 "monto": 680000, "fecha_vencimiento": "2026-08-05"},
            ],
        }],
    }


class RecibeLaCarteraDePatrimonio(TestCase):
    """El caso completo, con el archivo real."""

    def setUp(self):
        self.acreedor = crear_acreedor()

    def test_acepta_el_archivo_tal_como_lo_genera_patrimonio(self):
        recibir_cartera(self.acreedor, lote_de_agosto())
        respuesta = recibir_cartera(self.acreedor, cartera_de_ejemplo())

        self.assertEqual(respuesta["recibidas"], 4)
        self.assertEqual(respuesta["aceptadas"], 4, respuesta["resultados"])
        self.assertEqual(respuesta["rechazadas"], 0)
        self.assertEqual(respuesta["campos_ignorados"], [])

        por_id = {r["id_externo"]: r for r in respuesta["resultados"]}
        self.assertEqual(por_id["CTR-2025-014"]["resultado"], "registrada")
        self.assertEqual(por_id["CTR-2025-022"]["resultado"], "retirada")

    def test_calcula_la_mora_y_el_tramo_de_cada_deuda(self):
        """
        Los tramos son los que APOFYX usa para priorizar: 1-30, 31-90 y 91-120.
        """
        respuesta = recibir_cartera(self.acreedor, cartera_de_ejemplo())
        por_id = {r["id_externo"]: r for r in respuesta["resultados"]}

        self.assertEqual(por_id["CTR-2025-014"]["mora_dias"], 44)
        self.assertEqual(por_id["CTR-2025-014"]["tramo"], "31-90")
        self.assertEqual(por_id["CTR-2026-031"]["mora_dias"], 13)
        self.assertEqual(por_id["CTR-2026-031"]["tramo"], "1-30")
        self.assertEqual(por_id["CTR-2024-007"]["mora_dias"], 75)

    def test_guarda_deudores_deudas_y_cargos(self):
        recibir_cartera(self.acreedor, cartera_de_ejemplo())

        self.assertEqual(Debtor.objects.count(), 3)
        self.assertEqual(Debt.objects.count(), 3)
        self.assertEqual(DebtCharge.objects.count(), 6)

        deuda = Debt.objects.get(external_id="CTR-2025-014")
        self.assertEqual(deuda.saldo, Decimal("1040000.00"))
        self.assertEqual(deuda.charges.count(), 2)
        self.assertEqual(deuda.debtor.tax_id, "16482337-7")
        self.assertEqual(deuda.refs["propiedad"], "Depto 1204, Av. Irarrázaval 2450, Ñuñoa")
        self.assertEqual(deuda.dias_mora(date(2026, 9, 18)), 44)

    def test_la_empresa_sin_telefono_queda_con_un_solo_canal(self):
        """
        El doble canal del codigo de acceso necesita correo Y telefono. Con uno
        solo se puede cobrar igual, pero conviene saber cuales son.
        """
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        empresa = Debtor.objects.get(tax_id="76991245-2")

        self.assertEqual(empresa.kind, Debtor.Kind.COMPANY)
        self.assertEqual([c[0] for c in empresa.canales], ["correo"])
        self.assertEqual(len(Debtor.objects.get(tax_id="16482337-7").canales), 2)


class ReenviarNoDuplica(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()

    def test_el_mismo_lote_dos_veces_devuelve_la_misma_respuesta(self):
        primera = recibir_cartera(self.acreedor, cartera_de_ejemplo())
        segunda = recibir_cartera(self.acreedor, cartera_de_ejemplo())

        self.assertFalse(primera["repetido"])
        self.assertTrue(segunda["repetido"])
        self.assertEqual(primera["resultados"], segunda["resultados"])
        self.assertEqual(Batch.objects.count(), 1)
        self.assertEqual(Debt.objects.count(), 3)

    def test_el_mismo_id_con_otro_contenido_se_rechaza(self):
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        distinta = cartera_de_ejemplo()
        distinta["deudas"][0]["cargos"][0]["monto"] = 999000

        with self.assertRaises(CarteraInvalida) as fallo:
            recibir_cartera(self.acreedor, distinta)
        self.assertEqual(fallo.exception.codigo, "lote_id_reutilizado")
        self.assertEqual(fallo.exception.status, 409)

    def test_la_misma_deuda_en_otro_lote_sin_cambios_no_toca_nada(self):
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        otra_vez = cartera_de_ejemplo()
        otra_vez["lote"]["id_externo"] = "PAT-2026-09-18-02"
        otra_vez["deudas"] = [otra_vez["deudas"][0]]

        respuesta = recibir_cartera(self.acreedor, otra_vez)
        self.assertEqual(respuesta["resultados"][0]["resultado"], "sin_cambios")

    def test_una_deuda_con_menos_saldo_se_actualiza_y_reemplaza_sus_cargos(self):
        """
        El arrendatario pago un mes en la oficina: el acreedor reenvia la deuda
        con menos cargos. Conservar los viejos dejaria a APOFYX cobrando un
        monto que ya no existe.
        """
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        actualizada = cartera_de_ejemplo()
        actualizada["lote"]["id_externo"] = "PAT-2026-09-25-01"
        primera = copy.deepcopy(actualizada["deudas"][0])
        primera["cargos"] = primera["cargos"][1:]
        actualizada["deudas"] = [primera]

        respuesta = recibir_cartera(self.acreedor, actualizada)
        deuda = Debt.objects.get(external_id="CTR-2025-014")

        self.assertEqual(respuesta["resultados"][0]["resultado"], "actualizada")
        self.assertEqual(deuda.charges.count(), 1)
        self.assertEqual(deuda.saldo, Decimal("520000.00"))


class RechazaLoQueNoCorresponde(TestCase):
    """Aceptacion parcial: lo malo se cae solo y lo bueno entra igual."""

    def setUp(self):
        self.acreedor = crear_acreedor()

    def _una_deuda(self, cambios):
        payload = cartera_de_ejemplo()
        payload["deudas"] = [copy.deepcopy(payload["deudas"][0])]
        cambios(payload["deudas"][0])
        return recibir_cartera(self.acreedor, payload)["resultados"][0]

    def codigos(self, resultado):
        return [e["codigo"] for e in resultado.get("errores", [])]

    def test_rut_con_digito_verificador_falso(self):
        r = self._una_deuda(lambda d: d["deudor"].update(rut="16482337-8"))
        self.assertIn("rut_invalido", self.codigos(r))

    def test_deudor_sin_correo_ni_telefono(self):
        def sin_contacto(d):
            d["deudor"].pop("correo")
            d["deudor"].pop("telefono")
        self.assertIn("sin_canal_contacto", self.codigos(self._una_deuda(sin_contacto)))

    def test_cargo_que_todavia_no_vence(self):
        r = self._una_deuda(lambda d: d["cargos"][0].update(fecha_vencimiento="2026-09-30"))
        self.assertIn("cargo_no_vencido", self.codigos(r))

    def test_mora_mayor_a_120_dias_vuelve_al_acreedor(self):
        r = self._una_deuda(lambda d: d["cargos"][0].update(fecha_vencimiento="2026-01-05"))
        self.assertIn("mora_fuera_de_mandato", self.codigos(r))

    def test_pesos_con_decimales(self):
        r = self._una_deuda(lambda d: d["cargos"][0].update(monto=520000.5))
        self.assertIn("monto_invalido", self.codigos(r))

    def test_uf_con_mas_de_dos_decimales(self):
        def uf_larga(d):
            d["moneda"] = "UF"
            d["cargos"][0]["monto"] = 38.555
        self.assertIn("monto_invalido", self.codigos(self._una_deuda(uf_larga)))

    def test_retirar_una_deuda_que_no_existe(self):
        payload = cartera_de_ejemplo()
        payload["deudas"] = [{"id_externo": "CTR-9999", "accion": "retirar",
                              "motivo_retiro": "pago_directo"}]
        r = recibir_cartera(self.acreedor, payload)["resultados"][0]
        self.assertIn("deuda_no_encontrada", self.codigos(r))

    def test_dos_deudas_con_el_mismo_id_en_el_lote(self):
        payload = cartera_de_ejemplo()
        payload["deudas"] = [payload["deudas"][0], copy.deepcopy(payload["deudas"][0])]
        respuesta = recibir_cartera(self.acreedor, payload)

        self.assertEqual(respuesta["aceptadas"], 1)
        self.assertIn("id_duplicado_en_lote", self.codigos(respuesta["resultados"][1]))

    def test_una_deuda_mala_no_arrastra_a_las_demas(self):
        payload = cartera_de_ejemplo()
        payload["deudas"][1]["deudor"]["rut"] = "11111111-2"

        respuesta = recibir_cartera(self.acreedor, payload)
        self.assertEqual(respuesta["aceptadas"], 3)   # Felipe, Nandu y Tomas, que esta al dia
        self.assertEqual(respuesta["rechazadas"], 1)  # el RUT malo
        self.assertTrue(Debt.objects.filter(external_id="CTR-2025-014").exists())

    def test_la_cartera_dice_ser_de_otro_acreedor(self):
        otro = cartera_de_ejemplo()
        otro["lote"]["acreedor"]["rut"] = "77305118-6"

        with self.assertRaises(CarteraInvalida) as fallo:
            recibir_cartera(self.acreedor, otro)
        self.assertEqual(fallo.exception.codigo, "acreedor_no_coincide")
        self.assertEqual(fallo.exception.status, 403)

    def test_una_version_que_no_se_conoce(self):
        futura = cartera_de_ejemplo()
        futura["version"] = "2.0"
        with self.assertRaises(CarteraInvalida) as fallo:
            recibir_cartera(self.acreedor, futura)
        self.assertEqual(fallo.exception.codigo, "version_no_soportada")

    def test_avisa_de_los_campos_que_no_conoce(self):
        """Se reciben igual: el receptor es tolerante, pero lo dice."""
        payload = cartera_de_ejemplo()
        payload["deudas"][0]["color_favorito"] = "azul"
        respuesta = recibir_cartera(self.acreedor, payload)

        self.assertIn("deudas[].color_favorito", respuesta["campos_ignorados"])
        self.assertEqual(respuesta["aceptadas"], 4)


class UnDeudorEsElMismoEnTodosLosAcreedores(TestCase):

    def test_el_rut_no_se_duplica_entre_acreedores(self):
        """
        Si el mismo RUT apareciera dos veces, APOFYX no podria saber cuantas
        veces le esta escribiendo a la misma persona.
        """
        patrimonio = crear_acreedor()
        gimnasio = crear_acreedor("76543210-3", "Vitalis Gym")

        recibir_cartera(patrimonio, cartera_de_ejemplo())
        del_gimnasio = cartera_de_ejemplo()
        del_gimnasio["lote"]["acreedor"]["rut"] = "76543210-3"
        del_gimnasio["lote"]["id_externo"] = "VIT-2026-09-01"
        del_gimnasio["deudas"] = [copy.deepcopy(del_gimnasio["deudas"][0])]
        del_gimnasio["deudas"][0]["id_externo"] = "SOCIO-4410"
        recibir_cartera(gimnasio, del_gimnasio)

        deudor = Debtor.objects.get(tax_id="16482337-7")
        self.assertEqual(Debtor.objects.count(), 3)
        self.assertEqual(deudor.debts.count(), 2)
        self.assertEqual(
            sorted(d.creditor.trade_name for d in deudor.debts.all()),
            ["Patrimonio Inmuebles", "Vitalis Gym"],
        )


class ElEndpointPideCredencial(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()
        self.clave, self.registro = ApiKey.emitir(self.acreedor, "Patrimonio")
        self.url = reverse("integracion:carteras")

    def _enviar(self, payload, clave=None):
        return self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json",
            headers={"authorization": f"Bearer {clave if clave is not None else self.clave}"},
        )

    def test_con_la_clave_correcta_recibe_la_cartera(self):
        r = self._enviar(cartera_de_ejemplo())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["aceptadas"], 4)

    def test_sin_clave_no_entra(self):
        r = self.client.post(self.url, data=json.dumps(cartera_de_ejemplo()),
                             content_type="application/json")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"]["codigo"], "no_autorizado")

    def test_con_una_clave_inventada_tampoco(self):
        self.assertEqual(self._enviar(cartera_de_ejemplo(), "apx_cualquier_cosa").status_code, 401)

    def test_una_clave_revocada_deja_de_servir(self):
        from django.utils import timezone
        ApiKey.objects.filter(pk=self.registro.pk).update(revoked_at=timezone.now())
        self.assertEqual(self._enviar(cartera_de_ejemplo()).status_code, 401)

    def test_la_clave_no_se_guarda_en_la_base(self):
        """Se guarda su huella. Si se pierde, se emite otra; no se recuerda."""
        self.assertNotIn(self.clave, json.dumps(list(
            ApiKey.objects.values("key_hash", "prefix", "name")
        )))
        self.assertEqual(self.registro.key_hash, ApiKey.huella(self.clave))

    def test_el_cuerpo_que_no_es_json(self):
        r = self.client.post(self.url, data="{roto", content_type="application/json",
                             headers={"authorization": f"Bearer {self.clave}"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["codigo"], "json_invalido")

    def test_la_clave_registra_su_ultimo_uso(self):
        self._enviar(cartera_de_ejemplo())
        self.registro.refresh_from_db()
        self.assertIsNotNone(self.registro.last_used_at)


class LaCopiaDelContratoEstaAlDia(TestCase):
    """
    El fixture es una copia del ejemplo publicado del contrato. Si el otro
    repositorio esta al lado, se revisa que no se hayan separado.
    """

    def test_el_fixture_calza_con_el_ejemplo_publicado(self):
        publicado = (
            Path(ajustes.BASE_DIR).parent / "TB_web" / "docs" / "integracion"
            / "ejemplos" / "cartera-v1.patrimonio.json"
        )
        if not publicado.exists():
            self.skipTest("El repositorio de DataBridge no esta al lado")
        self.assertEqual(
            json.loads(publicado.read_text(encoding="utf-8")),
            cartera_de_ejemplo(),
            "El ejemplo del contrato cambio: hay que actualizar el fixture.",
        )


# ==========================================================================
#  El reenvio a DataBridge
# ==========================================================================

from datetime import date as _date  # noqa: E402

from django.test import override_settings  # noqa: E402

from crm.esquema import valores_del_enum  # noqa: E402

from .models import Forward  # noqa: E402
from .reenvio import (  # noqa: E402
    ErrorDataBridge, canales_para_databridge, construir_cartera, despachar,
    encolar, id_de_campana,
)

DATABRIDGE_PRUEBA = {
    "URL": "http://databridge.prueba", "CLAVE": "tbk_prueba",
    "RUT_AGENCIA": "77305118-6", "MORA_MAXIMA_DIAS": 120, "TIMEOUT_S": 2,
    "REENVIO_INMEDIATO": False, "SECRETO_EVENTOS": "",
}


class ClienteFalso:
    """Hace de DataBridge: anota lo que recibe y responde como el de verdad."""

    def __init__(self, caido=False):
        self.caido = caido
        self.llamadas = []

    def enviar(self, ruta, cuerpo):
        if self.caido:
            raise ErrorDataBridge("Sin respuesta de DataBridge: conexion rechazada")
        self.llamadas.append((ruta, cuerpo))
        if ruta == "/api/v1/carteras":
            return {"lote": cuerpo["lote"]["id_externo"], "repetido": False,
                    "recibidas": len(cuerpo["deudas"]), "aceptadas": len(cuerpo["deudas"]),
                    "rechazadas": 0, "resultados": []}
        return {"ok": True}


def campana_de(acreedor):
    return Campaign.objects.create(
        creditor=acreedor, name="Patrimonio - Arriendos - Septiembre 2026",
        starts_on=_date(2026, 9, 19), status=Campaign.Status.RUNNING,
        channels=["whatsapp", "email", "sms"], contact_attempts=5,
    )


@override_settings(DATABRIDGE=DATABRIDGE_PRUEBA)
class LaCarteraQueSaleEsLaQueEntro(TestCase):
    """
    APOFYX no cambia montos ni cargos: lo que le pasa a DataBridge es
    exactamente lo que el acreedor le entrego y APOFYX acepto.
    """

    def setUp(self):
        self.acreedor = crear_acreedor()
        self.campana = campana_de(self.acreedor)
        recibir_cartera(self.acreedor, lote_de_agosto())
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        self.forward = Forward.objects.get(batch__external_id="PAT-2026-09-18-01")
        self.cartera = construir_cartera(self.forward, self.campana)

    def test_las_deudas_salen_identicas_a_como_entraron(self):
        """Las que deben salen tal cual; Tomas, al dia, sale como el retiro de su deuda de agosto."""
        entraron = [d for d in cartera_de_ejemplo()["deudas"] if d["cargos"]]
        salen = [d for d in self.cartera["deudas"] if d.get("accion") != "retirar"]
        self.assertEqual(salen, entraron)
        self.assertIn({"id_externo": "CTR-2025-022", "accion": "retirar", "motivo_retiro": "pago_directo"},
                      self.cartera["deudas"])

    def test_el_acreedor_sigue_siendo_patrimonio(self):
        self.assertEqual(self.cartera["lote"]["acreedor"]["rut"], RUT_PATRIMONIO)

    def test_apofyx_agrega_su_mandato_y_su_propio_numero_de_lote(self):
        lote = self.cartera["lote"]
        self.assertEqual(lote["mandato"]["agencia_rut"], "77305118-6")
        self.assertEqual(lote["mandato"]["campana_id_externo"], id_de_campana(self.campana))
        self.assertNotEqual(lote["id_externo"], "PAT-2026-09-18-01")
        self.assertTrue(lote["id_externo"].startswith("APX-2026-09-18-"))

    def test_los_pesos_viajan_enteros_y_la_uf_con_decimales(self):
        por_id = {d["id_externo"]: d for d in self.cartera["deudas"]}
        self.assertIsInstance(por_id["CTR-2025-014"]["cargos"][0]["monto"], int)
        self.assertEqual(por_id["CTR-2024-007"]["cargos"][0]["monto"], 38.5)


@override_settings(DATABRIDGE=DATABRIDGE_PRUEBA)
class LaBandejaDeSalida(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()

    def test_una_entrega_aceptada_queda_en_la_bandeja(self):
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        self.assertEqual(Forward.objects.count(), 1)
        self.assertEqual(Forward.objects.get().status, Forward.Status.PENDING)

    def test_una_entrega_totalmente_rechazada_no_se_reenvia(self):
        mala = cartera_de_ejemplo()
        mala["deudas"] = [{"id_externo": "CTR-9999", "accion": "retirar",
                           "motivo_retiro": "pago_directo"}]
        recibir_cartera(self.acreedor, mala)
        self.assertEqual(Forward.objects.count(), 0)

    @override_settings(DATABRIDGE={**DATABRIDGE_PRUEBA, "URL": "", "CLAVE": ""})
    def test_sin_configuracion_apofyx_trabaja_solo(self):
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        self.assertEqual(Forward.objects.count(), 0)

    def test_con_databridge_arriba_se_entrega(self):
        campana_de(self.acreedor)
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        cliente = ClienteFalso()

        forward = despachar(Forward.objects.get().pk, cliente)

        self.assertEqual(forward.status, Forward.Status.SENT)
        self.assertEqual([ruta for ruta, _ in cliente.llamadas],
                         ["/api/v1/mandatos", "/api/v1/campanas", "/api/v1/carteras"])

    def test_si_databridge_esta_caido_queda_para_reintentar(self):
        campana_de(self.acreedor)
        recibir_cartera(self.acreedor, cartera_de_ejemplo())

        with self.assertLogs("integracion.reenvio", "WARNING"):
            forward = despachar(Forward.objects.get().pk, ClienteFalso(caido=True))

        self.assertEqual(forward.status, Forward.Status.PENDING)
        self.assertEqual(forward.attempts, 1)
        self.assertIn("Sin respuesta", forward.last_error)
        self.assertGreater(forward.next_attempt_at, forward.created_at)

    def test_despues_del_ultimo_intento_queda_fallida(self):
        campana_de(self.acreedor)
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        pk = Forward.objects.get().pk
        with self.assertLogs("integracion.reenvio", "WARNING"):
            for _ in range(len(Forward.ESPERAS)):
                despachar(pk, ClienteFalso(caido=True))
        self.assertEqual(Forward.objects.get(pk=pk).status, Forward.Status.FAILED)

    def test_sin_campana_no_se_adivina_espera(self):
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        forward = despachar(Forward.objects.get().pk, ClienteFalso())
        self.assertEqual(forward.status, Forward.Status.WAITING_CAMPAIGN)

    def test_con_dos_campanas_en_curso_tampoco_se_adivina(self):
        campana_de(self.acreedor)
        Campaign.objects.create(
            creditor=self.acreedor, name="Otra campana", starts_on=_date(2026, 9, 1),
            status=Campaign.Status.RUNNING, channels=["email"],
        )
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        forward = despachar(Forward.objects.get().pk, ClienteFalso())
        self.assertEqual(forward.status, Forward.Status.WAITING_CAMPAIGN)

    @override_settings(DATABRIDGE={**DATABRIDGE_PRUEBA, "URL": "http://127.0.0.1:9",
                                   "REENVIO_INMEDIATO": True})
    def test_la_recepcion_no_falla_aunque_databridge_este_caido(self):
        """
        El cliente de APOFYX tiene que recibir su respuesta aunque DataBridge
        no conteste: el problema no es suyo.
        """
        campana_de(self.acreedor)
        with self.assertLogs("integracion.reenvio", "WARNING"),                 self.captureOnCommitCallbacks(execute=True):
            respuesta = recibir_cartera(self.acreedor, cartera_de_ejemplo())

        self.assertEqual(respuesta["aceptadas"], 4)
        forward = Forward.objects.get()
        self.assertEqual(forward.status, Forward.Status.PENDING)
        self.assertEqual(forward.attempts, 1)


class ElVocabularioSeTraduceEnElBorde(TestCase):

    def test_email_pasa_a_correo_y_el_sms_se_cae(self):
        self.assertEqual(canales_para_databridge(["whatsapp", "email", "sms"]),
                         ["whatsapp", "correo"])

    def test_el_check_de_la_bandeja_calza_con_el_modelo(self):
        self.assertEqual(valores_del_enum("integracion_forward", "status"),
                         set(Forward.Status.values))


@override_settings(DATABRIDGE=DATABRIDGE_PRUEBA)
class LaCampanaSeAsignaDesdeElAdmin(TestCase):
    """Cuando el reenvio queda esperando campana, alguien la asigna a mano."""

    def test_solo_ofrece_campanas_del_mismo_acreedor(self):
        from django.contrib.auth import get_user_model

        acreedor = crear_acreedor()
        otro = crear_acreedor("77812341-K", "Otro Acreedor")
        propia = campana_de(acreedor)
        Campaign.objects.create(creditor=otro, name="Campana ajena", starts_on=_date(2026, 9, 1),
                                status=Campaign.Status.RUNNING, channels=["email"])
        recibir_cartera(acreedor, cartera_de_ejemplo())
        entrega = Batch.objects.get()

        self.client.force_login(get_user_model().objects.create_superuser(
            "supervisora", "supervisora@apofyx.cl", "clave-de-prueba"))
        pagina = self.client.get(reverse("admin:cartera_batch_change", args=[entrega.pk]))

        ofrecidas = pagina.context["adminform"].form.fields["campaign"].queryset
        self.assertEqual(list(ofrecidas), [propia])


# ==========================================================================
#  Los eventos de vuelta: DataBridge -> APOFYX -> el cliente
# ==========================================================================

import threading  # noqa: E402
import time as _time  # noqa: E402
from http.server import BaseHTTPRequestHandler, HTTPServer  # noqa: E402

from .eventos import despachar_evento, firma_valida, firmar, recibir_evento  # noqa: E402
from .models import InboundEvent, OutboundEvent, Subscription  # noqa: E402

SECRETO_DATABRIDGE = "whsec_de_databridge"
CON_EVENTOS = {**DATABRIDGE_PRUEBA, "SECRETO_EVENTOS": SECRETO_DATABRIDGE}


def evento_de_databridge(tipo, deuda="CTR-2025-014", **datos):
    """Un evento como lo arma ms-debt, con el lote de APOFYX."""
    return {
        "id": f"evt_{tipo}_{deuda}_{len(datos)}",
        "tipo": tipo,
        "version": "1",
        "ocurrido_en": "2026-09-20T14:03:11-03:00",
        "acreedor_rut": RUT_PATRIMONIO,
        "lote_id_externo": "APX-2026-09-18-0001",
        "datos": {"deuda_id_externo": deuda, **datos},
    }


PAGO = {"pago_id": "41", "monto": 520000, "moneda": "CLP", "monto_clp": 520000,
        "medio": "webpay", "pagado_en": "2026-09-20T14:03:11-03:00"}


class LaFirmaDelContrato(TestCase):

    def test_firma_igual_que_node_y_que_java(self):
        """
        La misma referencia que usa la prueba de ms-debt: los tres sistemas
        tienen que firmar byte a byte igual, o todo evento llega rechazado.
        """
        cuerpo = b'{"id":"evt_1","tipo":"pago.confirmado"}'
        self.assertEqual(
            firmar("whsec_prueba", 1789923791, cuerpo),
            "v1=344ce2850a1c9cb0b60434906199eb2d716de503c6191265746204fcaa31d3f6",
        )

    def test_rechaza_un_cuerpo_alterado(self):
        marca = int(_time.time())
        firma = firmar("s", marca, b'{"monto": 1000}')
        self.assertTrue(firma_valida("s", str(marca), firma, b'{"monto": 1000}'))
        self.assertFalse(firma_valida("s", str(marca), firma, b'{"monto": 9000}'))

    def test_rechaza_otro_secreto(self):
        marca = int(_time.time())
        self.assertFalse(firma_valida("s", marca, firmar("otro", marca, b"{}"), b"{}"))

    def test_rechaza_un_evento_de_hace_mas_de_cinco_minutos(self):
        """Un evento interceptado no se puede volver a mandar mas tarde."""
        vieja = int(_time.time()) - 6 * 60
        self.assertFalse(firma_valida("s", vieja, firmar("s", vieja, b"{}"), b"{}"))


@override_settings(DATABRIDGE=CON_EVENTOS)
class LosEventosPonenAlDiaLaCartera(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()
        recibir_cartera(self.acreedor, lote_de_agosto())
        recibir_cartera(self.acreedor, cartera_de_ejemplo())

    def deuda(self, id_externo="CTR-2025-014"):
        return Debt.objects.get(external_id=id_externo)

    def test_un_pago_se_anota_pero_no_cambia_el_estado(self):
        """El saldo vive en DataBridge; APOFYX solo cambia de estado al saldarse."""
        respuesta = recibir_evento(evento_de_databridge("pago.confirmado", **PAGO))
        self.assertEqual(respuesta["resultado"], "pago anotado")
        self.assertEqual(self.deuda().status, Debt.Status.OPEN)
        self.assertEqual(InboundEvent.objects.get().debt, self.deuda())

    def test_la_deuda_saldada_deja_de_estar_en_gestion(self):
        recibir_evento(evento_de_databridge("deuda.saldada", saldada_en="2026-09-20T14:03:11-03:00"))
        self.assertEqual(self.deuda().status, Debt.Status.PAID)

    def test_una_repactacion_pasa_a_convenio(self):
        recibir_evento(evento_de_databridge("repactacion.aceptada", cuotas=6,
                                            monto_cuota=173334, moneda="CLP",
                                            primera_cuota="2026-10-20"))
        self.assertEqual(self.deuda().status, Debt.Status.REPACTED)

    def test_el_convenio_sobrevive_a_la_cartera_del_mes_siguiente(self):
        """
        Patrimonio vuelve a mandar la deuda en su cartera mensual. Eso no es una
        decision sobre el deudor: el convenio sigue.
        """
        recibir_evento(evento_de_databridge("repactacion.aceptada", cuotas=6))
        otra = cartera_de_ejemplo()
        otra["lote"]["id_externo"] = "PAT-2026-10-18-01"
        otra["deudas"] = [otra["deudas"][0]]

        respuesta = recibir_cartera(self.acreedor, otra)

        self.assertEqual(respuesta["resultados"][0]["resultado"], "sin_cambios")
        self.assertEqual(self.deuda().status, Debt.Status.REPACTED)

    def test_un_aviso_atrasado_no_reabre_una_deuda_pagada(self):
        """Los eventos no llegan en orden garantizado (contrato 8.1)."""
        recibir_evento(evento_de_databridge("deuda.saldada"))
        respuesta = recibir_evento(evento_de_databridge("repactacion.aceptada", cuotas=3))
        self.assertEqual(respuesta["resultado"], "se mantiene pagada")
        self.assertEqual(self.deuda().status, Debt.Status.PAID)

    def test_el_mismo_evento_dos_veces_se_procesa_una(self):
        evento = evento_de_databridge("deuda.saldada")
        recibir_evento(evento)
        segunda = recibir_evento(evento)
        self.assertTrue(segunda["repetido"])
        self.assertEqual(InboundEvent.objects.count(), 1)

    def test_una_deuda_que_apofyx_no_conoce_se_guarda_y_no_se_reenvia(self):
        Subscription.registrar(self.acreedor, "http://patrimonio.prueba/api/eventos")
        respuesta = recibir_evento(evento_de_databridge("pago.confirmado", deuda="CTR-9999", **PAGO))
        self.assertEqual(respuesta["resultado"], "deuda desconocida")
        self.assertEqual(respuesta["avisados"], 0)
        self.assertEqual(InboundEvent.objects.count(), 1)


@override_settings(DATABRIDGE=CON_EVENTOS)
class APOFYXLeReportaAlCliente(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()
        recibir_cartera(self.acreedor, cartera_de_ejemplo())

    def test_sin_suscripcion_el_cliente_no_recibe_nada(self):
        respuesta = recibir_evento(evento_de_databridge("pago.confirmado", **PAGO))
        self.assertEqual(respuesta["avisados"], 0)
        self.assertEqual(OutboundEvent.objects.count(), 0)

    def test_el_evento_que_sale_lleva_el_lote_del_cliente_y_un_id_propio(self):
        Subscription.registrar(self.acreedor, "http://patrimonio.prueba/api/eventos")
        original = evento_de_databridge("pago.confirmado", **PAGO)

        recibir_evento(original)

        saliente = OutboundEvent.objects.get().payload
        self.assertEqual(saliente["lote_id_externo"], "PAT-2026-09-18-01")
        self.assertNotEqual(saliente["id"], original["id"])
        self.assertEqual(saliente["datos"], original["datos"])
        self.assertEqual(saliente["acreedor_rut"], RUT_PATRIMONIO)

    def test_el_cliente_elige_que_eventos_recibe(self):
        Subscription.registrar(self.acreedor, "http://patrimonio.prueba/api/eventos",
                               ["deuda.saldada"])
        recibir_evento(evento_de_databridge("pago.confirmado", **PAGO))
        recibir_evento(evento_de_databridge("deuda.saldada"))
        self.assertEqual(list(OutboundEvent.objects.values_list("type", flat=True)), ["deuda.saldada"])

    def test_registrar_la_misma_url_devuelve_el_mismo_secreto(self):
        primera = Subscription.registrar(self.acreedor, "http://patrimonio.prueba/api/eventos")
        segunda = Subscription.registrar(self.acreedor, "http://patrimonio.prueba/api/eventos")
        self.assertEqual(primera.secret, segunda.secret)
        self.assertEqual(Subscription.objects.count(), 1)

    def test_el_aviso_llega_firmado_y_el_cliente_puede_verificarlo(self):
        """Un servidor de verdad hace de Patrimonio y verifica la firma."""
        recibido = {}

        class Patrimonio(BaseHTTPRequestHandler):
            def do_POST(self):
                cuerpo = self.rfile.read(int(self.headers["Content-Length"]))
                recibido.update(cuerpo=cuerpo, marca=self.headers["X-Timestamp"],
                                firma=self.headers["X-Firma"], tipo=self.headers["X-Evento"])
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"repetido": false}')

            def log_message(self, *args):
                pass

        servidor = HTTPServer(("127.0.0.1", 0), Patrimonio)
        hilo = threading.Thread(target=servidor.handle_request, daemon=True)
        hilo.start()
        try:
            suscripcion = Subscription.registrar(
                self.acreedor, f"http://127.0.0.1:{servidor.server_port}/api/eventos")
            recibir_evento(evento_de_databridge("pago.confirmado", **PAGO))

            pendiente = despachar_evento(OutboundEvent.objects.get().pk)
        finally:
            hilo.join(timeout=5)
            servidor.server_close()

        self.assertEqual(pendiente.status, OutboundEvent.Status.DELIVERED)
        self.assertEqual(recibido["tipo"], "pago.confirmado")
        self.assertTrue(firma_valida(suscripcion.secret, recibido["marca"],
                                     recibido["firma"], recibido["cuerpo"]))

    def test_si_el_cliente_esta_caido_el_aviso_espera(self):
        Subscription.registrar(self.acreedor, "http://127.0.0.1:9/api/eventos")
        recibir_evento(evento_de_databridge("pago.confirmado", **PAGO))

        with self.assertLogs("integracion.eventos", "WARNING"):
            pendiente = despachar_evento(OutboundEvent.objects.get().pk)

        self.assertEqual(pendiente.status, OutboundEvent.Status.PENDING)
        self.assertEqual(pendiente.attempts, 1)


class ElEndpointDeEventos(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        self.url = reverse("integracion:eventos")

    def enviar(self, evento, secreto=SECRETO_DATABRIDGE, marca=None):
        cuerpo = json.dumps(evento).encode("utf-8")
        marca = int(_time.time()) if marca is None else marca
        return self.client.post(self.url, data=cuerpo, content_type="application/json",
                                HTTP_X_TIMESTAMP=str(marca),
                                HTTP_X_FIRMA=firmar(secreto, marca, cuerpo))

    @override_settings(DATABRIDGE=DATABRIDGE_PRUEBA)
    def test_sin_secreto_configurado_no_recibe(self):
        respuesta = self.enviar(evento_de_databridge("deuda.saldada"))
        self.assertEqual(respuesta.status_code, 503)

    @override_settings(DATABRIDGE=CON_EVENTOS)
    def test_con_otra_firma_responde_401_y_no_toca_nada(self):
        respuesta = self.enviar(evento_de_databridge("deuda.saldada"), secreto="whsec_falso")
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(Debt.objects.get(external_id="CTR-2025-014").status, Debt.Status.OPEN)

    @override_settings(DATABRIDGE=CON_EVENTOS)
    def test_un_evento_viejo_se_rechaza_aunque_la_firma_calce(self):
        vieja = int(_time.time()) - 600
        self.assertEqual(self.enviar(evento_de_databridge("deuda.saldada"), marca=vieja).status_code, 401)

    @override_settings(DATABRIDGE=CON_EVENTOS)
    def test_bien_firmado_pone_al_dia_la_deuda(self):
        respuesta = self.enviar(evento_de_databridge("deuda.saldada"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["resultado"], "en gestion -> pagada")
        self.assertEqual(Debt.objects.get(external_id="CTR-2025-014").status, Debt.Status.PAID)

    def test_el_check_de_la_bandeja_de_avisos_calza_con_el_modelo(self):
        self.assertEqual(valores_del_enum("integracion_outboundevent", "status"),
                         set(OutboundEvent.Status.values))

@override_settings(DATABRIDGE=CON_EVENTOS)
class ElAvanceDeLaCampanaLlenaElEmbudo(TestCase):
    """
    Lo que APOFYX no podia medir sola: hasta donde llega su embudo terminaba en
    el mensaje enviado, porque el pago ocurria fuera de su producto (docs 11.3).
    """

    def setUp(self):
        self.acreedor = crear_acreedor()
        self.campana = campana_de(self.acreedor)
        recibir_cartera(self.acreedor, cartera_de_ejemplo())

    def avance(self, **datos):
        return {
            "id": f"evt_avance_{len(datos)}",
            "tipo": "campana.avance",
            "version": "1",
            "ocurrido_en": "2026-09-22T08:00:00-03:00",
            "acreedor_rut": RUT_PATRIMONIO,
            "datos": {"campana_id_externo": f"APX-CMP-{self.campana.pk}",
                      "fecha_corte": "2026-09-22", **datos},
        }

    def test_guarda_los_pagos_y_lo_recuperado(self):
        respuesta = recibir_evento(self.avance(
            enviados=3, ingresos_portal=2, pagos=1, recuperado_clp=410000, recuperado_uf="19.25"))

        self.assertIn("embudo al 2026-09-22", respuesta["resultado"])
        foto = CampaignFunnelSnapshot.objects.get()
        self.assertEqual(foto.campaign, self.campana)
        self.assertEqual(str(foto.measured_on), "2026-09-22")
        self.assertEqual(foto.messages_sent, 3)
        self.assertEqual(foto.link_clicks, 2)          # ingresos al portal
        self.assertEqual(foto.payments, 1)
        self.assertEqual(foto.recovered_clp, 410000)
        self.assertEqual(str(foto.recovered_uf), "19.25")

    def test_los_pesos_y_las_uf_no_se_suman(self):
        recibir_evento(self.avance(pagos=2, recuperado_clp=410000, recuperado_uf="19.25"))
        foto = CampaignFunnelSnapshot.objects.get()
        self.assertEqual((foto.recovered_clp, str(foto.recovered_uf)), (410000, "19.25"))

    def test_lo_que_databridge_no_mide_no_queda_en_cero(self):
        """Un cero diria "ninguno"; lo que falta es "no lo se"."""
        CampaignFunnelSnapshot.objects.create(
            campaign=self.campana, measured_on=date(2026, 9, 22),
            messages_delivered=7, replies_received=2,
        )
        recibir_evento(self.avance(enviados=3, pagos=1))
        foto = CampaignFunnelSnapshot.objects.get()
        self.assertEqual((foto.messages_delivered, foto.replies_received), (7, 2))
        self.assertEqual(foto.messages_sent, 3)

    def test_el_mismo_dia_se_actualiza_en_vez_de_duplicarse(self):
        recibir_evento(self.avance(pagos=1))
        segundo = self.avance(pagos=2)
        segundo["id"] = "evt_avance_mas_tarde"
        recibir_evento(segundo)
        self.assertEqual(CampaignFunnelSnapshot.objects.count(), 1)
        self.assertEqual(CampaignFunnelSnapshot.objects.get().payments, 2)

    def test_una_campana_de_otro_acreedor_no_se_toca(self):
        otro = crear_acreedor("77812341-K", "Otro Acreedor")
        ajena = Campaign.objects.create(
            creditor=otro, name="Ajena", starts_on=_date(2026, 9, 1),
            status=Campaign.Status.RUNNING, channels=["email"])
        evento = self.avance(pagos=9)
        evento["datos"]["campana_id_externo"] = f"APX-CMP-{ajena.pk}"

        respuesta = recibir_evento(evento)

        self.assertEqual(respuesta["resultado"], "campana desconocida")
        self.assertEqual(CampaignFunnelSnapshot.objects.count(), 0)

    def test_el_avance_no_se_le_reenvia_al_cliente(self):
        """Es la campana de APOFYX, no del acreedor: a Patrimonio no le dice nada."""
        Subscription.registrar(self.acreedor, "http://patrimonio.prueba/api/eventos")
        respuesta = recibir_evento(self.avance(pagos=1))
        self.assertEqual(respuesta["avisados"], 0)
        self.assertEqual(OutboundEvent.objects.count(), 0)


@override_settings(DATABRIDGE=CON_EVENTOS)
class ElLoteProcesadoSeAnota(TestCase):

    def test_se_guarda_aunque_no_hable_de_una_deuda(self):
        acreedor = crear_acreedor()
        recibir_cartera(acreedor, cartera_de_ejemplo())
        respuesta = recibir_evento({
            "id": "evt_lote_1", "tipo": "lote.procesado", "version": "1",
            "ocurrido_en": "2026-09-22T08:00:00-03:00", "acreedor_rut": RUT_PATRIMONIO,
            "lote_id_externo": "APX-2026-09-18-0001",
            "datos": {"periodo": "2026-09", "recibidas": 4, "aceptadas": 3, "rechazadas": 1,
                      "tramos": [{"tramo": "31-90", "deudas": 2, "promedio_clp": 520000}]},
        })
        self.assertEqual(respuesta["resultado"], "anotado")
        self.assertEqual(InboundEvent.objects.get().type, "lote.procesado")


# ==========================================================================
#  La historia de la demo (manage.py cargar_demo)
# ==========================================================================

from io import StringIO  # noqa: E402

from django.core.management import call_command  # noqa: E402
from django.core.management.base import CommandError  # noqa: E402
from django.utils.timezone import localtime  # noqa: E402

from .intake import huella  # noqa: E402


def cargar_demo(**opciones):
    salida = StringIO()
    call_command("cargar_demo", stdout=salida, **opciones)
    return salida.getvalue()


#  Con DataBridge configurado y Patrimonio suscrito: si la demo reenviara algo,
#  aca se notaria.
@override_settings(DATABRIDGE=CON_EVENTOS)
class LaDemoCuentaLaMismaHistoriaQueDataBridge(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()
        Subscription.registrar(self.acreedor, "http://patrimonio.prueba/api/eventos")
        cargar_demo()

    def deuda(self, id_externo):
        return Debt.objects.get(creditor=self.acreedor, external_id=id_externo)

    def test_cada_deudor_queda_en_su_situacion(self):
        self.assertEqual(dict(Debt.objects.values_list("external_id", "status")), {
            "CTR-2025-014": Debt.Status.REPACTED,    # Felipe: 3 de 6 cuotas pagadas
            "CTR-2026-031": Debt.Status.OPEN,        # Valentina: DataBridge no la tomo
            "CTR-2024-007": Debt.Status.OPEN,        # Comercial Nandu
            "CTR-2025-022": Debt.Status.WITHDRAWN,   # Tomas pago en la oficina
            "CTR-2025-019": Debt.Status.OPEN,        # Rodrigo
            "CTR-2026-012": Debt.Status.PAID,        # Carolina
            "CTR-2024-019": Debt.Status.REPACTED,    # La Espiga
            "CTR-2025-027": Debt.Status.REPACTED,    # Ignacio, el convenio en riesgo
            "CTR-2026-015": Debt.Status.PAID,        # Daniela
        })

    def test_la_cartera_es_la_que_mando_patrimonio(self):
        rodrigo = self.deuda("CTR-2025-019")
        self.assertEqual((rodrigo.charges.count(), rodrigo.saldo), (4, Decimal("1800000")))
        self.assertEqual(self.deuda("CTR-2024-019").saldo, Decimal("72"))
        self.assertEqual(self.deuda("CTR-2025-022").withdrawn_reason, "pago_directo")
        #  El contrato de Ignacio termino en agosto: no volvio en septiembre.
        self.assertEqual(self.deuda("CTR-2025-027").last_batch.external_id, "PAT-2026-08-18-01")
        self.assertEqual(self.deuda("CTR-2026-031").first_batch.external_id, "PAT-2026-09-18-01")

    def test_las_dos_carteras_se_le_pasaron_a_databridge(self):
        reenvios = {f.batch.external_id: f for f in Forward.objects.select_related("batch__campaign")}
        agosto, septiembre = reenvios["PAT-2026-08-18-01"], reenvios["PAT-2026-09-18-01"]
        self.assertEqual({agosto.status, septiembre.status}, {Forward.Status.SENT})
        self.assertEqual((agosto.external_id, septiembre.external_id), ("APX-2026-08-19-003", "APX-2026-09-19-004"))
        self.assertEqual((agosto.response["aceptadas"], agosto.response["rechazadas"]), (6, 2))
        self.assertEqual((septiembre.response["aceptadas"], septiembre.response["rechazadas"]), (7, 1))
        self.assertEqual(agosto.batch.campaign.status, Campaign.Status.FINISHED)
        self.assertEqual(septiembre.batch.campaign.name, "Patrimonio - Arriendos - Septiembre 2026")

    def test_los_avisos_quedan_como_rastro(self):
        avisos = InboundEvent.objects.filter(debt=self.deuda("CTR-2026-015")).order_by("occurred_at", "pk")
        self.assertEqual([a.result for a in avisos], [
            "en gestion -> en convenio de pago", "pago anotado", "en convenio de pago -> pagada",
        ])
        self.assertEqual(InboundEvent.objects.count(), 14)

    def test_no_le_avisa_a_nadie(self):
        self.assertEqual(OutboundEvent.objects.count(), 0)
        self.assertFalse(Forward.objects.exclude(status=Forward.Status.SENT).exists())

    def test_cada_cosa_lleva_la_fecha_en_que_paso(self):
        felipe = self.deuda("CTR-2025-014")
        self.assertEqual(localtime(felipe.created_at).date(), _date(2026, 8, 18))
        self.assertEqual(localtime(felipe.updated_at).date(), _date(2026, 9, 20))   # acepto el convenio
        self.assertEqual(localtime(Batch.objects.get(external_id="PAT-2026-09-18-01").received_at).date(),
                         _date(2026, 9, 18))
        self.assertEqual(localtime(Forward.objects.get(external_id="APX-2026-08-19-003").sent_at).date(),
                         _date(2026, 8, 19))
        aviso = InboundEvent.objects.get(type="deuda.saldada", debt=self.deuda("CTR-2026-012"))
        self.assertEqual((aviso.received_at - aviso.occurred_at).total_seconds(), 4)

    def test_cargarla_otra_vez_no_cambia_nada(self):
        antes = (Batch.objects.count(), Debt.objects.count(), InboundEvent.objects.count())
        self.assertIn("ya estaba cargada", cargar_demo())
        self.assertEqual((Batch.objects.count(), Debt.objects.count(), InboundEvent.objects.count()), antes)

    def test_reemplazar_la_devuelve_al_comienzo(self):
        """Despues de jugar con ella en la cadena, --reemplazar la deja como era."""
        recibir_evento(evento_de_databridge("deuda.saldada", deuda="CTR-2025-019"))
        self.assertEqual(self.deuda("CTR-2025-019").status, Debt.Status.PAID)

        cargar_demo(reemplazar=True)

        self.assertEqual(self.deuda("CTR-2025-019").status, Debt.Status.OPEN)
        self.assertEqual((Batch.objects.count(), InboundEvent.objects.count()), (2, 14))


class LaDemoNoPisaUnaCarteraReal(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()

    def test_si_patrimonio_ya_entrego_cartera_no_se_toca(self):
        recibir_cartera(self.acreedor, cartera_de_ejemplo())

        salida = cargar_demo()

        self.assertIn("--reemplazar", salida)
        self.assertEqual(Batch.objects.get().payload_hash, huella(cartera_de_ejemplo()))

    def test_reemplazar_borra_solo_lo_de_patrimonio(self):
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        otro = crear_acreedor("77812341-K", "Otro Acreedor")
        suya = cartera_de_ejemplo()
        suya["lote"]["id_externo"] = "OTRO-2026-09-01"
        suya["lote"]["acreedor"]["rut"] = "77812341-K"
        suya["deudas"] = [suya["deudas"][0]]      # Felipe tambien le debe a otro
        recibir_cartera(otro, suya)

        cargar_demo(reemplazar=True)

        self.assertEqual(Debt.objects.filter(creditor=otro).count(), 1)
        self.assertEqual(Debtor.objects.filter(tax_id="16482337-7").count(), 1)
        self.assertEqual(set(Batch.objects.filter(creditor=self.acreedor).values_list("external_id", flat=True)),
                         {"PAT-2026-08-18-01", "PAT-2026-09-18-01"})

    def test_sin_patrimonio_entre_los_clientes_no_hay_demo(self):
        self.acreedor.delete()
        with self.assertRaises(CommandError):
            cargar_demo()


# ==========================================================================
#  El mes siguiente: el acreedor vuelve a mandar una deuda que APOFYX ya tiene
# ==========================================================================

def lote_de_felipe(corte, meses):
    """Una entrega de Patrimonio con solo la deuda de Felipe, a otra fecha de corte."""
    lote = cartera_de_ejemplo()
    lote["lote"]["id_externo"] = f"PAT-{corte}-01"
    lote["lote"]["fecha_corte"] = corte
    felipe = lote["deudas"][0]
    felipe["cargos"] = [{"concepto": f"Arriendo {nombre}", "periodo": periodo, "monto": 520000,
                         "fecha_vencimiento": f"{periodo}-05"} for nombre, periodo in meses]
    lote["deudas"] = [felipe]
    return lote


@override_settings(DATABRIDGE=CON_EVENTOS)
class UnaDeudaPagadaVuelveSiElDeudorSeAtrasa(TestCase):

    def setUp(self):
        self.acreedor = crear_acreedor()
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        recibir_evento(evento_de_databridge("deuda.saldada"))

    def felipe(self):
        return Debt.objects.get(external_id="CTR-2025-014")

    def test_con_un_mes_nuevo_vuelve_a_gestion(self):
        respuesta = recibir_cartera(self.acreedor, lote_de_felipe("2026-10-18", [("octubre", "2026-10")]))

        self.assertEqual(respuesta["resultados"][0]["resultado"], "actualizada")
        self.assertEqual(self.felipe().status, Debt.Status.OPEN)
        self.assertEqual(self.felipe().saldo, Decimal("520000"))

    def test_con_un_mes_que_ya_se_pago_se_rechaza(self):
        """Cobrar septiembre de nuevo seria cobrarlo dos veces."""
        respuesta = recibir_cartera(self.acreedor, lote_de_felipe(
            "2026-10-18", [("septiembre", "2026-09"), ("octubre", "2026-10")]))

        resultado = respuesta["resultados"][0]
        self.assertEqual(resultado["resultado"], "rechazada")
        self.assertEqual(resultado["errores"][0]["codigo"], "deuda_saldada")
        self.assertEqual(self.felipe().status, Debt.Status.PAID)

    def test_retirarla_no_cambia_nada(self):
        lote = lote_de_felipe("2026-10-18", [])
        lote["deudas"] = [{"id_externo": "CTR-2025-014", "accion": "retirar", "motivo_retiro": "pago_directo"}]

        respuesta = recibir_cartera(self.acreedor, lote)

        self.assertEqual(respuesta["resultados"][0]["errores"][0]["codigo"], "deuda_saldada")
        self.assertEqual(self.felipe().status, Debt.Status.PAID)


@override_settings(DATABRIDGE=DATABRIDGE_PRUEBA)
class UnCasoFueraDeMandatoVuelveAlAcreedor(TestCase):
    """
    Pasados los 120 dias de mora APOFYX devuelve el caso (docs 2.2). Si ya lo
    estaba cobrando, rechazar la actualizacion no basta: DataBridge seguiria
    cobrando el monto viejo.
    """

    def setUp(self):
        self.acreedor = crear_acreedor()
        self.campana = campana_de(self.acreedor)
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        #  En enero Felipe sigue debiendo desde agosto: 166 dias.
        self.respuesta = recibir_cartera(self.acreedor, lote_de_felipe(
            "2027-01-18", [("agosto", "2026-08"), ("septiembre", "2026-09")]))

    def test_la_respuesta_dice_que_vuelve_al_acreedor(self):
        resultado = self.respuesta["resultados"][0]
        self.assertEqual(resultado["resultado"], "rechazada")
        self.assertEqual(resultado["errores"][0]["codigo"], "mora_fuera_de_mandato")
        self.assertIn("deja de cobrarla", resultado["errores"][0]["mensaje"])

    def test_apofyx_la_saca_de_su_cartera(self):
        felipe = Debt.objects.get(external_id="CTR-2025-014")
        self.assertEqual(felipe.status, Debt.Status.WITHDRAWN)
        self.assertEqual(felipe.withdrawn_reason, "fuera_de_mandato")

    def test_y_el_retiro_sigue_a_databridge(self):
        forward = Forward.objects.get(batch__external_id="PAT-2027-01-18-01")
        cartera = construir_cartera(forward, self.campana)
        self.assertEqual(cartera["deudas"], [
            {"id_externo": "CTR-2025-014", "accion": "retirar", "motivo_retiro": "fuera_de_mandato"},
        ])

    def test_una_deuda_nueva_fuera_de_mandato_solo_se_rechaza(self):
        lote = lote_de_felipe("2027-02-18", [("agosto", "2026-08")])
        lote["deudas"][0]["id_externo"] = "CTR-2026-099"

        respuesta = recibir_cartera(self.acreedor, lote)

        self.assertEqual(respuesta["resultados"][0]["errores"][0]["codigo"], "mora_fuera_de_mandato")
        self.assertNotIn("deja de cobrarla", respuesta["resultados"][0]["errores"][0]["mensaje"])
        self.assertFalse(Forward.objects.filter(batch__external_id="PAT-2027-02-18-01").exists())


# ==========================================================================
#  El panel muestra la cartera que llego por la integracion
# ==========================================================================

from django.contrib.auth.models import User  # noqa: E402


@override_settings(DATABRIDGE=CON_EVENTOS)
class ElPanelMuestraLaCarteraRecibida(TestCase):
    """
    El panel leia solo los cortes mensuales que se cargaban a mano, y un
    cliente que entrega por la API aparecia sin cartera.
    """

    def setUp(self):
        User.objects.create_user("operador", password="clave-larga-123", is_staff=True)
        self.client.login(username="operador", password="clave-larga-123")
        self.acreedor = crear_acreedor()
        recibir_cartera(self.acreedor, cartera_de_ejemplo())
        recibir_evento(evento_de_databridge("repactacion.aceptada", cuotas=6))

    def test_la_ficha_muestra_la_entrega_y_cada_deuda(self):
        r = self.client.get(reverse("panel:cliente_detalle", args=[self.acreedor.pk]))

        self.assertContains(r, "PAT-2026-09-18-01")
        self.assertContains(r, "CTR-2025-014")
        self.assertNotContains(r, "todavía no ha entregado cartera")
        estados = dict(r.context["recibida"]["estados"])
        self.assertEqual(estados["En convenio"], 1)      # Felipe
        self.assertEqual(estados["En gestión"], 2)       # Valentina y Nandu
        self.assertEqual(r.context["recibida"]["informado_clp"], Decimal("1450000"))
        self.assertEqual(r.context["recibida"]["informado_uf"], Decimal("115.50"))

    def test_el_listado_y_el_resumen_la_cuentan(self):
        empresa = next(e for e in self.client.get(reverse("panel:clientes")).context["empresas"]
                       if e.pk == self.acreedor.pk)
        self.assertEqual(empresa.cartera["registros"], 3)
        #  El ticket, solo sobre las deudas en pesos: Felipe y Valentina.
        self.assertEqual(empresa.cartera["ticket"], Decimal("725000"))
        self.assertEqual(self.client.get(reverse("panel:dashboard")).context["cartera_total"], 3)


# ==========================================================================
#  Todos los clientes con contrato: el que esta al dia viene sin cargos
# ==========================================================================

@override_settings(DATABRIDGE=DATABRIDGE_PRUEBA)
class UnClienteAlDiaNoSeCobra(TestCase):
    """
    En la cartera de ejemplo, Tomas se puso al dia en la oficina y viene sin
    cargos.

    El acreedor manda a todos sus clientes con contrato y APOFYX detecta al
    moroso. De quien esta al dia no se guarda nada; si tenia su deuda en
    gestion, le pago al acreedor por fuera y la deuda se cierra.
    """

    def setUp(self):
        self.acreedor = crear_acreedor()

    def test_uno_nuevo_al_dia_se_acepta_sin_guardar_nada(self):
        respuesta = recibir_cartera(self.acreedor, cartera_de_ejemplo())
        por_id = {r["id_externo"]: r for r in respuesta["resultados"]}
        self.assertEqual(por_id["CTR-2025-022"]["resultado"], "al_dia")
        self.assertEqual(respuesta["rechazadas"], 0)
        self.assertFalse(Debt.objects.filter(external_id="CTR-2025-022").exists())
        self.assertFalse(Debtor.objects.filter(tax_id="15227640-0").exists())

    def test_al_dia_con_su_deuda_en_gestion_la_cierra_y_se_la_pasa_a_databridge(self):
        recibir_cartera(self.acreedor, lote_de_agosto())
        campana = campana_de(self.acreedor)
        respuesta = recibir_cartera(self.acreedor, cartera_de_ejemplo())

        por_id = {r["id_externo"]: r for r in respuesta["resultados"]}
        self.assertEqual(por_id["CTR-2025-022"]["resultado"], "retirada")
        tomas = Debt.objects.get(external_id="CTR-2025-022")
        self.assertEqual(tomas.status, Debt.Status.WITHDRAWN)
        self.assertEqual(tomas.withdrawn_reason, "pago_directo")

        forward = Forward.objects.get(batch__external_id="PAT-2026-09-18-01")
        retiros = [d for d in construir_cartera(forward, campana)["deudas"] if d.get("accion") == "retirar"]
        self.assertEqual(retiros, [{"id_externo": "CTR-2025-022", "accion": "retirar",
                                    "motivo_retiro": "pago_directo"}])

    def test_al_dia_con_una_deuda_ya_pagada_no_cambia_nada(self):
        recibir_cartera(self.acreedor, lote_de_agosto())
        Debt.objects.filter(external_id="CTR-2025-022").update(status=Debt.Status.PAID)
        respuesta = recibir_cartera(self.acreedor, cartera_de_ejemplo())
        por_id = {r["id_externo"]: r for r in respuesta["resultados"]}
        self.assertEqual(por_id["CTR-2025-022"]["resultado"], "al_dia")
        self.assertEqual(Debt.objects.get(external_id="CTR-2025-022").status, Debt.Status.PAID)

    def test_una_deuda_sin_la_lista_de_cargos_sigue_siendo_un_error(self):
        cartera = cartera_de_ejemplo()
        del cartera["deudas"][0]["cargos"]
        respuesta = recibir_cartera(self.acreedor, cartera)
        self.assertEqual(respuesta["resultados"][0]["errores"][0]["codigo"], "sin_cargos")

    @override_settings(DATABRIDGE={**DATABRIDGE_PRUEBA, "MORA_MAXIMA_DIAS": 30})
    def test_el_limite_de_mora_sale_de_la_configuracion(self):
        respuesta = recibir_cartera(self.acreedor, cartera_de_ejemplo())
        por_id = {r["id_externo"]: r for r in respuesta["resultados"]}
        self.assertEqual(por_id["CTR-2025-014"]["errores"][0]["codigo"], "mora_fuera_de_mandato")


# ==========================================================================
#  La empresa conecta su sistema: cuenta y suscripciones por API
# ==========================================================================

class LaEmpresaConectaSuSistema(TestCase):
    """El mismo contrato que atiende DataBridge un tramo mas arriba."""

    def setUp(self):
        self.acreedor = crear_acreedor()
        self.clave, _ = ApiKey.emitir(self.acreedor, "Sistema de arriendos")

    def _auth(self, clave=None):
        return {"authorization": f"Bearer {clave or self.clave}"}

    def test_la_cuenta_dice_de_quien_es_la_clave_y_con_quien_quedo_conectada(self):
        r = self.client.get(reverse("integracion:cuenta"), headers=self._auth())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {
            "rut": RUT_PATRIMONIO, "razon_social": "Patrimonio Inmuebles SpA",
            "nombre": "Patrimonio Inmuebles", "tipo": "acreedor",
            "receptor": {"rut": "77305118-6", "nombre": "APOFYX"},
        })

    def test_la_cuenta_sin_clave_es_401(self):
        r = self.client.get(reverse("integracion:cuenta"), headers=self._auth("apx_inventada"))
        self.assertEqual(r.status_code, 401)

    def test_suscribirse_entrega_el_secreto_y_repetirlo_devuelve_el_mismo(self):
        cuerpo = json.dumps({"url": "http://patrimonio.prueba/api/eventos"})
        uno = self.client.post(reverse("integracion:suscripciones"), cuerpo, content_type="application/json",
                               headers=self._auth()).json()
        dos = self.client.post(reverse("integracion:suscripciones"), cuerpo, content_type="application/json",
                               headers=self._auth()).json()
        self.assertTrue(uno["secreto"].startswith("whsec_"))
        self.assertEqual(uno["secreto"], dos["secreto"])
        self.assertEqual(uno["eventos"], "todos")
        self.assertEqual(self.acreedor.subscriptions.get().url, "http://patrimonio.prueba/api/eventos")

    def test_suscribirse_con_una_url_que_no_es_web_es_400(self):
        r = self.client.post(reverse("integracion:suscripciones"), json.dumps({"url": "ftp://x"}),
                             content_type="application/json", headers=self._auth())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["codigo"], "url_invalida")

    def test_suscribirse_a_un_evento_que_no_existe_es_400(self):
        r = self.client.post(reverse("integracion:suscripciones"),
                             json.dumps({"url": "http://x.cl/e", "eventos": ["pago.inventado"]}),
                             content_type="application/json", headers=self._auth())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["codigo"], "evento_desconocido")

    def test_una_clave_revocada_deja_de_servir(self):
        ApiKey.objects.get().revocar()
        self.assertEqual(self.client.get(reverse("integracion:cuenta"), headers=self._auth()).status_code, 401)


# ==========================================================================
#  La planilla: el mismo contrato para la empresa sin sistema
# ==========================================================================

from . import planilla  # noqa: E402

PLANTILLA = Path(ajustes.BASE_DIR) / "static" / "plantillas" / "cartera-v1.plantilla.csv"


class LaPlanillaEsElMismoContrato(TestCase):

    def leer(self, texto):
        return planilla.leer(texto.encode("utf-8"), "CSV-1", "2026-09-18", RUT_PATRIMONIO)

    def test_la_plantilla_es_la_misma_cartera_que_el_ejemplo_json(self):
        cartera = planilla.leer(PLANTILLA.read_bytes(), "PAT-2026-09-18-01", "2026-09-18", RUT_PATRIMONIO)
        self.assertEqual(cartera["deudas"], cartera_de_ejemplo()["deudas"])

    def test_la_plantilla_es_la_del_contrato_publicado(self):
        publicada = (Path(ajustes.BASE_DIR).parent / "TB_web" / "docs" / "integracion"
                     / "ejemplos" / "cartera-v1.plantilla.csv")
        if not publicada.exists():
            self.skipTest("El repositorio de DataBridge no esta al lado")
        self.assertEqual(PLANTILLA.read_bytes(), publicada.read_bytes())

    def test_una_fila_sin_cargo_es_un_cliente_al_dia(self):
        encabezado = ";".join(planilla.COLUMNAS)
        cartera = self.leer(f"{encabezado}\nCTR-1;registrar;;16482337-7;persona;Felipe;f@correo.cl;;CLP;Arriendo;;;;;\n")
        self.assertEqual(cartera["deudas"][0]["cargos"], [])

    def test_en_pesos_un_punto_es_un_separador_de_miles(self):
        encabezado = ";".join(planilla.COLUMNAS)
        with self.assertRaises(CarteraInvalida) as caso:
            self.leer(f"{encabezado}\nCTR-1;registrar;;16482337-7;persona;Felipe;;;CLP;Arriendo;;Julio;;520.000;2026-07-05\n")
        self.assertIn("sin puntos ni comas", caso.exception.mensaje)

    def test_sin_las_columnas_del_contrato_se_rechaza_entera(self):
        with self.assertRaises(CarteraInvalida) as caso:
            self.leer("email;nombre;monto\nana@correo.cl;Ana;1000\n")
        self.assertIn("Faltan columnas", caso.exception.mensaje)

    def test_una_deuda_con_filas_distintas_dice_cual_fila(self):
        encabezado = ";".join(planilla.COLUMNAS)
        with self.assertRaises(CarteraInvalida) as caso:
            self.leer(f"{encabezado}\n"
                      "CTR-1;registrar;;16482337-7;persona;Felipe;;;CLP;Arriendo;;Julio;;520000;2026-07-05\n"
                      "CTR-1;registrar;;18905214-6;persona;Felipe;;;CLP;Arriendo;;Agosto;;520000;2026-08-05\n")
        self.assertTrue(caso.exception.mensaje.startswith("Fila 3: la deuda CTR-1 tiene otro deudor_rut"))


# ==========================================================================
#  La conexion con la plataforma de pagos, desde el panel
# ==========================================================================

from .models import PlatformConnection  # noqa: E402
from .plataforma import ConexionFallida, conectar, plataforma  # noqa: E402
from .reenvio import asegurar_mandato_y_campana  # noqa: E402


class PlataformaFalsa:
    """Hace de DataBridge al conectar: responde la cuenta y la suscripcion."""

    def __init__(self, rut="77305118-6", caida=False):
        self.rut, self.caida, self.llamadas = rut, caida, []

    def consultar(self, ruta):
        if self.caida:
            raise ErrorDataBridge("Sin respuesta de DataBridge")
        self.llamadas.append(("GET", ruta, None))
        return {"rut": self.rut, "nombre": "APOFYX", "tipo": "agencia",
                "receptor": {"rut": None, "nombre": "DataBridge"}}

    def enviar(self, ruta, cuerpo):
        self.llamadas.append(("POST", ruta, cuerpo))
        return {"url": cuerpo["url"], "eventos": "todos", "secreto": "whsec_de_databridge"}


@override_settings(DATABRIDGE={**DATABRIDGE_PRUEBA, "URL": "", "CLAVE": ""})
class APOFYXSeConectaDesdeElPanel(TestCase):

    def test_conectar_comprueba_la_clave_se_suscribe_y_guarda_todo(self):
        falsa = PlataformaFalsa()
        fila = conectar("http://databridge.prueba/", "tbk_clave", "http://apofyx.prueba/api/v1/eventos", falsa)
        self.assertEqual(falsa.llamadas[0][:2], ("GET", "/api/v1/cuenta"))
        self.assertEqual(falsa.llamadas[1], ("POST", "/api/v1/suscripciones",
                                             {"url": "http://apofyx.prueba/api/v1/eventos"}))
        self.assertEqual(fila.platform_name, "DataBridge")
        self.assertEqual(fila.url, "http://databridge.prueba")

    def test_desde_ese_momento_vale_la_conexion_y_no_la_configuracion(self):
        self.assertEqual(plataforma()["URL"], "")
        conectar("http://databridge.prueba", "tbk_clave", "http://apofyx.prueba/api/v1/eventos", PlataformaFalsa())
        conf = plataforma()
        self.assertEqual((conf["URL"], conf["CLAVE"], conf["SECRETO_EVENTOS"]),
                         ("http://databridge.prueba", "tbk_clave", "whsec_de_databridge"))

    def test_una_clave_de_otra_empresa_no_se_guarda(self):
        with self.assertRaises(ConexionFallida) as caso:
            conectar("http://databridge.prueba", "tbk_ajena", "http://apofyx.prueba/e", PlataformaFalsa(rut="76418902-7"))
        self.assertIn("no de APOFYX", str(caso.exception))
        self.assertFalse(PlatformConnection.objects.exists())

    def test_si_la_plataforma_no_responde_no_se_guarda_nada(self):
        with self.assertRaises(ConexionFallida):
            conectar("http://databridge.prueba", "tbk_clave", "http://apofyx.prueba/e", PlataformaFalsa(caida=True))
        self.assertFalse(PlatformConnection.objects.exists())

    def test_la_pagina_del_panel_conecta(self):
        from unittest import mock
        from django.contrib.auth.models import User

        User.objects.create_user("operador", password="clave-larga-123", is_staff=True)
        self.client.login(username="operador", password="clave-larga-123")
        with mock.patch("crm.panel_views.conectar") as conectar_falso:
            conectar_falso.return_value = PlatformConnection(platform_name="DataBridge")
            r = self.client.post(reverse("panel:plataforma"), {
                "accion": "conectar", "url": "http://databridge.prueba", "api_key": "tbk_clave",
                "url_avisos": "http://apofyx.prueba/api/v1/eventos",
            })
        self.assertRedirects(r, reverse("panel:plataforma"))
        conectar_falso.assert_called_once_with("http://databridge.prueba", "tbk_clave",
                                               "http://apofyx.prueba/api/v1/eventos")


@override_settings(DATABRIDGE=DATABRIDGE_PRUEBA)
class ElMandatoPresentaALaEmpresa(TestCase):
    """DataBridge registra a una empresa nueva con los nombres que le manda APOFYX."""

    def test_el_mandato_lleva_la_razon_social_y_el_nombre_de_fantasia(self):
        acreedor = crear_acreedor()
        campana = campana_de(acreedor)
        recibir_cartera(acreedor, cartera_de_ejemplo())
        cliente = ClienteFalso()
        asegurar_mandato_y_campana(cliente, Batch.objects.get(), campana)
        ruta, mandato = cliente.llamadas[0]
        self.assertEqual(ruta, "/api/v1/mandatos")
        self.assertEqual(mandato["razon_social"], "Patrimonio Inmuebles SpA")
        self.assertEqual(mandato["nombre_fantasia"], "Patrimonio Inmuebles")

    def test_la_cartera_que_sale_nombra_a_la_empresa(self):
        acreedor = crear_acreedor()
        campana = campana_de(acreedor)
        recibir_cartera(acreedor, cartera_de_ejemplo())
        forward = Forward.objects.get()
        self.assertEqual(construir_cartera(forward, campana)["lote"]["acreedor"]["nombre_fantasia"],
                         "Patrimonio Inmuebles")
