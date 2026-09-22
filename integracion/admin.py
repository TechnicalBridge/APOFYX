from django.contrib import admin

from .eventos import despachar_evento
from .models import ApiKey, Forward, InboundEvent, OutboundEvent, Subscription
from .reenvio import despachar


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    """
    Las claves se emiten con `manage.py emitir_clave`, no desde aca: la clave
    se muestra una sola vez y esta pantalla no podria mostrarla, porque en la
    base solo esta su huella.
    """

    list_display = ("prefix", "creditor", "name", "created_at", "last_used_at", "revoked_at")
    list_filter = ("creditor",)
    readonly_fields = ("key_hash", "prefix", "created_at", "last_used_at")

    def has_add_permission(self, request):
        return False


@admin.register(Forward)
class ForwardAdmin(admin.ModelAdmin):
    """
    La bandeja de salida hacia DataBridge. Se mira, no se edita: el estado lo
    lleva el despachador. Lo unico que se puede hacer a mano es pedir que lo
    intente ya, sin esperar su turno.
    """

    list_display = ("external_id", "batch", "status", "attempts", "next_attempt_at",
                    "sent_at", "last_error")
    list_filter = ("status",)
    search_fields = ("external_id", "batch__external_id")
    readonly_fields = [c.name for c in Forward._meta.fields]
    actions = ["reintentar_ahora"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Intentar entregar ahora")
    def reintentar_ahora(self, request, queryset):
        resultados = [despachar(f.pk) for f in queryset.exclude(status=Forward.Status.SENT)]
        entregadas = sum(1 for f in resultados if f.status == Forward.Status.SENT)
        self.message_user(request, f"{entregadas} de {len(resultados)} entregadas a DataBridge.")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """
    Se crean con `manage.py suscribir_cliente`, que muestra el secreto una vez
    para configurarlo en el cliente. Aca no se muestra: quien tenga acceso al
    admin no necesita poder firmar eventos a nombre de APOFYX.
    """

    list_display = ("creditor", "url", "active", "created_at")
    list_filter = ("active",)
    exclude = ("secret",)
    readonly_fields = ("creditor", "url", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(InboundEvent)
class InboundEventAdmin(admin.ModelAdmin):
    """Lo que llego de DataBridge, y que le hizo cada evento a la deuda."""

    list_display = ("type", "debt", "result", "occurred_at", "received_at")
    list_filter = ("type",)
    search_fields = ("event_id", "debt__external_id")
    readonly_fields = [c.name for c in InboundEvent._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(OutboundEvent)
class OutboundEventAdmin(admin.ModelAdmin):
    """Los avisos a los clientes. Igual que los reenvios: se miran y se reintentan."""

    list_display = ("type", "subscription", "status", "attempts", "next_attempt_at",
                    "delivered_at", "last_error")
    list_filter = ("status", "type")
    search_fields = ("event_id",)
    readonly_fields = [c.name for c in OutboundEvent._meta.fields]
    actions = ["reintentar_ahora"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Intentar avisar ahora")
    def reintentar_ahora(self, request, queryset):
        resultados = [despachar_evento(e.pk) for e in queryset.exclude(status=OutboundEvent.Status.DELIVERED)]
        entregados = sum(1 for e in resultados if e.status == OutboundEvent.Status.DELIVERED)
        self.message_user(request, f"{entregados} de {len(resultados)} avisados al cliente.")
