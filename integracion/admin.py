from django.contrib import admin

from .models import ApiKey


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
