"""
Pruebas del asistente del sitio: normalizacion, motor de reglas, flujo
multipaso, respaldo con modelo y endpoint JSON.

Ninguna prueba llama a la API de Gemini: el respaldo se simula. Lo que se
verifica del LLM no es que responda bien —eso se probo a mano contra la API
real— sino que el motor lo use en el momento correcto y degrade sin romperse.
"""

import json
import logging
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from crm.models import Lead
from . import engine
from .models import Conversation, Intent, IntentPattern, IntentResponse, Message


def crear_intencion(slug, nombre, patrones, respuesta, **extra):
    """Intencion con sus patrones y una respuesta, como en el catalogo real."""
    intencion = Intent.objects.create(
        slug=slug, name=nombre,
        audience=extra.pop("audience", Intent.Audience.GENERAL),
        tiebreak_priority=extra.pop("tiebreak_priority", 100),
        **extra,
    )
    for texto, peso in patrones:
        IntentPattern.objects.create(intent=intencion, pattern_text=texto, match_weight=peso)
    if respuesta:
        IntentResponse.objects.create(
            intent=intencion, response_text=respuesta,
            suggested_action=extra.pop("accion", None),
        )
    return intencion


class CatalogoBase(TestCase):
    """Catalogo minimo compartido por las pruebas del motor."""

    def setUp(self):
        crear_intencion(
            "saludo", "Saludo",
            [("hola", 3.0), ("buenos dias", 3.0)],
            "Hola. Soy el asistente automatico de APOFYX.",
            tiebreak_priority=90,
        )
        crear_intencion(
            "precios_planes", "Precios",
            [("cuanto cuesta", 3.0), ("precio", 1.0)],
            "No publicamos tarifas.",
            tiebreak_priority=20,
        )
        crear_intencion(
            "es_estafa", "Es estafa",
            [("esto es estafa", 3.0), ("no conozco apofyx", 3.0), ("estafa", 1.0)],
            "Verifique con la empresa acreedora.",
            audience=Intent.Audience.DEBTOR, tiebreak_priority=10,
        )
        crear_intencion(
            "agendar_demo", "Agendar demo",
            [("quiero una demo", 3.0), ("demo", 1.0)],
            "Con gusto.",
            tiebreak_priority=10,
        )
        crear_intencion(
            "fallback", "No se entendio",
            [],
            "No estoy seguro de haber entendido.",
            tiebreak_priority=999,
        )


# ==========================================================================
#  Normalizacion
# ==========================================================================

class NormalizarTest(TestCase):

    def test_pasa_a_minusculas(self):
        self.assertEqual(engine.normalizar("HOLA Mundo"), "hola mundo")

    def test_quita_tildes_y_dieresis(self):
        self.assertEqual(engine.normalizar("¿Cuánto cuesta?"), "cuanto cuesta")
        self.assertEqual(engine.normalizar("pingüino"), "pinguino")

    def test_la_ene_pierde_la_virgulilla(self):
        """Es lo que permite que 'año' y 'ano' calcen con el mismo patron."""
        self.assertEqual(engine.normalizar("Ñuñoa"), "nunoa")

    def test_quita_signos(self):
        self.assertEqual(engine.normalizar("¡Hola!! ¿Qué tal?"), "hola que tal")

    def test_colapsa_espacios(self):
        self.assertEqual(engine.normalizar("  hola   mundo  "), "hola mundo")

    def test_conserva_numeros(self):
        self.assertEqual(engine.normalizar("son 1.800 deudores"), "son 1 800 deudores")

    def test_vacio_y_none(self):
        self.assertEqual(engine.normalizar(""), "")
        self.assertEqual(engine.normalizar(None), "")

    def test_solo_signos_queda_vacio(self):
        self.assertEqual(engine.normalizar("¿¡...!?"), "")


# ==========================================================================
#  Motor de reglas
# ==========================================================================

class PuntuacionTest(CatalogoBase):

    def test_reconoce_una_frase_exacta(self):
        resultado = engine.puntuar_intenciones("hola")
        self.assertEqual(resultado[0][0].slug, "saludo")
        self.assertEqual(resultado[0][1], 3.0)

    def test_ignora_tildes_y_mayusculas(self):
        resultado = engine.puntuar_intenciones("¿CUÁNTO CUESTA?")
        self.assertEqual(resultado[0][0].slug, "precios_planes")

    def test_los_patrones_suman(self):
        """Dos patrones de la misma intencion acumulan puntaje."""
        resultado = engine.puntuar_intenciones("esto es estafa, no conozco apofyx")
        self.assertEqual(resultado[0][0].slug, "es_estafa")
        self.assertEqual(resultado[0][1], 7.0)   # 3 + 3 + 1 de "estafa"

    def test_ordena_de_mayor_a_menor(self):
        resultado = engine.puntuar_intenciones("hola, esto es estafa")
        self.assertEqual(resultado[0][0].slug, "es_estafa")
        self.assertGreater(resultado[0][1], resultado[1][1])

    def test_a_igual_puntaje_gana_la_de_menor_prioridad(self):
        crear_intencion("empate_a", "A", [("zzz", 2.0)], "A", tiebreak_priority=50)
        crear_intencion("empate_b", "B", [("zzz", 2.0)], "B", tiebreak_priority=5)
        resultado = engine.puntuar_intenciones("zzz")
        self.assertEqual(resultado[0][0].slug, "empate_b")

    def test_el_fallback_no_compite(self):
        """Es la red de seguridad, no una intencion que se gane por puntaje."""
        IntentPattern.objects.create(
            intent=Intent.objects.get(slug="fallback"), pattern_text="hola", match_weight=9.0
        )
        resultado = engine.puntuar_intenciones("hola")
        self.assertNotIn("fallback", [i.slug for i, _ in resultado])

    def test_ignora_intenciones_desactivadas(self):
        Intent.objects.filter(slug="saludo").update(is_active=False)
        self.assertEqual(engine.puntuar_intenciones("hola"), [])

    def test_sin_coincidencias_devuelve_lista_vacia(self):
        self.assertEqual(engine.puntuar_intenciones("xyzqw"), [])

    def test_mensaje_vacio(self):
        self.assertEqual(engine.puntuar_intenciones(""), [])
        self.assertEqual(engine.puntuar_intenciones("   "), [])


class RespuestasTest(CatalogoBase):

    def test_devuelve_la_primera_activa(self):
        intencion = Intent.objects.get(slug="saludo")
        IntentResponse.objects.create(intent=intencion, response_text="Segunda", display_order=1)
        self.assertEqual(engine.respuesta_de(intencion).display_order, 0)

    def test_omite_las_desactivadas(self):
        intencion = Intent.objects.get(slug="saludo")
        IntentResponse.objects.filter(intent=intencion).update(is_active=False)
        self.assertIsNone(engine.respuesta_de(intencion))

    def test_fallback_sale_del_catalogo(self):
        _, texto, _ = engine.respuesta_fallback()
        self.assertEqual(texto, "No estoy seguro de haber entendido.")

    def test_fallback_tiene_red_propia_si_falta_en_la_base(self):
        """Si alguien borra la intencion, el motor igual responde algo."""
        Intent.objects.filter(slug="fallback").delete()
        intencion, texto, accion = engine.respuesta_fallback()
        self.assertIsNone(intencion)
        self.assertTrue(texto)
        self.assertEqual(accion, "show_menu")


# ==========================================================================
#  Flujo multipaso
# ==========================================================================

class FlujoDemoTest(TestCase):

    def recorrer(self, respuestas):
        """Avanza el flujo con una lista de respuestas y devuelve el estado."""
        estado = engine.iniciar_demo()
        ultimo = None
        for respuesta in respuestas:
            estado, texto, accion, creado = engine.avanzar_demo(estado, respuesta)
            ultimo = (estado, texto, accion, creado)
            if estado is None:
                break
        return ultimo

    def test_pregunta_de_a_uno(self):
        estado = engine.iniciar_demo()
        estado, texto, _, creado = engine.avanzar_demo(estado, "Camila Vega")
        self.assertEqual(estado["paso"], 1)
        self.assertIn("empresa", texto.lower())
        self.assertFalse(creado)

    def test_recorrido_completo_crea_el_lead(self):
        estado, texto, _, creado = self.recorrer([
            "Camila Vega", "Gimnasios Aurora", "cvega@aurora.cl", "900 deudores",
        ])
        self.assertIsNone(estado)   # el flujo termino
        self.assertTrue(creado)

        lead = Lead.objects.get()
        self.assertEqual(lead.full_name, "Camila Vega")
        self.assertEqual(lead.company_name, "Gimnasios Aurora")
        self.assertEqual(lead.email, "cvega@aurora.cl")
        self.assertEqual(lead.estimated_debtor_count, 900)
        self.assertEqual(lead.source, Lead.Source.ASSISTANT)

    def test_saluda_por_el_nombre_de_pila(self):
        _, texto, _, _ = self.recorrer([
            "Camila Vega", "Aurora", "c@a.cl", "900",
        ])
        self.assertIn("Camila", texto)

    def test_correo_invalido_no_avanza(self):
        estado = engine.iniciar_demo()
        estado, _, _, _ = engine.avanzar_demo(estado, "Camila")
        estado, _, _, _ = engine.avanzar_demo(estado, "Aurora")
        paso_antes = estado["paso"]
        estado, texto, _, _ = engine.avanzar_demo(estado, "correo-malo")

        self.assertEqual(estado["paso"], paso_antes)   # sigue en el mismo paso
        self.assertIn("correo", texto.lower())
        self.assertEqual(Lead.objects.count(), 0)

    def test_se_recupera_tras_un_correo_malo(self):
        estado, _, _, creado = self.recorrer([
            "Camila", "Aurora", "no-sirve", "cvega@aurora.cl", "900",
        ])
        self.assertTrue(creado)
        self.assertEqual(Lead.objects.get().email, "cvega@aurora.cl")

    def test_nombre_muy_corto_no_avanza(self):
        estado = engine.iniciar_demo()
        estado, texto, _, _ = engine.avanzar_demo(estado, "A")
        self.assertEqual(estado["paso"], 0)

    def test_extrae_los_digitos_del_texto_libre(self):
        self.recorrer(["Camila", "Aurora", "c@a.cl", "son como 1.800 personas"])
        self.assertEqual(Lead.objects.get().estimated_debtor_count, 1800)

    def test_sin_numero_queda_en_none(self):
        self.recorrer(["Camila", "Aurora", "c@a.cl", "no se"])
        self.assertIsNone(Lead.objects.get().estimated_debtor_count)

    def test_cancelar_corta_sin_crear_nada(self):
        estado = engine.iniciar_demo()
        estado, texto, _, creado = engine.avanzar_demo(estado, "cancelar")
        self.assertIsNone(estado)
        self.assertFalse(creado)
        self.assertEqual(Lead.objects.count(), 0)

    def test_cancelar_a_media_conversacion(self):
        estado = engine.iniciar_demo()
        estado, _, _, _ = engine.avanzar_demo(estado, "Camila")
        estado, _, _, creado = engine.avanzar_demo(estado, "olvidalo")
        self.assertIsNone(estado)
        self.assertEqual(Lead.objects.count(), 0)


# ==========================================================================
#  Respaldo con modelo
# ==========================================================================

class ContextoParaModeloTest(CatalogoBase):
    """Lo que el modelo puede decir sale del catalogo, no de su memoria."""

    def test_incluye_las_respuestas_aprobadas(self):
        contexto = engine._contexto_para_modelo()
        self.assertIn("No publicamos tarifas.", contexto)
        self.assertIn("Verifique con la empresa acreedora.", contexto)

    def test_omite_las_intenciones_desactivadas(self):
        Intent.objects.filter(slug="precios_planes").update(is_active=False)
        self.assertNotIn("No publicamos tarifas.", engine._contexto_para_modelo())


class RespaldoModeloTest(CatalogoBase):
    """
    El respaldo con Gemini, simulado.

    No se llama a la API real: lo que importa no es que el modelo responda bien
    —eso se probo a mano— sino que el motor lo invoque bien y degrade sin
    romperse cuando algo falla.
    """

    def con_clave(self):
        return patch.object(engine, "AJUSTES", {**engine.AJUSTES, "GEMINI_API_KEY": "x"})

    def silenciar_avisos(self):
        """El motor registra un aviso a proposito; aca es ruido esperado."""
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)

    def respuesta_simulada(self, texto, motivo="STOP"):
        """Imita lo que devuelve el SDK: texto mas el motivo de termino."""
        candidato = type("Candidato", (), {"finish_reason": motivo})()
        return type("Respuesta", (), {"text": texto, "candidates": [candidato]})()

    def test_sin_clave_no_intenta_nada(self):
        with patch.object(engine, "AJUSTES", {**engine.AJUSTES, "GEMINI_API_KEY": ""}), \
                patch("google.genai.Client") as cliente:
            self.assertIsNone(engine.consultar_modelo("hola"))
        cliente.assert_not_called()

    def test_respuesta_valida_se_devuelve(self):
        with self.con_clave(), patch("google.genai.Client") as Cliente:
            Cliente.return_value.models.generate_content.return_value = (
                self.respuesta_simulada("Atendemos clinicas dentales.")
            )
            self.assertEqual(
                engine.consultar_modelo("sirve para una clinica"),
                "Atendemos clinicas dentales.",
            )

    def test_descarta_la_respuesta_truncada(self):
        """
        Los modelos que razonan gastan el presupuesto pensando y devuelven una
        frase a medias. Mostrar eso es peor que no responder: se descarta y el
        motor cae en fallback.
        """
        with self.con_clave(), patch("google.genai.Client") as Cliente:
            Cliente.return_value.models.generate_content.return_value = (
                self.respuesta_simulada("').\\n\\n4. **Refining for", motivo="MAX_TOKENS")
            )
            self.silenciar_avisos()
            self.assertIsNone(engine.consultar_modelo("hola"))

    def test_respuesta_vacia_se_descarta(self):
        with self.con_clave(), patch("google.genai.Client") as Cliente:
            Cliente.return_value.models.generate_content.return_value = (
                self.respuesta_simulada("   ")
            )
            self.assertIsNone(engine.consultar_modelo("hola"))

    def test_si_la_api_falla_devuelve_none(self):
        """Un 503 o un corte de red no deben propagarse: el motor sigue."""
        self.silenciar_avisos()
        with self.con_clave(), \
                patch("google.genai.Client", side_effect=RuntimeError("503 saturado")):
            self.assertIsNone(engine.consultar_modelo("hola"))

    def test_usa_el_modelo_y_el_tiempo_de_espera_configurados(self):
        ajustes = {**engine.AJUSTES, "GEMINI_API_KEY": "x",
                   "GEMINI_MODEL": "modelo-de-prueba", "GEMINI_TIMEOUT_MS": 12000}
        with patch.object(engine, "AJUSTES", ajustes), \
                patch("google.genai.Client") as Cliente:
            Cliente.return_value.models.generate_content.return_value = (
                self.respuesta_simulada("ok")
            )
            engine.consultar_modelo("hola")

        llamada = Cliente.return_value.models.generate_content.call_args
        self.assertEqual(llamada.kwargs["model"], "modelo-de-prueba")
        # El tiempo de espera va en el cliente, no en la llamada.
        self.assertEqual(Cliente.call_args.kwargs["http_options"].timeout, 12000)


class MotorConRespaldoTest(CatalogoBase):
    """Que el motor recurra al modelo en el momento correcto, y solo ahi."""

    def responder(self, mensaje):
        sesion = self.client.session
        return engine.responder(mensaje, sesion)

    def test_si_las_reglas_alcanzan_no_llama_al_modelo(self):
        with patch.object(engine, "consultar_modelo") as simulado:
            resultado = self.responder("hola")
        simulado.assert_not_called()
        self.assertEqual(resultado["origen"], Message.AnswerEngine.RULES)
        self.assertEqual(resultado["intencion"], "saludo")

    def test_bajo_el_umbral_recurre_al_modelo(self):
        with patch.object(engine, "consultar_modelo", return_value="Respuesta del modelo") as s:
            resultado = self.responder("precio")   # puntaje 1.0, bajo el umbral 2.5
        s.assert_called_once()
        self.assertEqual(resultado["origen"], Message.AnswerEngine.LLM)
        self.assertEqual(resultado["respuesta"], "Respuesta del modelo")

    def test_si_el_modelo_falla_cae_en_fallback(self):
        with patch.object(engine, "consultar_modelo", return_value=None):
            resultado = self.responder("xyzqw sin sentido")
        self.assertEqual(resultado["origen"], Message.AnswerEngine.FALLBACK)
        self.assertEqual(resultado["respuesta"], "No estoy seguro de haber entendido.")

    def test_registra_los_dos_turnos(self):
        self.responder("hola")
        self.assertEqual(Message.objects.filter(speaker=Message.Speaker.VISITOR).count(), 1)
        self.assertEqual(Message.objects.filter(speaker=Message.Speaker.ASSISTANT).count(), 1)

    def test_guarda_el_origen_y_la_latencia(self):
        self.responder("hola")
        respuesta = Message.objects.get(speaker=Message.Speaker.ASSISTANT)
        self.assertEqual(respuesta.answer_engine, Message.AnswerEngine.RULES)
        self.assertIsNotNone(respuesta.response_time_ms)
        self.assertIsNotNone(respuesta.match_confidence)

    def test_el_mensaje_del_visitante_no_lleva_origen(self):
        """La restriccion de MySQL lo exige, y el motor lo respeta."""
        self.responder("hola")
        visitante = Message.objects.get(speaker=Message.Speaker.VISITOR)
        self.assertIsNone(visitante.answer_engine)
        self.assertIsNone(visitante.match_confidence)

    def test_infiere_el_publico(self):
        self.responder("esto es estafa")
        conversacion = Conversation.objects.get()
        self.assertEqual(conversacion.inferred_audience, Intent.Audience.DEBTOR)

    def test_agendar_demo_abre_el_flujo(self):
        sesion = self.client.session
        engine.responder("quiero una demo", sesion)
        self.assertIn("flujo_demo", sesion)
        self.assertEqual(sesion["flujo_demo"]["paso"], 0)

    def test_el_flujo_abierto_tiene_prioridad(self):
        """Estando en el flujo, 'hola' es un nombre, no un saludo."""
        sesion = self.client.session
        engine.responder("quiero una demo", sesion)
        with patch.object(engine, "puntuar_intenciones") as puntuar:
            resultado = engine.responder("Hola Perez", sesion)
        puntuar.assert_not_called()
        self.assertIn("empresa", resultado["respuesta"].lower())


# ==========================================================================
#  Endpoint JSON
# ==========================================================================

class EndpointChatTest(CatalogoBase):

    def setUp(self):
        super().setUp()
        self.url = reverse("assistant:chat")

    def hablar(self, cuerpo):
        return self.client.post(
            self.url, data=json.dumps(cuerpo), content_type="application/json"
        )

    def test_mensaje_valido(self):
        r = self.hablar({"mensaje": "hola"})
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["origen"], "rules")
        self.assertEqual(datos["intencion"], "saludo")
        self.assertIsNotNone(datos["conversacion"])

    def test_get_no_esta_permitido(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_mensaje_vacio_es_400(self):
        r = self.hablar({"mensaje": "   "})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])

    def test_falta_el_campo_mensaje(self):
        self.assertEqual(self.hablar({}).status_code, 400)

    def test_mensaje_demasiado_largo(self):
        r = self.hablar({"mensaje": "a" * 501})
        self.assertEqual(r.status_code, 400)
        self.assertIn("500", r.json()["detalle"])

    def test_cuerpo_que_no_es_json(self):
        r = self.client.post(self.url, data="{roto", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_retoma_la_conversacion(self):
        primera = self.hablar({"mensaje": "hola"}).json()
        segunda = self.hablar({
            "mensaje": "cuanto cuesta", "conversacion": primera["conversacion"]
        }).json()
        self.assertEqual(primera["conversacion"], segunda["conversacion"])
        self.assertEqual(Conversation.objects.count(), 1)

    def test_no_retoma_la_conversacion_de_otra_sesion(self):
        """
        El identificador viaja por el navegador: si no se validara contra la
        sesion, cualquiera podria leer la conversacion de otra persona.
        """
        ajena = Conversation.objects.create(session_key="otra-sesion-distinta")
        datos = self.hablar({"mensaje": "hola", "conversacion": ajena.pk}).json()
        self.assertNotEqual(datos["conversacion"], ajena.pk)
        self.assertEqual(ajena.messages.count(), 0)

    def test_conversacion_inexistente_no_revienta(self):
        datos = self.hablar({"mensaje": "hola", "conversacion": 99999}).json()
        self.assertTrue(datos["ok"])

    def test_el_flujo_de_demo_sobrevive_entre_peticiones(self):
        """La sesion es lo que permite encadenar los turnos."""
        self.hablar({"mensaje": "quiero una demo"})
        self.hablar({"mensaje": "Camila Vega"})
        self.hablar({"mensaje": "Gimnasios Aurora"})
        self.hablar({"mensaje": "cvega@aurora.cl"})
        r = self.hablar({"mensaje": "900"}).json()

        self.assertTrue(r["ok"])
        lead = Lead.objects.get()
        self.assertEqual(lead.full_name, "Camila Vega")
        self.assertEqual(lead.source, Lead.Source.ASSISTANT)

    def test_devuelve_la_accion_sugerida(self):
        intencion = Intent.objects.get(slug="precios_planes")
        IntentResponse.objects.filter(intent=intencion).update(
            suggested_action="contact_sales"
        )
        datos = self.hablar({"mensaje": "cuanto cuesta"}).json()
        self.assertEqual(datos["accion"], "contact_sales")


# ==========================================================================
#  Representacion de los modelos
# ==========================================================================

class ReprModelosTest(CatalogoBase):
    """Los __str__ salen en el admin y en los logs; conviene que no revienten."""

    def test_intencion(self):
        self.assertEqual(str(Intent.objects.get(slug="saludo")), "Saludo")

    def test_patron_muestra_el_peso(self):
        patron = IntentPattern.objects.filter(pattern_text="hola").first()
        self.assertEqual(str(patron), "hola (3.00)")

    def test_respuesta_se_recorta(self):
        respuesta = IntentResponse.objects.filter(intent__slug="saludo").first()
        self.assertTrue(str(respuesta).startswith("saludo:"))

    def test_conversacion_y_mensaje(self):
        conversacion = Conversation.objects.create(session_key="s1")
        self.assertIn(str(conversacion.pk), str(conversacion))

        mensaje = Message.objects.create(
            conversation=conversacion, speaker=Message.Speaker.VISITOR, message_text="hola",
        )
        self.assertIn("Visitante", str(mensaje))


class AdminAsistenteTest(TestCase):
    """El catalogo se edita desde el admin: las columnas deben renderizar."""

    def setUp(self):
        from django.contrib.auth.models import User

        User.objects.create_superuser("jefe", "j@apofyx.cl", "clave-larga-123")
        self.client.login(username="jefe", password="clave-larga-123")

        self.intencion = crear_intencion(
            "saludo", "Saludo", [("hola", 3.0)], "Hola, soy el asistente.",
        )
        conversacion = Conversation.objects.create(session_key="s1")
        Message.objects.create(
            conversation=conversacion, speaker=Message.Speaker.VISITOR, message_text="hola",
        )
        # Un mensaje por cada origen, para recorrer todos los colores.
        for origen in (Message.AnswerEngine.RULES, Message.AnswerEngine.LLM,
                       Message.AnswerEngine.FALLBACK):
            Message.objects.create(
                conversation=conversacion, speaker=Message.Speaker.ASSISTANT,
                message_text="respuesta " * 20, answer_engine=origen, intent=self.intencion,
            )

    def test_listados(self):
        for modelo in ("intent", "intentpattern", "intentresponse",
                       "conversation", "message"):
            r = self.client.get(f"/admin/assistant/{modelo}/")
            self.assertEqual(r.status_code, 200, modelo)

    def test_conteos_de_la_intencion(self):
        r = self.client.get("/admin/assistant/intent/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Saludo")

    def test_los_tres_origenes_se_pintan(self):
        r = self.client.get("/admin/assistant/message/")
        for _, etiqueta in Message.AnswerEngine.choices:
            self.assertContains(r, etiqueta)

    def test_mensaje_de_visitante_sin_origen_muestra_guion(self):
        r = self.client.get("/admin/assistant/message/")
        self.assertContains(r, "—")

    def test_los_textos_largos_se_recortan(self):
        r = self.client.get("/admin/assistant/message/")
        self.assertContains(r, "…")

    def test_ficha_de_intencion_con_sus_inlines(self):
        r = self.client.get(f"/admin/assistant/intent/{self.intencion.pk}/change/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "hola")
