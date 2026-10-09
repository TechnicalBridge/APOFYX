"""
Modelos del CRM de APOFYX.

Los nombres describen el rol de cada cosa en el negocio, no su forma tecnica.
El caso mas importante es `Creditor`: se llamaba `Company`, y ese nombre no
distinguia nada —APOFYX tambien es una empresa—. Lo que esa tabla guarda es
**el acreedor**: quien tiene la deuda y encarga cobrarla.

Son el espejo de las tablas que crea sql/AphofyxDB.sql (ver docs seccion 14.3).

La cartera de cada acreedor (deudores, deudas y cargos) vive en la app
`cartera`, y llega por la integracion. Pagos no hay: APOFYX no procesa pagos.
Eso vive en DataBridge, en otro repositorio (docs seccion 2.2 y 13).

No hay rubros ni tipos de empresa: APOFYX cobra para cualquier empresa que
tenga cobros atrasados, y el rubro no cambia nada de como se cobra.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .campos import Categoria

DESCUENTO_FUERA_DE_RANGO = "El descuento es un porcentaje de 0 a 100."


class Creditor(models.Model):
    """
    Empresa acreedora: la que tiene deudores y contrata a APOFYX para cobrarles.

    En pantalla es "la empresa", porque asi la llama quien la atiende. En el
    codigo es acreedor, porque en este dominio hay tres empresas distintas en
    juego —APOFYX, la acreedora y DataBridge— y el nombre tiene que decir cual
    es. Puede darla de alta el personal, o registrarse sola en el portal de
    empresas; en ese caso parte "en incorporacion" hasta que el personal
    aprueba su acceso.
    """

    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "En incorporacion"
        ACTIVE = "active", "Activa"
        PAUSED = "paused", "Pausada"
        CHURNED = "churned", "Dada de baja"

    legal_name = models.CharField("razon social", max_length=160)
    trade_name = models.CharField("nombre de fantasia", max_length=120)
    tax_id = models.CharField(
        "RUT", max_length=12, unique=True,
        help_text="Normalizado, sin puntos y con guion: 76543210-3",
    )
    status = Categoria(
        "estado", max_length=20, choices=Status.choices, default=Status.ONBOARDING
    )
    client_since = models.DateField("cliente desde", blank=True, null=True)
    commune = models.CharField("comuna", max_length=80, blank=True, null=True)
    region = models.CharField("region", max_length=80, blank=True, null=True)
    website = models.URLField("sitio web", max_length=200, blank=True, null=True)
    internal_notes = models.TextField("notas internas", blank=True, null=True)
    #  Sale de la plata de la empresa: ella lo fija en su portal, no el personal.
    max_mora_discount = models.DecimalField(
        "descuento maximo sobre la mora (%)", max_digits=5, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0, DESCUENTO_FUERA_DE_RANGO), MaxValueValidator(100, DESCUENTO_FUERA_DE_RANGO)],
        help_text="El % de los intereses de mora que la empresa autoriza condonar a quien paga toda su deuda. "
                  "Vacio: ninguno.",
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        db_table = "crm_creditor"
        verbose_name = "empresa acreedora"
        verbose_name_plural = "empresas acreedoras"
        ordering = ["trade_name"]
        indexes = [
            models.Index(fields=["status"], name="ix_creditor_status"),
            models.Index(fields=["trade_name"], name="ix_creditor_trade"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_mora_discount__isnull=True)
                | models.Q(max_mora_discount__gte=0, max_mora_discount__lte=100),
                name="ck_creditor_mora_discount",
            ),
        ]

    def __str__(self):
        return self.trade_name

    @property
    def rut_formateado(self):
        """76543210-3 -> 76.543.210-3, solo para mostrar."""
        if "-" not in self.tax_id:
            return self.tax_id
        cuerpo, dv = self.tax_id.rsplit("-", 1)
        return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"

    @property
    def contacto_principal(self):
        return self.contacts.filter(is_primary=True).first()



class CreditorContact(models.Model):
    """
    Persona de contacto en la empresa acreedora.

    La base impide que existan dos contactos principales por acreedor, mediante
    una columna generada (primary_slot) con indice unico. Esa columna no se
    declara aca a proposito: MySQL la calcula sola y no admite escritura.
    El metodo save() hace cumplir la misma regla antes de llegar a la base.

    **La cuenta de la empresa es un contacto con acceso.** Quien se registra en
    el portal de empresas queda como contacto, con su usuario y el acceso por
    aprobar; el personal lo aprueba. Un contacto sin cuenta (NULL en los dos
    campos) es solo alguien a quien llamar.
    """

    class Access(models.TextChoices):
        PENDING = "pending", "Por aprobar"
        GRANTED = "granted", "Aprobado"
        REVOKED = "revoked", "Revocado"

    creditor = models.ForeignKey(
        Creditor, on_delete=models.CASCADE, related_name="contacts",
        verbose_name="acreedor", db_column="creditor_id",
    )
    full_name = models.CharField("nombre completo", max_length=120)
    job_title = models.CharField("cargo", max_length=80, blank=True, null=True)
    email = models.EmailField("correo", max_length=254)
    phone = models.CharField("telefono", max_length=20, blank=True, null=True)
    is_primary = models.BooleanField("es contacto principal", default=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="contacto",
        verbose_name="usuario del portal", db_column="user_id", blank=True, null=True,
    )
    portal_access = Categoria(
        "acceso al portal", max_length=10, choices=Access.choices, blank=True, null=True,
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        db_table = "crm_creditorcontact"
        verbose_name = "contacto del acreedor"
        verbose_name_plural = "contactos del acreedor"
        ordering = ["-is_primary", "full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["creditor", "email"], name="uq_contact_email"
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.creditor.trade_name})"

    @property
    def puede_entrar(self):
        return self.user_id is not None and self.portal_access == self.Access.GRANTED

    def save(self, *args, **kwargs):
        # Marcar este como principal degrada al anterior, en vez de chocar
        # contra el indice unico de la base con un error poco descriptivo.
        if self.is_primary:
            (
                CreditorContact.objects
                .filter(creditor=self.creditor, is_primary=True)
                .exclude(pk=self.pk)
                .update(is_primary=False)
            )
        super().save(*args, **kwargs)


class Campaign(models.Model):
    """Campana de contacto sobre la cartera de un acreedor."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        RUNNING = "running", "En curso"
        PAUSED = "paused", "Pausada"
        FINISHED = "finished", "Finalizada"

    creditor = models.ForeignKey(
        Creditor, on_delete=models.CASCADE, related_name="campaigns",
        verbose_name="acreedor", db_column="creditor_id",
    )
    name = models.CharField("nombre", max_length=120)
    starts_on = models.DateField("inicio")
    ends_on = models.DateField("termino", blank=True, null=True)
    status = Categoria(
        "estado", max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    channels = models.JSONField("canales", default=list)
    cadence_days = models.JSONField(
        "cadencia (dias)", null=True, blank=True,
        help_text="El dia en que sale cada toque, contado desde que la deuda entra. Vacia: 1, 4, 11, 25, 45.",
    )
    #  Nunca pasa el maximo que autoriza la empresa (Creditor.max_mora_discount).
    mora_discount = models.JSONField(
        "descuento por tramo", null=True, blank=True,
        help_text='El % de los intereses de mora que se condona a quien paga toda la deuda, por tramo: '
                  '{"1-30": 0, "31-90": 50, "91-120": 100}. Vacio: sin descuento.',
    )
    contact_attempts = models.PositiveSmallIntegerField(
        "intentos de contacto", default=3,
        help_text="Cuantas veces se le escribe a cada deudor durante la campana.",
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        db_table = "crm_campaign"
        verbose_name = "campana"
        verbose_name_plural = "campanas"
        ordering = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["creditor", "name"], name="uq_campaign_name"
            )
        ]

    def __str__(self):
        return self.name

    @property
    def embudo(self):
        """Suma las mediciones de la campana y calcula las tasas."""
        from django.db.models import Sum

        t = self.snapshots.aggregate(
            enviados=Sum("messages_sent"), entregados=Sum("messages_delivered"),
            abiertos=Sum("messages_opened"), respuestas=Sum("replies_received"),
            clics=Sum("link_clicks"), fraudes=Sum("fraud_reports"),
            bajas=Sum("optout_requests"),
        )
        if not t["enviados"]:
            return None

        def pct(parte, total):
            return round(100 * parte / total, 1) if total else 0

        datos = {k: v or 0 for k, v in t.items()}
        datos.update({
            "tasa_entrega": pct(datos["entregados"], datos["enviados"]),
            "tasa_apertura": pct(datos["abiertos"], datos["entregados"]),
            "tasa_clic": pct(datos["clics"], datos["abiertos"]),
        })
        return datos


class CampaignFunnelSnapshot(models.Model):
    """
    Una foto del embudo de la campana en una fecha de corte.

    Se llama "foto" y no "metrica" porque es eso: el estado acumulado del
    embudo completo en un momento, no un indicador suelto.

    Llegaba hasta los clics y se acababa: el pago ocurria fuera del producto
    (docs seccion 11.3), y la ausencia de columnas de pago era deliberada.
    Desde la integracion con DataBridge si se puede medir: el evento
    campana.avance trae los pagos y lo recuperado, y esas columnas se llenan
    solas. Las de mensajeria (entregados, abiertos, respuestas, bajas) siguen
    dependiendo del proveedor de mensajes y hoy no se miden.

    `link_clicks` ya no cuenta clics: con codigo de acceso no hay enlace que
    tocar, y lo que cuenta son los INGRESOS AL PORTAL.
    """

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="snapshots",
        verbose_name="campana", db_column="campaign_id",
    )
    measured_on = models.DateField("fecha de corte")
    messages_sent = models.PositiveIntegerField("mensajes enviados", default=0)
    messages_delivered = models.PositiveIntegerField("mensajes entregados", default=0)
    messages_opened = models.PositiveIntegerField("mensajes abiertos", default=0)
    replies_received = models.PositiveIntegerField("respuestas recibidas", default=0)
    link_clicks = models.PositiveIntegerField("ingresos al portal", default=0)
    fraud_reports = models.PositiveIntegerField("reportes de fraude", default=0)
    optout_requests = models.PositiveIntegerField("solicitudes de baja", default=0)
    debt_disputes = models.PositiveIntegerField("deudas disputadas", default=0)
    payments = models.PositiveIntegerField("pagos", default=0)
    recovered_clp = models.PositiveBigIntegerField("recuperado en pesos", default=0)
    #  Las UF no se suman con los pesos: se informan aparte.
    recovered_uf = models.DecimalField(
        "recuperado en UF", max_digits=12, decimal_places=2, default=0
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)

    class Meta:
        db_table = "crm_campaignfunnelsnapshot"
        verbose_name = "corte del embudo"
        verbose_name_plural = "cortes del embudo"
        ordering = ["-measured_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "measured_on"], name="uq_snapshot_slot"
            )
        ]

    def __str__(self):
        return f"{self.campaign.name} al {self.measured_on:%d-%m-%Y}"


class Lead(models.Model):
    """Contacto comercial entrante, del formulario del sitio o del asistente."""

    class Source(models.TextChoices):
        FORM = "form", "Formulario"
        ASSISTANT = "assistant", "Asistente"

    class Status(models.TextChoices):
        NEW = "new", "Nuevo"
        CONTACTED = "contacted", "Contactado"
        QUALIFIED = "qualified", "Calificado"
        CONVERTED = "converted", "Convertido"
        DISCARDED = "discarded", "Descartado"

    class CollectionMethod(models.TextChoices):
        """
        Como gestiona hoy su cartera. Es el dato que mas califica un lead.

        Los valores van en espanol a proposito, y eso no es un descuido del
        renombrado: por D12 los identificadores del codigo van en ingles y los
        datos en espanol. Status, Source o AnswerEngine guardan estados
        internos del sistema, asi que son ingles; esto guarda lo que el
        visitante declara sobre su propia operacion, asi que es espanol.
        Pasarlos a ingles obliga a tocar ck_lead_collection_method en el DDL
        sin que nadie gane nada.
        """
        NADIE = "nadie", "Hoy nadie la gestiona"
        LLAMADAS = "llamadas", "Llamamos por telefono"
        MENSAJES = "mensajes", "Enviamos correos o mensajes a mano"
        EXTERNO = "externo", "Una empresa de cobranza externa"
        MIXTO = "mixto", "Una mezcla de varias"

    full_name = models.CharField("nombre completo", max_length=120)
    job_title = models.CharField("cargo", max_length=80, blank=True, null=True)
    company_name = models.CharField("empresa", max_length=160)
    email = models.EmailField("correo", max_length=254)
    phone = models.CharField("telefono", max_length=20, blank=True, null=True)
    estimated_debtor_count = models.PositiveIntegerField(
        "deudores estimados", blank=True, null=True
    )
    estimated_overdue_clp = models.PositiveBigIntegerField(
        "monto moroso estimado (CLP)", blank=True, null=True
    )
    current_collection_method = Categoria(
        "como cobran hoy", max_length=20,
        choices=CollectionMethod.choices, blank=True, null=True,
    )
    source = Categoria(
        "origen", max_length=20, choices=Source.choices, default=Source.FORM
    )
    status = Categoria(
        "estado", max_length=20, choices=Status.choices, default=Status.NEW
    )
    inquiry_message = models.TextField("mensaje de la consulta", blank=True, null=True)
    conversation = models.ForeignKey(
        "assistant.Conversation", on_delete=models.SET_NULL, related_name="leads",
        verbose_name="conversacion", db_column="conversation_id",
        blank=True, null=True,
    )
    converted_creditor = models.ForeignKey(
        Creditor, on_delete=models.SET_NULL, related_name="origin_leads",
        verbose_name="acreedor creado", db_column="converted_creditor_id",
        blank=True, null=True,
    )
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        db_table = "crm_lead"
        verbose_name = "lead"
        verbose_name_plural = "leads"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} - {self.company_name}"

    def clean(self):
        """
        Un lead convertido tiene que apuntar al acreedor que se creo.

        Esta regla no se puede expresar como CHECK en MySQL: la columna ya
        participa en una clave foranea con ON DELETE SET NULL, y el motor
        rechaza la combinacion (error 3823). Por eso se valida aca.
        """
        from django.core.exceptions import ValidationError

        if self.status == self.Status.CONVERTED and self.converted_creditor_id is None:
            raise ValidationError(
                {"converted_creditor": "Un lead convertido debe apuntar al acreedor creado."}
            )
