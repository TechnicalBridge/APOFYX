"""
Registro en el admin del catalogo del asistente.

Aca es donde se edita lo que el asistente sabe responder, sin tocar codigo:
intenciones, los patrones que las disparan y las respuestas aprobadas.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Conversation, Intent, IntentPattern, IntentResponse, Message


class IntentPatternInline(admin.TabularInline):
    model = IntentPattern
    extra = 1
    fields = ("pattern_text", "match_weight")
    verbose_name_plural = "Patrones (sin tildes ni signos, ya normalizados)"


class IntentResponseInline(admin.StackedInline):
    model = IntentResponse
    extra = 1
    fields = ("response_text", "display_order", "suggested_action", "is_active")


@admin.register(Intent)
class IntentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "audience", "tiebreak_priority", "is_active",
                    "total_patrones", "total_respuestas")
    list_filter = ("audience", "is_active")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [IntentPatternInline, IntentResponseInline]

    @admin.display(description="patrones")
    def total_patrones(self, obj):
        return obj.patterns.count()

    @admin.display(description="respuestas")
    def total_respuestas(self, obj):
        return obj.responses.count()


@admin.register(IntentPattern)
class IntentPatternAdmin(admin.ModelAdmin):
    list_display = ("pattern_text", "intent", "match_weight")
    list_filter = ("intent__audience", "intent")
    search_fields = ("pattern_text",)
    autocomplete_fields = ("intent",)


@admin.register(IntentResponse)
class IntentResponseAdmin(admin.ModelAdmin):
    list_display = ("intent", "recorte", "suggested_action", "is_active")
    list_filter = ("is_active", "suggested_action", "intent__audience")
    search_fields = ("response_text", "intent__name")
    autocomplete_fields = ("intent",)

    @admin.display(description="respuesta")
    def recorte(self, obj):
        return obj.response_text[:90] + ("…" if len(obj.response_text) > 90 else "")


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    readonly_fields = ("speaker", "message_text", "intent", "match_confidence",
                       "answer_engine", "response_time_ms", "created_at")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        # El historial es un registro de lo que paso: no se escribe a mano.
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "started_at", "inferred_audience", "total_mensajes",
                    "is_resolved")
    list_filter = ("inferred_audience", "is_resolved", "started_at")
    date_hierarchy = "started_at"
    readonly_fields = ("session_key", "started_at", "last_activity_at", "user_agent")
    inlines = [MessageInline]

    @admin.display(description="mensajes")
    def total_mensajes(self, obj):
        return obj.messages.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "conversation", "speaker", "recorte",
                    "intent", "motor_coloreado", "match_confidence")
    list_filter = ("speaker", "answer_engine", "intent__audience")
    search_fields = ("message_text",)
    date_hierarchy = "created_at"
    readonly_fields = ("conversation", "speaker", "message_text", "intent",
                       "match_confidence", "answer_engine", "response_time_ms",
                       "created_at")

    @admin.display(description="texto")
    def recorte(self, obj):
        return obj.message_text[:70] + ("…" if len(obj.message_text) > 70 else "")

    @admin.display(description="motor", ordering="answer_engine")
    def motor_coloreado(self, obj):
        """
        De un vistazo se ve que motor resolvio cada respuesta. Es la metrica
        que dice si el catalogo de intenciones esta completo (docs §9.3).
        """
        if not obj.answer_engine:
            return "—"
        colores = {
            Message.AnswerEngine.RULES: "#4caf7d",
            Message.AnswerEngine.LLM: "#4fb3c2",
            Message.AnswerEngine.FALLBACK: "#c9a961",
        }
        return format_html(
            '<b style="color: {}">{}</b>',
            colores.get(obj.answer_engine, "#888"),
            obj.get_answer_engine_display(),
        )
