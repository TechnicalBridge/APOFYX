"""Formularios del sitio publico, del panel y del portal de empresas."""

import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import Campaign, Creditor, CreditorContact, Lead
from .rut import es_valido, normalizar, tiene_formato


def rut_limpio(valor):
    """El RUT en la forma canonica (sin puntos, con guion, K mayuscula), o un error que dice por que no."""
    limpio = normalizar(valor)
    if not tiene_formato(limpio):
        raise forms.ValidationError(
            "Formato no valido. Se espera algo como 76.543.210-3 o 76543210-3."
        )
    if not es_valido(limpio):
        raise forms.ValidationError(
            "El digito verificador no corresponde a ese RUT. Revisalo."
        )
    return limpio


def campo_fecha():
    """
    El selector de fecha del navegador. Solo entiende AAAA-MM-DD: con el formato
    local (29/09/2026) el campo se mostraria vacio aunque tenga valor.
    """
    return forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


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
            "phone",
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
            "trade_name", "legal_name", "tax_id", "status",
            "client_since", "commune", "region", "website", "internal_notes",
        ]
        widgets = {
            "trade_name": forms.TextInput(attrs={"placeholder": "Como se le conoce"}),
            "legal_name": forms.TextInput(attrs={"placeholder": "Razon social completa"}),
            "tax_id": forms.TextInput(attrs={"placeholder": "76.543.210-3"}),
            "client_since": campo_fecha(),
            "website": forms.URLInput(attrs={"placeholder": "https://"}),
            "internal_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for opcional in ("client_since", "commune", "region", "website", "internal_notes"):
            self.fields[opcional].required = False
        _aplicar_clases(self.fields)

    def clean_tax_id(self):
        """Deja el RUT en la forma canonica (sin puntos, con guion, K mayuscula) y valido."""
        return rut_limpio(self.cleaned_data["tax_id"])


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


class RegistroEmpresaForm(forms.Form):
    """
    Una empresa pide su cuenta en el portal: sus datos y los de quien la va a
    usar. Queda con el acceso por aprobar hasta que el personal lo revisa.
    """

    tax_id = forms.CharField(label="RUT de la empresa", max_length=14,
                             widget=forms.TextInput(attrs={"placeholder": "76.543.210-3"}))
    legal_name = forms.CharField(label="Razón social", max_length=160)
    trade_name = forms.CharField(label="Nombre de fantasía", max_length=120,
                                 help_text="El que ven sus deudores.")
    commune = forms.CharField(label="Comuna", max_length=80, required=False)
    region = forms.CharField(label="Región", max_length=80, required=False)
    website = forms.URLField(label="Sitio web", max_length=200, required=False,
                             widget=forms.URLInput(attrs={"placeholder": "https://"}))
    full_name = forms.CharField(label="Su nombre", max_length=120)
    job_title = forms.CharField(label="Cargo", max_length=80, required=False)
    email = forms.EmailField(label="Correo", max_length=254, help_text="Con él entra al portal.")
    phone = forms.CharField(label="Teléfono", max_length=20, required=False)
    password1 = forms.CharField(label="Clave", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repita la clave", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_clases(self.fields)

    def clean_tax_id(self):
        return rut_limpio(self.cleaned_data["tax_id"])

    def clean_email(self):
        correo = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(username__iexact=correo).exists():
            raise forms.ValidationError("Ese correo ya tiene una cuenta. Entre con él, o use otro.")
        return correo

    def clean(self):
        datos = super().clean()
        clave, repetida = datos.get("password1"), datos.get("password2")
        if clave and repetida and clave != repetida:
            self.add_error("password2", "Las dos claves no son iguales.")
        elif clave:
            try:
                validate_password(clave)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return datos


class EntrarEmpresaForm(AuthenticationForm):
    """
    Entrar al portal con correo y clave. Solo entra un contacto con el acceso
    aprobado: el personal de APOFYX usa el panel, no el portal.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "El correo o la clave no son correctos.",
        "en_revision": "Tu acceso está en revisión: te avisamos cuando lo aprobemos.",
        "sin_acceso": "Esa cuenta no tiene acceso al portal de empresas.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Correo"
        self.fields["username"].widget.attrs.update({"type": "email", "autocomplete": "email"})
        _aplicar_clases(self.fields)

    def clean_username(self):
        return (self.cleaned_data.get("username") or "").strip().lower()

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        contacto = getattr(user, "contacto", None)
        if contacto is None or contacto.portal_access == CreditorContact.Access.REVOKED:
            raise forms.ValidationError(self.error_messages["sin_acceso"], code="sin_acceso")
        if contacto.portal_access != CreditorContact.Access.GRANTED:
            raise forms.ValidationError(self.error_messages["en_revision"], code="en_revision")


class CampanaForm(forms.ModelForm):
    """
    Una campaña nueva sobre la cartera de una empresa. La empresa la fija la vista.

    La plataforma de pagos la ejecuta: manda cada toque el día que dice la
    cadencia, hasta los intentos, y solo por correo, que es lo que tiene
    conectado. WhatsApp y SMS vuelven al formulario cuando se puedan enviar.
    """

    CANALES = [("email", "Correo")]
    channels = forms.MultipleChoiceField(label="Canales", choices=CANALES,
                                         widget=forms.CheckboxSelectMultiple)
    cadencia = forms.CharField(
        label="Cadencia (días)", required=False,
        widget=forms.TextInput(attrs={"placeholder": "1, 4, 11, 25, 45"}),
        help_text="El día en que sale cada correo, contado desde que la deuda entra a la campaña. "
                  "Vacía: 1, 4, 11, 25 y 45.",
    )
    field_order = ["name", "starts_on", "ends_on", "status", "channels", "contact_attempts", "cadencia"]

    #  La Ley 19.496 (art. 37) deja escribirle a un deudor a lo mas dos veces por
    #  semana, con dos dias entre una y otra. La plataforma lo respeta igual, pero
    #  una cadencia mas seguida no se va a cumplir como esta escrita.
    ADVERTENCIA_LEY = ("Algunos toques van con menos de dos días entre uno y otro. La ley deja escribirle a un "
                       "deudor a lo más dos veces por semana y con dos días entre una y otra: esos correos "
                       "saldrán en cuanto se pueda.")

    class Meta:
        model = Campaign
        fields = ["name", "starts_on", "ends_on", "status", "channels", "contact_attempts"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Arriendos octubre 2026"}),
            "starts_on": campo_fecha(),
            "ends_on": campo_fecha(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ends_on"].required = False
        if not self.is_bound and self.instance.pk is None:
            self.initial.setdefault("starts_on", timezone.localdate())
            self.initial.setdefault("status", Campaign.Status.RUNNING)
            self.initial.setdefault("channels", ["email"])
        if self.instance.cadence_days:
            self.initial.setdefault("cadencia", ", ".join(str(d) for d in self.instance.cadence_days))
        _aplicar_clases({n: c for n, c in self.fields.items() if n != "channels"})

    def clean_cadencia(self):
        texto = (self.cleaned_data.get("cadencia") or "").strip()
        if not texto:
            return None
        try:
            dias = [int(d) for d in re.split(r"[,;\s]+", texto) if d]
        except ValueError:
            raise forms.ValidationError("Escribe los días como números separados por coma: 1, 4, 11.")
        if any(d < 0 for d in dias) or dias != sorted(set(dias)):
            raise forms.ValidationError("Los días van de menor a mayor y sin repetirse: 1, 4, 11.")
        if len(dias) > 10:
            raise forms.ValidationError("Una campaña tiene a lo más 10 toques.")
        return dias

    @property
    def advertencia(self):
        """Si la cadencia (o la de siempre, si va vacia) pide toques mas seguidos de lo que deja la ley."""
        dias = self.cleaned_data.get("cadencia") or [1, 4, 11, 25, 45]
        return self.ADVERTENCIA_LEY if any(b - a < 2 for a, b in zip(dias, dias[1:])) else None

    def save(self, commit=True):
        self.instance.cadence_days = self.cleaned_data.get("cadencia")
        return super().save(commit)

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("starts_on"), datos.get("ends_on")
        if inicio and fin and fin < inicio:
            self.add_error("ends_on", "La campaña no puede terminar antes de empezar.")
        cadencia, intentos = datos.get("cadencia"), datos.get("contact_attempts")
        if cadencia and intentos and len(cadencia) < intentos:
            self.add_error("cadencia", f"Con {intentos} intentos, la cadencia necesita {intentos} días.")
        return datos


class ConexionPlataformaForm(forms.Form):
    """La dirección y la clave que la plataforma de pagos le emitió a APOFYX."""

    url = forms.URLField(label="Dirección de la plataforma", max_length=300,
                         widget=forms.URLInput(attrs={"placeholder": "http://host.docker.internal:8080"}),
                         help_text="Tal como la ve APOFYX. Si APOFYX corre en Docker, «localhost» es su propio "
                                   "contenedor: el equipo es host.docker.internal.")
    api_key = forms.CharField(label="Clave de API", max_length=120,
                              widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
                              help_text="La que la plataforma le emitió a APOFYX. No se vuelve a mostrar.")
    url_avisos = forms.URLField(label="Dónde recibe APOFYX los avisos de pago", max_length=300,
                                help_text="La dirección de /api/v1/eventos de APOFYX, tal como la ve la plataforma.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _aplicar_clases(self.fields)


class SubirCarteraForm(forms.Form):
    """La planilla del contrato (Cartera v1, variante CSV) y los datos del lote."""

    archivo = forms.FileField(label="Planilla CSV", help_text="Separada por punto y coma, como la guarda Excel.")
    fecha_corte = forms.DateField(label="Fecha de corte", widget=campo_fecha())
    lote_id_externo = forms.CharField(label="Número del lote", max_length=60, required=False,
                                      help_text="Sin indicar, se arma con la fecha de corte: CSV-2026-09-30-1.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("fecha_corte", timezone.localdate())
        _aplicar_clases(self.fields)

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("La planilla pesa más de 5 MB: divídala en varios lotes.")
        return archivo


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
