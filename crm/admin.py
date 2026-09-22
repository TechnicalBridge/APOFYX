"""
Registro en el admin de Django.

Decision D10: el panel de clientes se construye a medida, y el admin nativo
queda habilitado en paralelo para carga y mantencion de datos. Aca no se busca
que sea bonito, sino que sea util para operar.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Campaign, CampaignFunnelSnapshot, Creditor, CreditorContact, Industry,
    Lead, PortfolioHandover,
)


class CreditorContactInline(admin.TabularInline):
    model = CreditorContact
    extra = 0
    fields = ("full_name", "job_title", "email", "phone", "is_primary")


class PortfolioHandoverInline(admin.TabularInline):
    model = PortfolioHandover
    extra = 0
    fields = ("period_month", "overdue_bracket", "debtor_count", "average_debt_clp")
    ordering = ("-period_month", "overdue_bracket")


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "total_acreedores")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="acreedores")
    def total_acreedores(self, obj):
        return obj.creditors.count()


@admin.register(Creditor)
class CreditorAdmin(admin.ModelAdmin):
    list_display = ("trade_name", "rut_formateado", "industry", "status",
                    "deudores_en_gestion", "client_since")
    list_filter = ("status", "industry", "region")
    search_fields = ("trade_name", "legal_name", "tax_id")
    date_hierarchy = "client_since"
    inlines = [CreditorContactInline, PortfolioHandoverInline]
    fieldsets = (
        ("Identificacion", {"fields": ("legal_name", "trade_name", "tax_id")}),
        ("Clasificacion", {"fields": ("industry", "status", "client_since")}),
        ("Ubicacion y contacto", {"fields": ("commune", "region", "website")}),
        ("Interno", {"fields": ("internal_notes",), "classes": ("collapse",)}),
    )

    @admin.display(description="deudores", ordering="trade_name")
    def deudores_en_gestion(self, obj):
        cartera = obj.cartera_actual
        if not cartera or not cartera["registros"]:
            return "—"
        return f"{cartera['registros']:,}".replace(",", ".")


@admin.register(CreditorContact)
class CreditorContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "creditor", "job_title", "email", "is_primary")
    list_filter = ("is_primary", "creditor__industry")
    search_fields = ("full_name", "email", "creditor__trade_name")
    autocomplete_fields = ("creditor",)


@admin.register(PortfolioHandover)
class PortfolioHandoverAdmin(admin.ModelAdmin):
    list_display = ("creditor", "period_month", "overdue_bracket",
                    "debtor_count", "average_debt_clp")
    list_filter = ("overdue_bracket", "period_month", "creditor")
    search_fields = ("creditor__trade_name",)
    autocomplete_fields = ("creditor",)


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
                    "industry", "estimated_debtor_count",
                    "current_collection_method", "created_at")
    list_filter = ("status", "source", "current_collection_method", "industry")
    search_fields = ("full_name", "company_name", "email")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at", "conversation")
    fieldsets = (
        ("Quien escribe", {"fields": ("full_name", "job_title", "email", "phone")}),
        ("Su empresa", {"fields": ("company_name", "industry")}),
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
