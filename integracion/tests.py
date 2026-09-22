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
from crm.models import Campaign, CampaignFunnelSnapshot, Creditor, Industry

from .intake import CarteraInvalida, recibir_cartera
from .models import ApiKey

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cartera-v1-patrimonio.json"
RUT_PATRIMONIO = "76418902-7"


def cartera_de_ejemplo():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def crear_acreedor(tax_id=RUT_PATRIMONIO, nombre="Patrimonio Inmuebles"):
    rubro, _ = Industry.objects.get_or_create(
        slug="arriendos", defaults={"name": "Corretaje y arriendos"}
    )
    return Creditor.objects.create(
        legal_name=f"{nombre} SpA", trade_name=nombre, tax_id=tax_id,
        industry=rubro, status=Creditor.Status.ACTIVE,
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
        Los tramos son los de crm_portfoliohandover, para que la entrega y el
        panel hablen de lo mismo.
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
        self.assertEqual(respuesta["aceptadas"], 2)
        self.assertEqual(respuesta["rechazadas"], 2)  # el RUT malo y el retiro sin deuda previa
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
        self.assertEqual(respuesta["aceptadas"], 3)


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
        self.assertEqual(r.json()["aceptadas"], 3)

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
        self.assertEqual(self.cartera["deudas"], cartera_de_ejemplo()["deudas"])

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

        self.assertEqual(respuesta["aceptadas"], 3)
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
