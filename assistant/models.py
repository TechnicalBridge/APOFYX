"""
Modelos del asistente del sitio.

Todo el conocimiento del chatbot vive aca, en la base, editable desde el
panel: intenciones, patrones que las disparan y respuestas aprobadas.
Ninguna respuesta se genera con IA (docs seccion 9.3).

Los campos que antes se llamaban `text`, `source` o `weight` ahora dicen de
que texto, de que fuente y de que peso se trata: habia tres tablas con un
campo `text` y no se distinguian entre si.

Ojo: este es el asistente de apofyx.cl, que orienta a quien visita el sitio.
La tecnologia conversacional la aporta DataBridge (docs seccion 13.2); APOFYX
solo la integra. No confundirlo con el agente que habla con el deudor sobre su
deuda, que vive en el portal del cliente.
"""

from django.db import models


class Intent(models.Model):
    """Una intencion reconocible: 'precios_planes', 'es_estafa', etc."""

    class Audience(models.TextChoices):
        PROSPECT = "prospect", "Empresa interesada"
        DEBTOR = "debtor", "Persona con deuda"
        GENERAL = "general", "General"

    slug = models.SlugField("identificador", max_length=60, unique=True)
    name = models.CharField("nombre", max_length=120)
    audience = models.CharField(
        "publico", max_length=20, choices=Audience.choices, default=Audience.GENERAL
    )
    description = models.CharField("descripcion", max_length=255, blank=True, null=True)
    tiebreak_priority = models.SmallIntegerField(
        "prioridad de desempate", default=100,
        help_text="Decide cuando dos intenciones puntuan igual. Menor gana.",
    )
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        db_table = "assistant_intent"
        verbose_name = "intencion"
        verbose_name_plural = "intenciones"
        ordering = ["audience", "tiebreak_priority", "slug"]

    def __str__(self):
        return self.name


class IntentPattern(models.Model):
    """
    Frase o palabra clave que dispara una intencion.

    Se guarda YA NORMALIZADA: minusculas, sin tildes y sin puntuacion. Asi la
    comparacion no depende de como escriba el visitante.
    """

    intent = models.ForeignKey(
        Intent, on_delete=models.CASCADE, related_name="patterns",
        verbose_name="intencion", db_column="intent_id",
    )
    pattern_text = models.CharField(
        "patron", max_length=200,
        help_text="Sin tildes ni signos. Ej: 'cuanto cuesta'",
    )
    match_weight = models.DecimalField(
        "peso de coincidencia", max_digits=4, decimal_places=2, default=1,
        help_text="3.00 frase completa - 2.00 frase parcial - 1.00 palabra suelta",
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)

    class Meta:
        db_table = "assistant_intentpattern"
        verbose_name = "patron"
        verbose_name_plural = "patrones"
        ordering = ["-match_weight", "pattern_text"]
        constraints = [
            models.UniqueConstraint(
                fields=["intent", "pattern_text"], name="uq_pattern_text"
            )
        ]

    def __str__(self):
        return f"{self.pattern_text} ({self.match_weight})"


class IntentResponse(models.Model):
    """
    Respuesta aprobada para una intencion.

    Precios, plazos y tratamiento de datos son declaraciones comerciales y
    legales de la empresa: salen de aqui, revisadas, y no se generan.
    """

    intent = models.ForeignKey(
        Intent, on_delete=models.CASCADE, related_name="responses",
        verbose_name="intencion", db_column="intent_id",
    )
    response_text = models.TextField("texto de la respuesta")
    display_order = models.SmallIntegerField("orden de presentacion", default=0)
    suggested_action = models.CharField(
        "accion sugerida", max_length=40, blank=True, null=True,
        help_text="Lo que la interfaz ofrece junto al texto: show_plans, "
                  "schedule_demo, verify_with_creditor, show_menu...",
    )
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        db_table = "assistant_intentresponse"
        verbose_name = "respuesta"
        verbose_name_plural = "respuestas"
        ordering = ["intent", "display_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["intent", "display_order"], name="uq_response_slot"
            )
        ]

    def __str__(self):
        return f"{self.intent.slug}: {self.response_text[:60]}"


class Conversation(models.Model):
    """
    Una sesion de chat en el sitio.

    No hay relacion con usuario: el visitante es anonimo. session_key es un
    identificador que genera el navegador, no identifica a una persona.
    """

    session_key = models.CharField("sesion", max_length=64, db_index=True)
    inferred_audience = models.CharField(
        "publico inferido", max_length=20,
        choices=Intent.Audience.choices, blank=True, null=True,
    )
    is_resolved = models.BooleanField("resuelta", default=False)
    started_at = models.DateTimeField("inicio", auto_now_add=True)
    last_activity_at = models.DateTimeField("ultima actividad", auto_now=True)
    user_agent = models.CharField("navegador", max_length=255, blank=True, null=True)

    class Meta:
        db_table = "assistant_conversation"
        verbose_name = "conversacion"
        verbose_name_plural = "conversaciones"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Conversacion {self.pk} ({self.started_at:%d-%m-%Y %H:%M})"


class Message(models.Model):
    """
    Un turno de la conversacion.

    `answer_engine` es el campo que importa para la defensa: dice que motor
    resolvio la respuesta —el catalogo de reglas, el modelo de lenguaje o el
    respaldo—. Con eso se puede medir que tan completo esta el catalogo
    (docs seccion 9.3).
    """

    class Speaker(models.TextChoices):
        VISITOR = "visitor", "Visitante"
        ASSISTANT = "assistant", "Asistente"

    class AnswerEngine(models.TextChoices):
        RULES = "rules", "Catalogo de reglas"
        LLM = "llm", "Modelo de lenguaje"
        FALLBACK = "fallback", "Respuesta de respaldo"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages",
        verbose_name="conversacion", db_column="conversation_id",
    )
    speaker = models.CharField("quien habla", max_length=10, choices=Speaker.choices)
    message_text = models.TextField("texto del mensaje")
    intent = models.ForeignKey(
        Intent, on_delete=models.SET_NULL, related_name="messages",
        verbose_name="intencion detectada", db_column="intent_id",
        blank=True, null=True,
    )
    match_confidence = models.DecimalField(
        "confianza de la coincidencia", max_digits=5, decimal_places=4,
        blank=True, null=True,
    )
    answer_engine = models.CharField(
        "motor que respondio", max_length=10,
        choices=AnswerEngine.choices, blank=True, null=True,
    )
    response_time_ms = models.PositiveIntegerField(
        "tiempo de respuesta (ms)", blank=True, null=True
    )
    created_at = models.DateTimeField("enviado", auto_now_add=True)

    class Meta:
        db_table = "assistant_message"
        verbose_name = "mensaje"
        verbose_name_plural = "mensajes"
        ordering = ["conversation", "created_at"]

    def __str__(self):
        return f"[{self.get_speaker_display()}] {self.message_text[:60]}"
