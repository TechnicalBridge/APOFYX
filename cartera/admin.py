from django.contrib import admin

from .models import Batch, Debt, DebtCharge, Debtor


class CargoInline(admin.TabularInline):
    model = DebtCharge
    extra = 0
    fields = ("concept", "period", "amount", "due_date")


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("external_id", "creditor", "cut_off", "status",
                    "received_count", "accepted_count", "rejected_count")
    list_filter = ("status", "source", "creditor")
    search_fields = ("external_id",)
    date_hierarchy = "cut_off"
    # Una entrega es un hecho ocurrido: se consulta, no se edita.
    readonly_fields = [c.name for c in Batch._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(Debtor)
class DebtorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "tax_id", "kind", "email", "phone")
    list_filter = ("kind",)
    search_fields = ("full_name", "tax_id", "email")


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ("external_id", "debtor", "creditor", "currency", "status", "updated_at")
    list_filter = ("status", "currency", "creditor")
    search_fields = ("external_id", "debtor__full_name", "debtor__tax_id")
    inlines = [CargoInline]
    raw_id_fields = ("debtor", "first_batch", "last_batch")
