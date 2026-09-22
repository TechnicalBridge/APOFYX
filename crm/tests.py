"""
Pruebas del CRM: modelos, formulario, sitio publico y panel.

Se prueba el comportamiento de la aplicacion, no las restricciones de MySQL
(esas se verificaron directamente contra el motor y viven en el DDL).

La excepcion es EsquemaYModelosCalzan, al final: Django crea la base de pruebas
desde las migraciones, y las migraciones no llevan ni uno de los CHECK del DDL.
Esa clase compara el texto del DDL con las opciones de los modelos, sin tocar la
base, porque ese desajuste no lo puede encontrar ninguna otra prueba de aqui.
"""

import re
from datetime import date
from decimal import Decimal

from django.conf import settings as ajustes
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from .esquema import clausula_check, ddl as leer_ddl, valores_del_enum
from .forms import CreditorForm, LeadForm
from .models import (
    PortfolioHandover, Campaign, CampaignFunnelSnapshot, Creditor, CreditorContact,
    Industry, Lead,
)
from .panel_views import adjuntar_cartera


def crear_empresa(**extra):
    """Empresa minima viable, con rubro propio para no chocar con el unique."""
    rubro = extra.pop("industry", None) or Industry.objects.create(
        name=f"Rubro {Industry.objects.count()}",
        slug=f"rubro-{Industry.objects.count()}",
    )
    datos = {
        "legal_name": "Vitalis Fitness SpA",
        "trade_name": "Vitalis Gym",
        "tax_id": "76543210-3",
        "industry": rubro,
        "status": Creditor.Status.ACTIVE,
    }
    datos.update(extra)
    return Creditor.objects.create(**datos)


# ==========================================================================
#  Modelos
# ==========================================================================

class RutFormateadoTest(TestCase):
    """El RUT se guarda normalizado y se muestra con puntos."""

    def test_agrega_puntos(self):
        empresa = crear_empresa(tax_id="76543210-3")
        self.assertEqual(empresa.rut_formateado, "76.543.210-3")

    def test_conserva_el_digito_verificador_k(self):
        empresa = crear_empresa(tax_id="77812341-K")
        self.assertEqual(empresa.rut_formateado, "77.812.341-K")

    def test_rut_corto(self):
        empresa = crear_empresa(tax_id="5126663-3")
        self.assertEqual(empresa.rut_formateado, "5.126.663-3")

    def test_sin_guion_devuelve_el_valor_tal_cual(self):
        """No revienta con datos mal formados; los deja pasar."""
        empresa = crear_empresa(tax_id="76543210")
        self.assertEqual(empresa.rut_formateado, "76543210")


class ContactoPrincipalTest(TestCase):
    """A lo mas un contacto principal por empresa."""

    def setUp(self):
        self.empresa = crear_empresa()

    def test_devuelve_el_marcado_como_principal(self):
        CreditorContact.objects.create(
            creditor=self.empresa, full_name="Rodrigo Munoz",
            email="r@vitalis.cl", is_primary=False,
        )
        principal = CreditorContact.objects.create(
            creditor=self.empresa, full_name="Paulina Cortes",
            email="p@vitalis.cl", is_primary=True,
        )
        self.assertEqual(self.empresa.contacto_principal, principal)

    def test_marcar_uno_nuevo_degrada_al_anterior(self):
        primero = CreditorContact.objects.create(
            creditor=self.empresa, full_name="Primero",
            email="1@vitalis.cl", is_primary=True,
        )
        CreditorContact.objects.create(
            creditor=self.empresa, full_name="Segundo",
            email="2@vitalis.cl", is_primary=True,
        )
        primero.refresh_from_db()
        self.assertFalse(primero.is_primary)
        self.assertEqual(
            CreditorContact.objects.filter(creditor=self.empresa, is_primary=True).count(), 1
        )

    def test_no_degrada_a_los_de_otra_empresa(self):
        otra = crear_empresa(tax_id="99999999-9", trade_name="Otra")
        suyo = CreditorContact.objects.create(
            creditor=otra, full_name="De la otra", email="o@otra.cl", is_primary=True,
        )
        CreditorContact.objects.create(
            creditor=self.empresa, full_name="De esta", email="e@vitalis.cl", is_primary=True,
        )
        suyo.refresh_from_db()
        self.assertTrue(suyo.is_primary)

    def test_sin_contactos_devuelve_none(self):
        self.assertIsNone(self.empresa.contacto_principal)


class CarteraTest(TestCase):
    """
    El ticket medio se pondera por cantidad de registros.

    Es el calculo mas facil de equivocar del proyecto: promediar los tres
    tramos daria un numero distinto y falso.
    """

    def setUp(self):
        self.empresa = crear_empresa()
        for tramo, registros, ticket in [
            ("1-30", 3100, 38900), ("31-90", 2200, 42700), ("91-120", 900, 45100),
        ]:
            PortfolioHandover.objects.create(
                creditor=self.empresa, period_month=date(2026, 8, 1),
                overdue_bracket=tramo, debtor_count=registros,
                average_debt_clp=Decimal(ticket),
            )

    def test_suma_los_registros_del_periodo(self):
        self.assertEqual(self.empresa.cartera_actual["registros"], 6200)

    def test_el_ticket_va_ponderado_y_no_promediado(self):
        # Ponderado: (3100*38900 + 2200*42700 + 900*45100) / 6200
        esperado = (3100 * 38900 + 2200 * 42700 + 900 * 45100) / 6200
        promedio_simple = (38900 + 42700 + 45100) / 3
        obtenido = float(self.empresa.cartera_actual["ticket"])

        self.assertAlmostEqual(obtenido, esperado, places=2)
        self.assertNotAlmostEqual(obtenido, promedio_simple, places=0)

    def test_usa_solo_el_ultimo_periodo(self):
        PortfolioHandover.objects.create(
            creditor=self.empresa, period_month=date(2026, 9, 1),
            overdue_bracket="1-30", debtor_count=100, average_debt_clp=Decimal(10000),
        )
        cartera = self.empresa.cartera_actual
        self.assertEqual(cartera["periodo"], date(2026, 9, 1))
        self.assertEqual(cartera["registros"], 100)

    def test_sin_cartera_devuelve_none(self):
        vacia = crear_empresa(tax_id="11111111-1", trade_name="Vacia")
        self.assertIsNone(vacia.cartera_actual)


class AdjuntarCarteraTest(TestCase):
    """El helper del panel deja .cartera en cada objeto."""

    def test_empresa_sin_tramos_queda_en_cero(self):
        empresa = crear_empresa()
        adjuntar_cartera([empresa])
        self.assertEqual(empresa.cartera["registros"], 0)
        self.assertEqual(empresa.cartera["tramos"], [])
        self.assertIsNone(empresa.cartera["periodo"])

    def test_coincide_con_la_propiedad_del_modelo(self):
        empresa = crear_empresa()
        PortfolioHandover.objects.create(
            creditor=empresa, period_month=date(2026, 8, 1), overdue_bracket="1-30",
            debtor_count=500, average_debt_clp=Decimal(20000),
        )
        adjuntar_cartera([empresa])
        self.assertEqual(
            empresa.cartera["registros"], empresa.cartera_actual["registros"]
        )


class EmbudoCampanaTest(TestCase):

    def setUp(self):
        self.campana = Campaign.objects.create(
            creditor=crear_empresa(), name="Agosto",
            starts_on=date(2026, 8, 1), channels=["whatsapp"],
        )

    def test_sin_mediciones_devuelve_none(self):
        self.assertIsNone(self.campana.embudo)

    def test_suma_varias_mediciones(self):
        CampaignFunnelSnapshot.objects.create(
            campaign=self.campana, measured_on=date(2026, 8, 15),
            messages_sent=1000, messages_delivered=900, messages_opened=300, link_clicks=60,
        )
        CampaignFunnelSnapshot.objects.create(
            campaign=self.campana, measured_on=date(2026, 8, 31),
            messages_sent=500, messages_delivered=450, messages_opened=150, link_clicks=30,
        )
        embudo = self.campana.embudo
        self.assertEqual(embudo["enviados"], 1500)
        self.assertEqual(embudo["clics"], 90)

    def test_calcula_las_tasas(self):
        CampaignFunnelSnapshot.objects.create(
            campaign=self.campana, measured_on=date(2026, 8, 31),
            messages_sent=1000, messages_delivered=900, messages_opened=300, link_clicks=60,
        )
        embudo = self.campana.embudo
        self.assertEqual(embudo["tasa_entrega"], 90.0)   # 900/1000
        self.assertEqual(embudo["tasa_apertura"], 33.3)  # 300/900
        self.assertEqual(embudo["tasa_clic"], 20.0)      # 60/300

    def test_no_divide_por_cero(self):
        CampaignFunnelSnapshot.objects.create(
            campaign=self.campana, measured_on=date(2026, 8, 31),
            messages_sent=10, messages_delivered=0, messages_opened=0, link_clicks=0,
        )
        embudo = self.campana.embudo
        self.assertEqual(embudo["tasa_apertura"], 0)
        self.assertEqual(embudo["tasa_clic"], 0)


class LeadTest(TestCase):
    """
    La regla de 'convertido exige empresa' se valida en Python.

    MySQL la rechaza como CHECK (error 3823) porque creditor_id participa en una
    clave foranea con ON DELETE SET NULL.
    """

    def test_convertido_sin_empresa_es_invalido(self):
        lead = Lead(
            full_name="Ana", company_name="X", email="a@x.cl",
            status=Lead.Status.CONVERTED,
        )
        with self.assertRaises(ValidationError) as caso:
            lead.clean()
        self.assertIn("converted_creditor", caso.exception.message_dict)

    def test_convertido_con_empresa_es_valido(self):
        lead = Lead(
            full_name="Ana", company_name="X", email="a@x.cl",
            status=Lead.Status.CONVERTED, converted_creditor=crear_empresa(),
        )
        lead.clean()  # no debe lanzar

    def test_los_otros_estados_no_exigen_empresa(self):
        for estado in [Lead.Status.NEW, Lead.Status.CONTACTED,
                       Lead.Status.QUALIFIED, Lead.Status.DISCARDED]:
            Lead(full_name="Ana", company_name="X", email="a@x.cl",
                 status=estado).clean()


# ==========================================================================
#  Formulario
# ==========================================================================

class LeadFormTest(TestCase):

    def setUp(self):
        self.rubro = Industry.objects.create(name="Gimnasios", slug="gimnasios")

    def datos(self, **extra):
        base = {
            "full_name": "Marcela Rios",
            "company_name": "Gimnasios Andino",
            "email": "mrios@andino.cl",
            "industry": self.rubro.pk,
        }
        base.update(extra)
        return base

    def test_los_cuatro_obligatorios_bastan(self):
        self.assertTrue(LeadForm(data=self.datos()).is_valid())

    def test_el_resto_es_opcional(self):
        for campo in ("phone", "job_title", "estimated_debtor_count",
                      "estimated_overdue_clp", "current_collection_method", "inquiry_message"):
            self.assertFalse(
                LeadForm().fields[campo].required,
                f"{campo} no deberia ser obligatorio",
            )

    def test_correo_invalido_se_rechaza(self):
        form = LeadForm(data=self.datos(email="esto-no-es-correo"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_falta_el_nombre(self):
        datos = self.datos()
        del datos["full_name"]
        form = LeadForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn("full_name", form.errors)

    def test_cartera_negativa_se_rechaza(self):
        form = LeadForm(data=self.datos(estimated_debtor_count=-5))
        self.assertFalse(form.is_valid())

    def test_gestion_actual_fuera_de_las_opciones(self):
        form = LeadForm(data=self.datos(current_collection_method="inventado"))
        self.assertFalse(form.is_valid())

    def test_aplica_las_clases_de_bootstrap(self):
        form = LeadForm()
        self.assertIn("form-select", form.fields["industry"].widget.attrs["class"])
        self.assertIn("form-control", form.fields["full_name"].widget.attrs["class"])

    def test_solo_ofrece_rubros_activos(self):
        Industry.objects.create(name="Retirado", slug="retirado", is_active=False)
        opciones = LeadForm().fields["industry"].queryset
        self.assertNotIn("retirado", [r.slug for r in opciones])


# ==========================================================================
#  Sitio publico
# ==========================================================================

class SitioPublicoTest(TestCase):

    def setUp(self):
        self.rubro = Industry.objects.create(name="Gimnasios", slug="gimnasios")
        self.empresa = crear_empresa(industry=self.rubro)
        PortfolioHandover.objects.create(
            creditor=self.empresa, period_month=date(2026, 8, 1), overdue_bracket="1-30",
            debtor_count=6200, average_debt_clp=Decimal(41300),
        )
        campana = Campaign.objects.create(
            creditor=self.empresa, name="Agosto", starts_on=date(2026, 8, 1),
            channels=["whatsapp"],
        )
        CampaignFunnelSnapshot.objects.create(
            campaign=campana, measured_on=date(2026, 8, 31),
            messages_sent=1000, messages_delivered=913, messages_opened=300, link_clicks=60,
        )

    def test_portada_responde(self):
        r = self.client.get(reverse("site:home"))
        self.assertEqual(r.status_code, 200)

    def test_las_cifras_salen_de_la_base(self):
        r = self.client.get(reverse("site:home"))
        cifras = r.context["cifras"]
        self.assertEqual(cifras["cartera"], 6200)
        self.assertEqual(cifras["empresas"], 1)
        self.assertEqual(cifras["rubros"], 1)
        self.assertEqual(cifras["tasa_entrega"], 91.3)

    def test_la_portada_no_vende_planes(self):
        """APOFYX no publica tarifas: el sitio lleva al formulario."""
        r = self.client.get(reverse("site:home"))
        self.assertNotIn("planes", r.context)
        self.assertNotContains(r, "#planes")

    def test_la_portada_no_se_atribuye_ia(self):
        """La IA la aporta DataBridge, no APOFYX (docs 7.3)."""
        r = self.client.get(reverse("site:home"))
        self.assertNotContains(r, "asistida por IA")

    def test_lista_los_clientes_activos(self):
        crear_empresa(tax_id="88888888-8", trade_name="Pausada",
                      status=Creditor.Status.PAUSED)
        r = self.client.get(reverse("site:home"))
        nombres = [e.trade_name for e in r.context["clientes"]]
        self.assertIn("Vitalis Gym", nombres)
        self.assertNotIn("Pausada", nombres)

    def test_sin_datos_no_revienta(self):
        """Una base vacia no debe romper la portada ni dividir por cero."""
        CampaignFunnelSnapshot.objects.all().delete()
        PortfolioHandover.objects.all().delete()
        Creditor.objects.all().delete()
        r = self.client.get(reverse("site:home"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["cifras"]["tasa_entrega"], 0)

    def test_gracias_responde(self):
        self.assertEqual(self.client.get(reverse("site:gracias")).status_code, 200)


class ContactoTest(TestCase):

    def setUp(self):
        self.rubro = Industry.objects.create(name="Gimnasios", slug="gimnasios")
        self.url = reverse("site:contacto")

    def datos(self, **extra):
        base = {
            "full_name": "Marcela Rios",
            "company_name": "Gimnasios Andino",
            "email": "mrios@andino.cl",
            "industry": self.rubro.pk,
        }
        base.update(extra)
        return base

    def test_get_redirige_a_la_portada(self):
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse("site:home"))

    def test_envio_valido_crea_el_lead_y_redirige(self):
        r = self.client.post(self.url, self.datos())
        self.assertRedirects(r, reverse("site:gracias"))
        lead = Lead.objects.get()
        self.assertEqual(lead.full_name, "Marcela Rios")
        self.assertEqual(lead.source, Lead.Source.FORM)
        self.assertEqual(lead.status, Lead.Status.NEW)

    def test_guarda_los_campos_de_calificacion(self):
        self.client.post(self.url, self.datos(
            job_title="Gerenta de Finanzas", estimated_debtor_count=1800,
            estimated_overdue_clp=340000000, current_collection_method="nadie",
        ))
        lead = Lead.objects.get()
        self.assertEqual(lead.job_title, "Gerenta de Finanzas")
        self.assertEqual(lead.estimated_debtor_count, 1800)
        self.assertEqual(lead.estimated_overdue_clp, 340000000)
        self.assertEqual(lead.current_collection_method, "nadie")

    def test_envio_invalido_devuelve_400_y_no_crea_nada(self):
        datos = self.datos()
        del datos["email"]
        r = self.client.post(self.url, datos)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Lead.objects.count(), 0)

    def test_el_error_conserva_lo_escrito(self):
        """El visitante no debe perder lo que ya habia llenado."""
        datos = self.datos(email="malo", company_name="Mi Empresa SpA")
        r = self.client.post(self.url, datos)
        self.assertContains(r, "Mi Empresa SpA", status_code=400)


# ==========================================================================
#  Panel
# ==========================================================================

class PanelAccesoTest(TestCase):
    """Ninguna vista del panel se ve sin sesion."""

    def setUp(self):
        self.empresa = crear_empresa()

    def rutas(self):
        return [
            reverse("panel:dashboard"),
            reverse("panel:clientes"),
            reverse("panel:cliente_detalle", args=[self.empresa.pk]),
            reverse("panel:leads"),
        ]

    def test_sin_sesion_redirige_al_login(self):
        for ruta in self.rutas():
            r = self.client.get(ruta)
            self.assertEqual(r.status_code, 302, ruta)
            self.assertIn(reverse("panel:login"), r.url, ruta)

    def test_con_sesion_responde(self):
        User.objects.create_user("operador", password="clave-larga-123")
        self.client.login(username="operador", password="clave-larga-123")
        for ruta in self.rutas():
            self.assertEqual(self.client.get(ruta).status_code, 200, ruta)


class PanelDatosTest(TestCase):

    def setUp(self):
        User.objects.create_user("operador", password="clave-larga-123")
        self.client.login(username="operador", password="clave-larga-123")

        self.salud = Industry.objects.create(name="Salud", slug="salud")
        self.gym = Industry.objects.create(name="Gimnasios", slug="gimnasios")

        self.vitalis = crear_empresa(industry=self.gym)
        self.clinica = crear_empresa(
            tax_id="76998877-7", trade_name="Clinica Sonrisa",
            legal_name="Dentales SpA", industry=self.salud,
            status=Creditor.Status.PAUSED,
        )
        PortfolioHandover.objects.create(
            creditor=self.vitalis, period_month=date(2026, 8, 1), overdue_bracket="1-30",
            debtor_count=6200, average_debt_clp=Decimal(41300),
        )
        campana = Campaign.objects.create(
            creditor=self.vitalis, name="Agosto", starts_on=date(2026, 8, 1),
            status=Campaign.Status.RUNNING, channels=["whatsapp"],
        )
        CampaignFunnelSnapshot.objects.create(
            campaign=campana, measured_on=date(2026, 8, 31),
            messages_sent=1000, messages_delivered=900, messages_opened=300, link_clicks=60, fraud_reports=25,
        )
        Lead.objects.create(full_name="Ana", company_name="X", email="a@x.cl")
        Lead.objects.create(
            full_name="Beto", company_name="Y", email="b@y.cl",
            source=Lead.Source.ASSISTANT, status=Lead.Status.CONTACTED,
        )

    # --- Resumen ---

    def test_kpis_del_resumen(self):
        c = self.client.get(reverse("panel:dashboard")).context
        self.assertEqual(c["clientes_total"], 2)
        self.assertEqual(c["clientes_activos"], 1)   # la clinica esta pausada
        self.assertEqual(c["cartera_total"], 6200)
        self.assertEqual(c["campanas_en_curso"], 1)
        self.assertEqual(c["leads_nuevos"], 1)       # el otro esta contactado

    def test_embudo_y_tasas_del_resumen(self):
        c = self.client.get(reverse("panel:dashboard")).context
        self.assertEqual(c["embudo"]["enviados"], 1000)
        self.assertEqual(c["embudo"]["fraudes"], 25)
        self.assertEqual(c["tasas"]["entrega"], 90.0)
        self.assertEqual(c["tasas"]["clic"], 20.0)

    def test_el_resumen_no_revienta_con_la_base_vacia(self):
        Creditor.objects.all().delete()
        Lead.objects.all().delete()
        r = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["tasas"]["entrega"], 0)

    # --- Listado de clientes ---

    def test_listado_muestra_todas(self):
        c = self.client.get(reverse("panel:clientes")).context
        self.assertEqual(len(c["empresas"]), 2)
        self.assertFalse(c["hay_filtros"])

    def test_filtra_por_rubro(self):
        c = self.client.get(reverse("panel:clientes"), {"rubro": "salud"}).context
        self.assertEqual([e.trade_name for e in c["empresas"]], ["Clinica Sonrisa"])
        self.assertTrue(c["hay_filtros"])

    def test_filtra_por_estado(self):
        c = self.client.get(reverse("panel:clientes"), {"estado": "paused"}).context
        self.assertEqual(len(c["empresas"]), 1)

    def test_busca_por_nombre_de_fantasia(self):
        c = self.client.get(reverse("panel:clientes"), {"q": "vitalis"}).context
        self.assertEqual(len(c["empresas"]), 1)

    def test_busca_por_razon_social(self):
        c = self.client.get(reverse("panel:clientes"), {"q": "Dentales"}).context
        self.assertEqual(len(c["empresas"]), 1)

    def test_busca_por_rut(self):
        c = self.client.get(reverse("panel:clientes"), {"q": "76998877"}).context
        self.assertEqual(len(c["empresas"]), 1)

    def test_busqueda_sin_resultados(self):
        c = self.client.get(reverse("panel:clientes"), {"q": "zzzz"}).context
        self.assertEqual(len(c["empresas"]), 0)

    def test_combina_filtros(self):
        c = self.client.get(
            reverse("panel:clientes"), {"rubro": "salud", "estado": "active"}
        ).context
        self.assertEqual(len(c["empresas"]), 0)   # la de salud esta pausada

    def test_el_listado_adjunta_la_cartera(self):
        c = self.client.get(reverse("panel:clientes")).context
        por_nombre = {e.trade_name: e for e in c["empresas"]}
        self.assertEqual(por_nombre["Vitalis Gym"].cartera["registros"], 6200)
        self.assertEqual(por_nombre["Clinica Sonrisa"].cartera["registros"], 0)

    # --- Ficha ---

    def test_ficha_trae_cartera_y_campanas(self):
        c = self.client.get(
            reverse("panel:cliente_detalle", args=[self.vitalis.pk])
        ).context
        self.assertEqual(c["empresa"].cartera["registros"], 6200)
        self.assertEqual(len(c["campanas"]), 1)
        self.assertEqual(c["campanas"][0]["embudo"]["enviados"], 1000)

    def test_ficha_inexistente_devuelve_404(self):
        r = self.client.get(reverse("panel:cliente_detalle", args=[99999]))
        self.assertEqual(r.status_code, 404)

    # --- Leads ---

    def test_listado_de_leads(self):
        c = self.client.get(reverse("panel:leads")).context
        self.assertEqual(len(c["leads"]), 2)

    def test_filtra_leads_por_origen(self):
        c = self.client.get(reverse("panel:leads"), {"origen": "assistant"}).context
        self.assertEqual([l.full_name for l in c["leads"]], ["Beto"])

    def test_filtra_leads_por_estado(self):
        c = self.client.get(reverse("panel:leads"), {"estado": "new"}).context
        self.assertEqual([l.full_name for l in c["leads"]], ["Ana"])

    def test_el_asistente_no_se_carga_en_el_panel(self):
        """El widget es para visitantes del sitio; adentro estorba."""
        r = self.client.get(reverse("panel:dashboard"))
        self.assertNotContains(r, "ap-chat-boton")
        self.assertNotContains(r, "asistente.js")


class ReprModelosCrmTest(TestCase):
    """Los __str__ salen en el admin y en los desplegables."""

    def test_empresa_y_rubro(self):
        empresa = crear_empresa()
        self.assertEqual(str(empresa), "Vitalis Gym")
        self.assertEqual(str(empresa.industry), empresa.industry.name)

    def test_contacto_nombra_a_su_empresa(self):
        empresa = crear_empresa()
        contacto = CreditorContact.objects.create(
            creditor=empresa, full_name="Paulina Cortes", email="p@v.cl",
        )
        self.assertEqual(str(contacto), "Paulina Cortes (Vitalis Gym)")

    def test_cartera_campana_y_metrica(self):
        empresa = crear_empresa()
        cartera = PortfolioHandover.objects.create(
            creditor=empresa, period_month=date(2026, 8, 1), overdue_bracket="1-30",
            debtor_count=10, average_debt_clp=Decimal(1000),
        )
        self.assertIn("2026-08", str(cartera))

        campana = Campaign.objects.create(
            creditor=empresa, name="Agosto", starts_on=date(2026, 8, 1),
            channels=["sms"],
        )
        self.assertEqual(str(campana), "Agosto")

        metrica = CampaignFunnelSnapshot.objects.create(
            campaign=campana, measured_on=date(2026, 8, 31),
        )
        self.assertIn("31-08-2026", str(metrica))

    def test_lead(self):
        lead = Lead.objects.create(
            full_name="Ana Soto", company_name="Andino", email="a@a.cl",
        )
        self.assertEqual(str(lead), "Ana Soto - Andino")


class AdminCrmTest(TestCase):
    """
    Las columnas calculadas del admin se ejecutan al renderizar el listado.

    Si una revienta —por un None inesperado, por ejemplo— el error solo
    aparece al abrir la pagina. Por eso se recorren todas aca.
    """

    def setUp(self):
        User.objects.create_superuser("jefe", "j@apofyx.cl", "clave-larga-123")
        self.client.login(username="jefe", password="clave-larga-123")

        self.empresa = crear_empresa()
        CreditorContact.objects.create(
            creditor=self.empresa, full_name="Paulina Cortes",
            email="p@v.cl", is_primary=True,
        )
        PortfolioHandover.objects.create(
            creditor=self.empresa, period_month=date(2026, 8, 1), overdue_bracket="1-30",
            debtor_count=6200, average_debt_clp=Decimal(41300),
        )
        campana = Campaign.objects.create(
            creditor=self.empresa, name="Agosto", starts_on=date(2026, 8, 1),
            channels=["whatsapp"],
        )
        CampaignFunnelSnapshot.objects.create(
            campaign=campana, measured_on=date(2026, 8, 31),
            messages_sent=1000, messages_delivered=900, messages_opened=300, link_clicks=60,
        )
        for estado, _ in Lead.Status.choices:
            Lead.objects.create(
                full_name=f"Lead {estado}", company_name="X",
                email=f"{estado}@x.cl", status=estado,
                converted_creditor=self.empresa if estado == Lead.Status.CONVERTED else None,
            )

    def test_listados(self):
        for modelo in ("industry", "creditor", "creditorcontact", "portfoliohandover",
                       "campaign", "campaignfunnelsnapshot", "lead"):
            r = self.client.get(f"/admin/crm/{modelo}/")
            self.assertEqual(r.status_code, 200, modelo)

    def test_columnas_calculadas_del_listado_de_empresas(self):
        r = self.client.get("/admin/crm/creditor/")
        self.assertContains(r, "76.543.210-3")   # rut_formateado
        self.assertContains(r, "6.200")          # cartera_registros

    def test_empresa_sin_cartera_muestra_guion(self):
        crear_empresa(tax_id="11111111-1", trade_name="Sin cartera")
        r = self.client.get("/admin/crm/creditor/")
        self.assertContains(r, "—")

    def test_campana_sin_mediciones_no_revienta(self):
        Campaign.objects.create(
            creditor=self.empresa, name="Vacia", starts_on=date(2026, 9, 1),
            channels=["sms"],
        )
        r = self.client.get("/admin/crm/campaign/")
        self.assertContains(r, "sin mediciones")

    def test_todos_los_estados_de_lead_se_pintan(self):
        r = self.client.get("/admin/crm/lead/")
        self.assertEqual(r.status_code, 200)
        for _, etiqueta in Lead.Status.choices:
            self.assertContains(r, etiqueta)

    def test_ficha_de_empresa_con_sus_inlines(self):
        r = self.client.get(f"/admin/crm/creditor/{self.empresa.pk}/change/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Paulina Cortes")


# ==========================================================================
#  Alta, edicion y baja en el panel
# ==========================================================================

class CompanyFormTest(TestCase):
    """El RUT se normaliza al guardar; si no, el unique no sirve de nada."""

    def setUp(self):
        self.rubro = Industry.objects.create(name="Gimnasios", slug="gimnasios")

    def datos(self, **extra):
        base = {
            "trade_name": "Vitalis Gym",
            "legal_name": "Vitalis Fitness SpA",
            "tax_id": "76.543.210-3",
            "industry": self.rubro.pk,
            "status": Creditor.Status.ACTIVE,
        }
        base.update(extra)
        return base

    def test_quita_los_puntos(self):
        form = CreditorForm(data=self.datos(tax_id="76.543.210-3"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["tax_id"], "76543210-3")

    def test_agrega_el_guion_si_falta(self):
        form = CreditorForm(data=self.datos(tax_id="765432103"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["tax_id"], "76543210-3")

    def test_pone_la_k_en_mayuscula(self):
        form = CreditorForm(data=self.datos(tax_id="77.812.341-k"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["tax_id"], "77812341-K")

    def test_las_tres_formas_del_mismo_rut_colisionan(self):
        """Es el punto de normalizar: que no entren duplicados disfrazados."""
        CreditorForm(data=self.datos()).save()
        for variante in ("76543210-3", "76.543.210-3", "765432103"):
            form = CreditorForm(data=self.datos(tax_id=variante, trade_name="Clon"))
            self.assertFalse(form.is_valid(), variante)
            self.assertIn("tax_id", form.errors)

    def test_rechaza_formatos_invalidos(self):
        for malo in ("123", "abc", "76543210-XY", ""):
            form = CreditorForm(data=self.datos(tax_id=malo))
            self.assertFalse(form.is_valid(), malo)

    def test_rechaza_un_digito_verificador_que_no_corresponde(self):
        """
        76.543.210-1 tiene buen formato, pero su verificador es 3. Antes entraba:
        se veia bien en el panel y lo rechazaba cualquier sistema que validara.
        """
        form = CreditorForm(data=self.datos(tax_id="76.543.210-1"))
        self.assertFalse(form.is_valid())
        self.assertIn("verificador", form.errors["tax_id"][0])

    def test_los_campos_de_ubicacion_son_opcionales(self):
        form = CreditorForm(data=self.datos())
        self.assertTrue(form.is_valid(), form.errors)

    def test_solo_ofrece_rubros_activos(self):
        Industry.objects.create(name="Retirado", slug="retirado", is_active=False)
        slugs = [r.slug for r in CreditorForm().fields["industry"].queryset]
        self.assertNotIn("retirado", slugs)


class PanelCrudTest(TestCase):

    def setUp(self):
        User.objects.create_user("operador", password="clave-larga-123")
        self.client.login(username="operador", password="clave-larga-123")
        self.rubro = Industry.objects.create(name="Gimnasios", slug="gimnasios")
        self.empresa = crear_empresa(industry=self.rubro)

    def datos_empresa(self, **extra):
        base = {
            "trade_name": "Nueva SpA",
            "legal_name": "Nueva Sociedad SpA",
            "tax_id": "77812341-K",
            "industry": self.rubro.pk,
            "status": Creditor.Status.ONBOARDING,
        }
        base.update(extra)
        return base

    # --- Alta ---

    def test_formulario_de_alta_responde(self):
        r = self.client.get(reverse("panel:cliente_nuevo"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["es_nueva"])

    def test_alta_crea_y_redirige_a_la_ficha(self):
        r = self.client.post(reverse("panel:cliente_nuevo"), self.datos_empresa())
        nueva = Creditor.objects.get(tax_id="77812341-K")
        self.assertRedirects(r, reverse("panel:cliente_detalle", args=[nueva.pk]))
        self.assertEqual(nueva.trade_name, "Nueva SpA")

    def test_alta_con_rut_repetido_no_crea(self):
        antes = Creditor.objects.count()
        r = self.client.post(
            reverse("panel:cliente_nuevo"), self.datos_empresa(tax_id="76543210-3")
        )
        self.assertEqual(r.status_code, 200)   # vuelve al formulario
        self.assertEqual(Creditor.objects.count(), antes)

    # --- Edicion ---

    def test_edicion_guarda_los_cambios(self):
        r = self.client.post(
            reverse("panel:cliente_editar", args=[self.empresa.pk]),
            self.datos_empresa(tax_id="76543210-3", trade_name="Vitalis Renovado"),
        )
        self.assertRedirects(
            r, reverse("panel:cliente_detalle", args=[self.empresa.pk])
        )
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.trade_name, "Vitalis Renovado")

    def test_editar_una_empresa_inexistente_es_404(self):
        r = self.client.get(reverse("panel:cliente_editar", args=[99999]))
        self.assertEqual(r.status_code, 404)

    # --- Baja ---

    def test_la_baja_cambia_el_estado_y_no_borra(self):
        """
        Una empresa arrastra cartera y campanas: borrarla se llevaria el
        historico. La baja es un cambio de estado.
        """
        r = self.client.post(
            reverse("panel:cliente_estado", args=[self.empresa.pk]),
            {"estado": Creditor.Status.CHURNED},
        )
        self.assertRedirects(
            r, reverse("panel:cliente_detalle", args=[self.empresa.pk])
        )
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.status, Creditor.Status.CHURNED)
        self.assertTrue(Creditor.objects.filter(pk=self.empresa.pk).exists())

    def test_un_estado_inventado_no_se_aplica(self):
        self.client.post(
            reverse("panel:cliente_estado", args=[self.empresa.pk]),
            {"estado": "no-existe"},
        )
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.status, Creditor.Status.ACTIVE)

    def test_el_cambio_de_estado_no_acepta_get(self):
        r = self.client.get(reverse("panel:cliente_estado", args=[self.empresa.pk]))
        self.assertEqual(r.status_code, 405)

    # --- Contactos ---

    def test_alta_de_contacto(self):
        r = self.client.post(
            reverse("panel:contacto_nuevo", args=[self.empresa.pk]),
            {"full_name": "Paulina Cortes", "email": "p@vitalis.cl", "is_primary": "on"},
        )
        self.assertRedirects(
            r, reverse("panel:cliente_detalle", args=[self.empresa.pk])
        )
        contacto = CreditorContact.objects.get()
        self.assertEqual(contacto.creditor, self.empresa)
        self.assertTrue(contacto.is_primary)

    def test_el_contacto_nuevo_degrada_al_principal_anterior(self):
        primero = CreditorContact.objects.create(
            creditor=self.empresa, full_name="Primero",
            email="1@v.cl", is_primary=True,
        )
        self.client.post(
            reverse("panel:contacto_nuevo", args=[self.empresa.pk]),
            {"full_name": "Segundo", "email": "2@v.cl", "is_primary": "on"},
        )
        primero.refresh_from_db()
        self.assertFalse(primero.is_primary)

    def test_edicion_de_contacto(self):
        contacto = CreditorContact.objects.create(
            creditor=self.empresa, full_name="Antes", email="a@v.cl",
        )
        self.client.post(
            reverse("panel:contacto_editar", args=[self.empresa.pk, contacto.pk]),
            {"full_name": "Despues", "email": "a@v.cl"},
        )
        contacto.refresh_from_db()
        self.assertEqual(contacto.full_name, "Despues")

    def test_no_se_puede_editar_el_contacto_de_otra_empresa(self):
        """El identificador viaja por la URL: hay que validar la pertenencia."""
        otra = crear_empresa(tax_id="99999999-9", trade_name="Otra")
        ajeno = CreditorContact.objects.create(
            creditor=otra, full_name="Ajeno", email="x@otra.cl",
        )
        r = self.client.get(
            reverse("panel:contacto_editar", args=[self.empresa.pk, ajeno.pk])
        )
        self.assertEqual(r.status_code, 404)

    def test_eliminar_contacto(self):
        contacto = CreditorContact.objects.create(
            creditor=self.empresa, full_name="Se va", email="s@v.cl",
        )
        r = self.client.post(
            reverse("panel:contacto_eliminar", args=[self.empresa.pk, contacto.pk])
        )
        self.assertRedirects(
            r, reverse("panel:cliente_detalle", args=[self.empresa.pk])
        )
        self.assertEqual(CreditorContact.objects.count(), 0)

    def test_eliminar_no_acepta_get(self):
        contacto = CreditorContact.objects.create(
            creditor=self.empresa, full_name="Se queda", email="q@v.cl",
        )
        r = self.client.get(
            reverse("panel:contacto_eliminar", args=[self.empresa.pk, contacto.pk])
        )
        self.assertEqual(r.status_code, 405)
        self.assertEqual(CreditorContact.objects.count(), 1)

    # --- Acceso ---

    def test_todas_las_rutas_de_escritura_exigen_sesion(self):
        contacto = CreditorContact.objects.create(
            creditor=self.empresa, full_name="X", email="x@v.cl",
        )
        self.client.logout()
        rutas = [
            reverse("panel:cliente_nuevo"),
            reverse("panel:cliente_editar", args=[self.empresa.pk]),
            reverse("panel:cliente_estado", args=[self.empresa.pk]),
            reverse("panel:contacto_nuevo", args=[self.empresa.pk]),
            reverse("panel:contacto_editar", args=[self.empresa.pk, contacto.pk]),
            reverse("panel:contacto_eliminar", args=[self.empresa.pk, contacto.pk]),
        ]
        for ruta in rutas:
            r = self.client.post(ruta, {})
            self.assertEqual(r.status_code, 302, ruta)
            self.assertIn(reverse("panel:login"), r.url, ruta)


class PaginacionTest(TestCase):
    """Sin tope, una base real dejaria los listados inservibles."""

    def setUp(self):
        User.objects.create_user("operador", password="clave-larga-123")
        self.client.login(username="operador", password="clave-larga-123")
        rubro = Industry.objects.create(name="Gimnasios", slug="gimnasios")
        for i in range(30):
            crear_empresa(
                industry=rubro, tax_id=f"7654321{i:02d}-1",
                trade_name=f"Empresa {i:02d}",
            )
            Lead.objects.create(
                full_name=f"Lead {i:02d}", company_name="X", email=f"{i}@x.cl",
            )

    def test_el_listado_de_clientes_pagina(self):
        c = self.client.get(reverse("panel:clientes")).context
        self.assertEqual(len(c["empresas"]), 25)
        self.assertEqual(c["total"], 30)
        self.assertTrue(c["pagina"].has_next())

    def test_segunda_pagina_de_clientes(self):
        c = self.client.get(reverse("panel:clientes"), {"pagina": 2}).context
        self.assertEqual(len(c["empresas"]), 5)
        self.assertFalse(c["pagina"].has_next())

    def test_la_paginacion_conserva_el_filtro(self):
        c = self.client.get(
            reverse("panel:clientes"), {"q": "Empresa 0", "pagina": 1}
        ).context
        self.assertEqual(c["total"], 10)   # Empresa 00 a 09

    def test_pagina_invalida_devuelve_la_ultima(self):
        """get_page no revienta con basura: entrega algo razonable."""
        c = self.client.get(reverse("panel:clientes"), {"pagina": "zzz"}).context
        self.assertEqual(c["pagina"].number, 1)

    def test_los_leads_tambien_paginan(self):
        c = self.client.get(reverse("panel:leads")).context
        self.assertEqual(len(c["leads"]), 25)
        self.assertEqual(c["total"], 30)

    def test_la_cartera_se_adjunta_solo_a_la_pagina_visible(self):
        c = self.client.get(reverse("panel:clientes")).context
        for empresa in c["empresas"]:
            self.assertTrue(hasattr(empresa, "cartera"))


MARCA_ROTA = "XXROTAXX[%s]"


def _motores_estrictos():
    """Copia de TEMPLATES que delata las variables inexistentes."""
    motores = [dict(m) for m in ajustes.TEMPLATES]
    motores[0]["OPTIONS"] = dict(motores[0]["OPTIONS"])
    motores[0]["OPTIONS"]["string_if_invalid"] = MARCA_ROTA
    return motores


@override_settings(TEMPLATES=_motores_estrictos())
class VariablesDePlantillaTest(TestCase):
    """
    Django renderiza como cadena vacia cualquier variable que no exista, asi
    que un campo renombrado no rompe nada: simplemente desaparece de la pagina.
    El renombrado de la base dejo dos accesores huerfanos
    (get_aging_bucket_display y get_current_collection_display) que las 168
    pruebas no vieron, porque ninguna compara el HTML contra los datos.

    Aca se pide cada ruta con string_if_invalid puesto, para que toda variable
    que no resuelva deje una marca y la prueba la pueda reclamar.
    """

    # Variables que legitimamente pueden no resolverse porque el dato es
    # opcional. La plantilla ya las cubre con |default, pero string_if_invalid
    # se adelanta al filtro y las marca igual, asi que hay que excusarlas.
    OPCIONALES = {"lead.industry.name"}

    def setUp(self):
        User.objects.create_user("operador", password="clave-larga-123")
        self.client.login(username="operador", password="clave-larga-123")

        rubro = Industry.objects.create(name="Gimnasios", slug="gimnasios")
        self.empresa = crear_empresa(industry=rubro)
        self.contacto = CreditorContact.objects.create(
            creditor=self.empresa, full_name="Paula Rios",
            job_title="Jefa de Cobranzas", email="paula@vitalis.cl",
            phone="+56 9 8888 7777", is_primary=True,
        )
        # Un tramo de cada clase, para que la tabla de mora los imprima todos.
        for bracket, deudores in PortfolioHandover.OverdueBracket.choices:
            PortfolioHandover.objects.create(
                creditor=self.empresa, period_month=date(2026, 8, 1),
                overdue_bracket=bracket, debtor_count=1500,
                average_debt_clp=Decimal(41300),
            )
        campana = Campaign.objects.create(
            creditor=self.empresa, name="Agosto", starts_on=date(2026, 8, 1),
            status=Campaign.Status.RUNNING, channels=["whatsapp"],
        )
        CampaignFunnelSnapshot.objects.create(
            campaign=campana, measured_on=date(2026, 8, 31),
            messages_sent=1000, messages_delivered=900, messages_opened=300,
            replies_received=120, link_clicks=60, fraud_reports=25,
            optout_requests=10, debt_disputes=4,
        )
        # Un lead con todos los campos llenos: los opcionales vacios no
        # ejercitan los accesores que interesan.
        self.lead = Lead.objects.create(
            full_name="Rosa Ibanez", job_title="Jefa de Finanzas",
            company_name="Retail Austral SpA", email="rosa@austral.cl",
            phone="+56 9 1111 2222", industry=rubro,
            estimated_debtor_count=800, estimated_overdue_clp=Decimal(45000000),
            current_collection_method=Lead.CollectionMethod.LLAMADAS,
            source=Lead.Source.FORM, inquiry_message="Necesitamos ayuda.",
        )

    def _rotas(self, respuesta):
        """Variables que la respuesta no supo resolver."""
        cuerpo = respuesta.content.decode("utf-8", "replace")
        halladas = {n for n in re.findall(r"XXROTAXX\[([^\]]*)\]", cuerpo) if n.strip()}
        return sorted(halladas - self.OPCIONALES)

    def _revisar(self, url, datos=None, estado=200):
        respuesta = self.client.post(url, datos) if datos is not None             else self.client.get(url)
        self.assertEqual(respuesta.status_code, estado)
        self.assertEqual(self._rotas(respuesta), [], f"variables rotas en {url}")
        return respuesta

    # --- Sitio publico ---

    def test_la_portada_no_deja_variables_sin_resolver(self):
        self._revisar(reverse("site:home"))

    def test_la_pagina_de_gracias_tampoco(self):
        self._revisar(reverse("site:gracias"))

    def test_la_portada_con_el_formulario_en_error_tampoco(self):
        """La rama de errores usa otro contexto que el GET no toca."""
        self._revisar(
            reverse("site:contacto"),
            {"full_name": "", "email": "no-es-correo"}, estado=400,
        )

    def test_la_pantalla_de_ingreso_tampoco(self):
        self.client.logout()
        self._revisar(reverse("panel:login"))

    # --- Panel ---

    def test_el_resumen_no_deja_variables_sin_resolver(self):
        self._revisar(reverse("panel:dashboard"))

    def test_el_listado_de_clientes_tampoco(self):
        self._revisar(reverse("panel:clientes"))
        self._revisar(reverse("panel:clientes") + "?q=vitalis&estado=active")
        self._revisar(reverse("panel:clientes") + "?estado=churned")

    def test_el_detalle_del_cliente_tampoco(self):
        """Aca vivia get_aging_bucket_display, que renderizaba vacio."""
        r = self._revisar(
            reverse("panel:cliente_detalle", args=[self.empresa.pk]))
        cuerpo = r.content.decode("utf-8")
        for _, etiqueta in PortfolioHandover.OverdueBracket.choices:
            self.assertIn(etiqueta, cuerpo)

    def test_el_listado_de_leads_tampoco(self):
        """Aca vivia get_current_collection_display, tapado por |default."""
        r = self._revisar(reverse("panel:leads"))
        self.assertIn(
            self.lead.get_current_collection_method_display(),
            r.content.decode("utf-8"),
        )
        self._revisar(reverse("panel:leads") + "?estado=new")

    def test_los_formularios_de_cliente_tampoco(self):
        self._revisar(reverse("panel:cliente_nuevo"))
        self._revisar(reverse("panel:cliente_editar", args=[self.empresa.pk]))
        self._revisar(
            reverse("panel:cliente_nuevo"),
            {"legal_name": "", "tax_id": "malo"},
        )

    def test_los_formularios_de_contacto_tampoco(self):
        self._revisar(reverse("panel:contacto_nuevo", args=[self.empresa.pk]))
        self._revisar(reverse(
            "panel:contacto_editar", args=[self.empresa.pk, self.contacto.pk]))
        self._revisar(
            reverse("panel:contacto_nuevo", args=[self.empresa.pk]),
            {"full_name": "", "email": "x"},
        )


# ==========================================================================
#  El DDL y los modelos tienen que decir lo mismo
#
#  Por que existe esta clase: el esquema real lo crea sql/AphofyxDB.sql y los
#  modelos son su espejo, pero Django arma la base de PRUEBAS desde las
#  migraciones, que no llevan ningun CHECK. Resultado: una prueba podia guardar
#  un estado que el DDL prohibe, pasar en verde, y reventar en produccion con
#  el error 3819. Paso de verdad con 'churned' contra 'terminated'.
#
#  Estas pruebas no necesitan base de datos: leen el .sql como texto.
# ==========================================================================

class EsquemaYModelosCalzan(TestCase):
    """Compara las listas de valores del DDL con las choices de los modelos."""

    #  Columna del DDL -> opciones que la aplicacion puede producir. Las
    #  categorias se guardan como ENUM, asi que la lista de valores esta en el
    #  tipo de la columna y no en un CHECK aparte.
    EQUIVALENCIAS = {
        ("crm_creditor", "status"): Creditor.Status,
        ("crm_campaign", "status"): Campaign.Status,
        ("crm_portfoliohandover", "overdue_bracket"): PortfolioHandover.OverdueBracket,
        ("crm_lead", "source"): Lead.Source,
        ("crm_lead", "status"): Lead.Status,
        ("crm_lead", "current_collection_method"): Lead.CollectionMethod,
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ddl = leer_ddl()

    def clausula(self, nombre):
        clausula = clausula_check(nombre, self.ddl)
        self.assertIsNotNone(clausula, f"El DDL no tiene el CHECK {nombre}.")
        return clausula

    def test_cada_enum_ofrece_los_mismos_valores_que_su_modelo(self):
        for (tabla, columna), opciones in self.EQUIVALENCIAS.items():
            with self.subTest(columna=f"{tabla}.{columna}"):
                en_el_ddl = valores_del_enum(tabla, columna, self.ddl)
                en_el_modelo = set(opciones.values)
                self.assertEqual(
                    en_el_ddl, en_el_modelo,
                    f"\n{tabla}.{columna} y {opciones.__qualname__} no dicen lo mismo."
                    f"\n  solo en el DDL:    {sorted(en_el_ddl - en_el_modelo)}"
                    f"\n  solo en el modelo: {sorted(en_el_modelo - en_el_ddl)}"
                    "\n  Un valor que solo esta en el modelo lo rechaza MySQL"
                    " con el error 3819 al guardar.",
                )

    def test_el_check_del_rut_acepta_el_formato_que_deja_pasar_el_formulario(self):
        """
        El formulario normaliza a '76543210-3' y la base tiene que aceptar eso
        mismo. Si el CHECK fuera mas estricto que el formulario, el panel
        guardaria y MySQL rechazaria.
        """
        patron = re.search(
            r"ck_creditor_tax_id CHECK \(\s*tax_id REGEXP '([^']+)'",
            self.ddl,
        )
        self.assertIsNotNone(patron, "El DDL no tiene el CHECK de formato del RUT.")
        regex = re.compile(patron.group(1))
        for valido in ("76543210-3", "77812341-K", "9876543-3"):
            self.assertTrue(regex.match(valido), f"{valido} deberia pasar el CHECK.")
        for invalido in ("76.543.210-3", "765432103", "76543210-XY", "abc"):
            self.assertFalse(regex.match(invalido), f"{invalido} no deberia pasar.")


class LosRutDeDemostracionSonValidos(TestCase):
    """
    El RUT es la llave con la que una empresa se identifica fuera de APOFYX.
    Un RUT de demostracion con digito verificador inventado se ve bien en el
    panel y lo rechaza cualquier sistema que valide modulo 11.
    """

    @staticmethod
    def digito_verificador(cuerpo):
        suma, factor = 0, 2
        for digito in reversed(str(cuerpo)):
            suma += int(digito) * factor
            factor = 2 if factor == 7 else factor + 1
        resto = 11 - suma % 11
        return {11: "0", 10: "K"}.get(resto, str(resto))

    def test_el_digito_verificador_del_seed_esta_bien_calculado(self):
        ddl = (ajustes.BASE_DIR / "sql" / "AphofyxDB.sql").read_text(encoding="utf-8")
        ruts = set(re.findall(r"'(\d{7,8})-([\dK])'", ddl))
        self.assertTrue(ruts, "El seed del DDL no trae ningun RUT.")
        for cuerpo, digito in sorted(ruts):
            with self.subTest(rut=f"{cuerpo}-{digito}"):
                self.assertEqual(
                    self.digito_verificador(cuerpo), digito,
                    f"{cuerpo}-{digito} no es un RUT valido: "
                    f"el digito verificador es {self.digito_verificador(cuerpo)}.",
                )
