"""Formularios del sitio publico y del panel."""

from django import forms

from .models import Creditor, CreditorContact, Industry, Lead
from .rut import es_valido, normalizar, tiene_formato


class LeadForm(forms.ModelForm):
    """
    Formulario de contacto de la landing. Graba un Lead real en MySQL: no es
    un formulario decorativo.
    """

    class Meta:
        model = Lead
        fields = [
            "full_name", "job_title",
            "company_name", "email",
            "phone", "industry",
            "estimated_debtor_count", "estimated_overdue_clp",
            "current_collection_method", "inquiry_message",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Nombre y apellido"}),
            "company_name": forms.TextInput(attrs={"placeholder": "Razon social o nombre de fantasia"}),
            "email": forms.EmailInput(attrs={"placeholder": "nombre@empresa.cl"}),
            "phone": forms.TextInput(attrs={"placeholder": "+56 9 1234 5678"}),
            "estimated_debtor_count": forms.NumberInput(attrs={"placeholder": "Cuantos deudores, aproximadamente", "min": 0}),
            "estimated_overdue_clp": forms.NumberInput(attrs={"placeholder": "Monto total en mora, en pesos", "min": 0, "step": 1000}),
            "job_title": forms.TextInput(attrs={"placeholder": "Gerente de Finanzas, Administrador..."}),
            "inquiry_message": forms.Textarea(attrs={"rows": 4, "placeholder": "Cuentenos brevemente su situacion (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["industry"].queryset = Industry.objects.filter(is_active=True)
        self.fields["industry"].empty_label = "Seleccione su rubro"
        self.fields["current_collection_method"].empty_label = "Seleccione una opcion"

        # Solo se exige lo minimo para poder responder. Los demas campos
        # califican el lead, pero pedirlos como obligatorios espanta gente.
        for opcional in ("phone", "job_title", "estimated_debtor_count",
                         "estimated_overdue_clp", "current_collection_method", "inquiry_message"):
            self.fields[opcional].required = False

        self.fields["estimated_debtor_count"].help_text = "Nos sirve para estimar su caso."
        self.fields["estimated_overdue_clp"].help_text = "Un orden de magnitud basta."
        # Clases de Bootstrap: <select> lleva form-select y el resto form-control.
        for campo in self.fields.values():
            es_select = isinstance(campo.widget, forms.Select)
            campo.widget.attrs["class"] = "form-select" if es_select else "form-control"
            if campo.required:
                campo.widget.attrs["required"] = "required"


class CreditorForm(forms.ModelForm):
    """
    Alta y edicion de empresas cliente desde el panel.

    El RUT se normaliza al guardar: sin puntos y con guion. Asi la restriccion
    de unicidad funciona de verdad; si se guardara como lo escribe cada
    persona, '76.543.210-3' y '76543210-3' serian dos empresas distintas.
    Y se comprueba el digito verificador: un RUT mal escrito se ve bien en el
    panel, pero lo rechaza cualquier sistema con el que la empresa se integre.
    """

    class Meta:
        model = Creditor
        fields = [
            "trade_name", "legal_name", "tax_id", "industry", "status",
            "client_since", "commune", "region", "website", "internal_notes",
        ]
        widgets = {
            "trade_name": forms.TextInput(attrs={"placeholder": "Como se le conoce"}),
            "legal_name": forms.TextInput(attrs={"placeholder": "Razon social completa"}),
            "tax_id": forms.TextInput(attrs={"placeholder": "76.543.210-3"}),
            "client_since": forms.DateInput(attrs={"type": "date"}),
            "website": forms.URLInput(attrs={"placeholder": "https://"}),
            "internal_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["industry"].queryset = Industry.objects.filter(is_active=True)
        for opcional in ("client_since", "commune", "region", "website", "internal_notes"):
            self.fields[opcional].required = False
        _aplicar_clases(self.fields)

    def clean_tax_id(self):
        """Deja el RUT en la forma canonica (sin puntos, con guion, K mayuscula) y valido."""
        limpio = normalizar(self.cleaned_data["tax_id"])
        if not tiene_formato(limpio):
            raise forms.ValidationError(
                "Formato no valido. Se espera algo como 76.543.210-3 o 76543210-3."
            )
        if not es_valido(limpio):
            raise forms.ValidationError(
                "El digito verificador no corresponde a ese RUT. Revisalo."
            )
        return limpio


class CreditorContactForm(forms.ModelForm):
    """Alta y edicion de contactos. La empresa la fija la vista, no el usuario."""

    class Meta:
        model = CreditorContact
        fields = ["full_name", "job_title", "email", "phone", "is_primary"]
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Nombre y apellido"}),
            "job_title": forms.TextInput(attrs={"placeholder": "Gerente de Finanzas"}),
            "phone": forms.TextInput(attrs={"placeholder": "+56 9 1234 5678"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for opcional in ("job_title", "phone"):
            self.fields[opcional].required = False
        _aplicar_clases(self.fields)


def _aplicar_clases(campos):
    """Clases de Bootstrap segun el tipo de control."""
    for campo in campos.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs["class"] = "form-check-input"
        elif isinstance(campo.widget, forms.Select):
            campo.widget.attrs["class"] = "form-select"
        else:
            campo.widget.attrs["class"] = "form-control"
        if campo.required:
            campo.widget.attrs["required"] = "required"
