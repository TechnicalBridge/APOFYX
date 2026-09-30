"""
Registro en el admin de Django.

Decision D10: el panel de clientes se construye a medida, y el admin nativo
queda habilitado en paralelo para carga y mantencion de datos. Aca no se busca
que sea bonito, sino que sea util para operar.
"""

from django.contrib import admin
from django.utils.html import format_html

from cartera.models import Debt

from .models import Campaign, CampaignFunnelSnapshot, Creditor, CreditorContact, Lead


class CreditorContactInline(admin.TabularInline):
    model = CreditorContact
    extra = 0
    fields = ("full_name", "job_title", "email", "phone", "is_primary", "portal_access")
    readonly_fields = ("portal_access",)


@admin.register(Creditor)
class CreditorAdmin(admin.ModelAdmin):
    list_display = ("trade_name", "rut_formateado", "status", "deudas_en_gestion", "client_since")
    list_filter = ("status", "region")
    search_fields = ("trade_name", "legal_name", "tax_id")
    date_hierarchy = "client_since"
    inlines = [CreditorContactInline]
    fieldsets = (
        ("Identificacion", {"fields": ("legal_name", "trade_name", "tax_id")}),
        ("Estado", {"fields": ("status", "client_since")}),
        ("Ubicacion y contacto", {"fields": ("commune", "region", "website")}),
        ("Interno", {"fields": ("internal_notes",), "classes": ("collapse",)}),
    )

    @admin.display(description="deudas en gestion")
    def deudas_en_gestion(self, obj):
        total = Debt.objects.filter(
            creditor=obj, status__in=(Debt.Status.OPEN, Debt.Status.REPACTED, Debt.Status.DISPUTED)
        ).count()
        return f"{total:,}".replace(",", ".") if total else "—"


@admin.register(CreditorContact)
class CreditorContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "creditor", "job_title", "email", "is_primary", "portal_access")
    list_filter = ("is_primary", "portal_access")
    search_fields = ("full_name", "email", "creditor__trade_name")
    autocomplete_fields = ("creditor",)
    #  El acceso se aprueba desde el panel, que es donde se ve quien lo pidio.
    readonly_fields = ("user", "portal_access")


class CampaignFunnelSnapshotInline(admin.TabularInline):
    model = CampaignFunnelSnapshot
    extra = 0
    fields = ("measured_on", "messages_sent", "messages_delivered",
              "messages_opened", "replies_received", "link_clicks",
              "fraud_reports", "optout_requests", "debt_disputes")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "creditor", "status", "starts_on", "ends_on",
                    "resumen_embudo")
    list_filter = ("status", "creditor")
    search_fields = ("name", "creditor__trade_name")
    autocomplete_fields = ("creditor",)
    inlines = [CampaignFunnelSnapshotInline]

    @admin.display(description="enviados / clics")
    def resumen_embudo(self, obj):
        e = obj.embudo
        if not e:
            return "sin mediciones"
        return f"{e['enviados']:,} / {e['clics']:,}".replace(",", ".")


@admin.register(CampaignFunnelSnapshot)
class CampaignFunnelSnapshotAdmin(admin.ModelAdmin):
    list_display = ("campaign", "measured_on", "messages_sent",
                    "messages_delivered", "messages_opened", "link_clicks",
                    "fraud_reports")
    list_filter = ("measured_on", "campaign__creditor")
    date_hierarchy = "measured_on"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company_name", "estado_coloreado", "source",
                    "estimated_debtor_count", "current_collection_method", "created_at")
    list_filter = ("status", "source", "current_collection_method")
    search_fields = ("full_name", "company_name", "email")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at", "conversation")
    fieldsets = (
        ("Quien escribe", {"fields": ("full_name", "job_title", "email", "phone")}),
        ("Su empresa", {"fields": ("company_name",)}),
        ("Calificacion", {
            "fields": ("estimated_debtor_count", "estimated_overdue_clp",
                       "current_collection_method"),
            "description": "Lo que permite dimensionar la oportunidad antes de llamar.",
        }),
        ("Seguimiento", {"fields": ("status", "converted_creditor", "inquiry_message")}),
        ("Origen", {"fields": ("source", "conversation", "created_at", "updated_at")}),
    )

    @admin.display(description="estado", ordering="status")
    def estado_coloreado(self, obj):
        colores = {
            Lead.Status.NEW: "#c9a961",
            Lead.Status.CONTACTED: "#4fb3c2",
            Lead.Status.QUALIFIED: "#4fb3c2",
            Lead.Status.CONVERTED: "#4caf7d",
            Lead.Status.DISCARDED: "#8a8a8a",
        }
        return format_html(
            '<b style="color: {}">{}</b>',
            colores.get(obj.status, "#888"), obj.get_status_display(),
        )
