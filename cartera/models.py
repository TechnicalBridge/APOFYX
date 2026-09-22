"""
La cartera que los acreedores le entregan a APOFYX.

POR QUE ESTA APP EXISTE
APOFYX es una empresa de cobranza: recibe la cartera morosa de sus clientes, la
valida, la prioriza y la trabaja. Sin estas tablas no tiene nada que cobrar, y
no podria operar si la plataforma de pagos estuviera caida.

Esto corrige lo que decia §2.2 del documento, escrita cuando el alcance del
repositorio era solo el sitio y el panel. Lo que sigue siendo cierto es la otra
mitad de esa frase: **aca no hay tablas de pago ni de transaccion**. El dinero
lo mueve DataBridge; a APOFYX le llega el aviso y actualiza el estado.

EL LIMITE DE LOS 120 DIAS
Pasada esa mora APOFYX devuelve el caso al acreedor (§2.2). La validacion de la
cartera lo aplica al recibir, asi que una deuda mas vieja nunca entra.

Los nombres siguen la convencion D12: identificadores en ingles, datos en
espanol. Las tablas llevan el prefijo de la app: cartera_debtor, cartera_debt.
"""

from django.core.validators import MinValueValidator
from django.db import models

from crm.campos import Categoria


class Batch(models.Model):
    """
    Una entrega de cartera: el archivo que mando el acreedor, con fecha de
    corte.

    No confundir con `crm_portfoliohandover`, que es el agregado comercial que
    el panel muestra por tramo de mora. Esto es la entrega real, con su
    contenido.

    `external_id` es el numero de lote del acreedor y es unico por acreedor:
    es lo que permite reenviar sin duplicar. `payload_hash` guarda la huella
    del contenido, para distinguir un reenvio identico (se responde lo mismo)
    de uno con el mismo id y otro contenido (se rechaza).
    """

    class Source(models.TextChoices):
        API = "api", "Por API"
        FILE = "file", "Archivo cargado a mano"

    class Status(models.TextChoices):
        RECEIVED = "received", "Recibido"
        PROCESSED = "processed", "Procesado"
        REJECTED = "rejected", "Rechazado"

    creditor = models.ForeignKey(
        "crm.Creditor", on_delete=models.PROTECT, related_name="batches",
        verbose_name="acreedor", db_column="creditor_id",
    )
    external_id = models.CharField("id del lote en el acreedor", max_length=64)
    cut_off = models.DateField("fecha de corte")
    campaign = models.ForeignKey(
        "crm.Campaign", on_delete=models.SET_NULL, related_name="batches",
        verbose_name="campana", db_column="campaign_id", blank=True, null=True,
        help_text="Se asigna despues de recibir, al armar la campana.",
    )
    source = Categoria(
        "origen", max_length=10, choices=Source.choices, default=Source.API
    )
    status = Categoria(
        "estado", max_length=20, choices=Status.choices, default=Status.RECEIVED
    )
    received_count = models.PositiveIntegerField("deudas recibidas", default=0)
    accepted_count = models.PositiveIntegerField("aceptadas", default=0)
    rejected_count = models.PositiveIntegerField("rechazadas", default=0)
    payload_hash = models.CharField("huella del contenido", max_length=64)
    response = models.JSONField(
        "respuesta entregada", default=dict, blank=True,
        help_text="Lo que se le contesto al acreedor. Un reenvio identico "
                  "recibe esto mismo en vez de procesarse de nuevo.",
    )
    received_at = models.DateTimeField("recibido", auto_now_add=True)

    class Meta:
        db_table = "cartera_batch"
        verbose_name = "entrega recibida"
        verbose_name_plural = "entregas recibidas"
        ordering = ["-cut_off", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["creditor", "external_id"], name="uq_batch_external"
            ),
        ]

    def __str__(self):
        return f"{self.external_id} ({self.creditor.trade_name})"


class Debtor(models.Model):
    """
    La persona o empresa que debe.

    Vive una sola vez por RUT aunque deba a varios acreedores: es la misma
    persona, y tratarla como dos registros distintos haria imposible saber
    cuantas veces se le esta escribiendo.

    Guardar esto convierte a APOFYX en encargado de tratamiento de datos
    personales (§15.2). Por eso el minimo indispensable: nombre, RUT y por
    donde contactarlo.
    """

    class Kind(models.TextChoices):
        PERSON = "person", "Persona"
        COMPANY = "company", "Empresa"

    tax_id = models.CharField(
        "RUT", max_length=12, unique=True,
        help_text="Normalizado, sin puntos y con guion: 16482337-7",
    )
    kind = Categoria(
        "tipo", max_length=10, choices=Kind.choices, default=Kind.PERSON
    )
    full_name = models.CharField("nombre", max_length=160)
    email = models.EmailField("correo", max_length=254, blank=True, null=True)
    phone = models.CharField("telefono", max_length=20, blank=True, null=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        db_table = "cartera_debtor"
        verbose_name = "deudor"
        verbose_name_plural = "deudores"
        ordering = ["full_name"]
        constraints = [
            # Sin correo ni telefono no hay por donde cobrarle. Es la misma
            # regla que el contrato de integracion llama 'sin_canal_contacto'.
            models.CheckConstraint(
                condition=models.Q(email__isnull=False) | models.Q(phone__isnull=False),
                name="ck_debtor_contacto",
            ),
            # El formato del RUT lo obliga la base. El digito verificador no:
            # el modulo 11 es aritmetica y no cabe en una expresion regular.
            # Eso lo valida la recepcion de cartera.
            models.CheckConstraint(
                condition=models.Q(tax_id__regex=r"^[0-9]{7,8}-[0-9K]$"),
                name="ck_debtor_tax_id",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.tax_id})"

    @property
    def canales(self):
        """Por cuantas vias se le puede escribir. Dos habilitan el doble canal."""
        return [c for c in (("correo", self.email), ("whatsapp", self.phone)) if c[1]]


class Debt(models.Model):
    """
    Lo que un deudor le debe a un acreedor, con el id que le puso el acreedor.

    `external_id` es del acreedor y no se toca nunca: es lo que permite que un
    pago vuelva hasta el contrato de arriendo que lo origino. Por eso el unico
    es (acreedor, external_id) y no incluye el lote: la misma deuda puede
    llegar en varias entregas, actualizada.
    """

    class Currency(models.TextChoices):
        CLP = "CLP", "Pesos"
        UF = "UF", "UF"

    class Status(models.TextChoices):
        OPEN = "open", "En gestion"
        REPACTED = "repacted", "En convenio de pago"
        PAID = "paid", "Pagada"
        WITHDRAWN = "withdrawn", "Retirada por el acreedor"
        DISPUTED = "disputed", "Disputada"

    creditor = models.ForeignKey(
        "crm.Creditor", on_delete=models.PROTECT, related_name="debts",
        verbose_name="acreedor", db_column="creditor_id",
    )
    debtor = models.ForeignKey(
        Debtor, on_delete=models.PROTECT, related_name="debts",
        verbose_name="deudor", db_column="debtor_id",
    )
    external_id = models.CharField("id en el acreedor", max_length=64)
    currency = Categoria(
        "moneda", max_length=3, choices=Currency.choices, default=Currency.CLP
    )
    concept = models.CharField("concepto", max_length=200)
    refs = models.JSONField(
        "referencias", default=dict, blank=True,
        help_text="Lo que se le muestra al deudor para que reconozca la deuda.",
    )
    status = Categoria(
        "estado", max_length=20, choices=Status.choices, default=Status.OPEN
    )
    first_batch = models.ForeignKey(
        Batch, on_delete=models.PROTECT, related_name="debts_opened",
        verbose_name="entrega que la trajo", db_column="first_batch_id",
    )
    last_batch = models.ForeignKey(
        Batch, on_delete=models.PROTECT, related_name="debts_updated",
        verbose_name="ultima entrega", db_column="last_batch_id",
    )
    withdrawn_reason = models.CharField(
        "motivo del retiro", max_length=30, blank=True, null=True
    )
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        db_table = "cartera_debt"
        verbose_name = "deuda"
        verbose_name_plural = "deudas"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["creditor", "external_id"], name="uq_debt_external"
            ),
        ]
        indexes = [
            models.Index(fields=["creditor", "status"], name="ix_debt_creditor_status"),
        ]

    def __str__(self):
        return f"{self.external_id} - {self.debtor.full_name}"

    @property
    def saldo(self):
        """
        Lo que se debe hoy: la suma de los cargos vigentes.

        Se calcula y no se guarda, por la misma razon de siempre: un total
        almacenado al lado de sus partes termina discrepando de ellas.
        """
        from django.db.models import Sum

        total = self.charges.aggregate(t=Sum("amount"))["t"]
        return total or 0

    def dias_mora(self, al_dia):
        """Dias entre el cargo mas antiguo y la fecha que se le pase."""
        mas_antiguo = self.charges.order_by("due_date").values_list("due_date", flat=True).first()
        return (al_dia - mas_antiguo).days if mas_antiguo else 0

    @staticmethod
    def tramo(dias):
        """Los tramos de crm_portfoliohandover, para que los numeros calcen."""
        if dias <= 30:
            return "1-30"
        if dias <= 90:
            return "31-90"
        if dias <= 120:
            return "91-120"
        return ">120"


class DebtCharge(models.Model):
    """
    Un cargo de la deuda: el mes de arriendo, la cuota, la boleta.

    El monto es lo que se debe hoy de ese cargo, no el original: cuando el
    acreedor reenvia la deuda con un saldo menor porque le pagaron en la
    oficina, los cargos se reemplazan por los nuevos.
    """

    debt = models.ForeignKey(
        Debt, on_delete=models.CASCADE, related_name="charges",
        verbose_name="deuda", db_column="debt_id",
    )
    concept = models.CharField("concepto", max_length=120)
    period = models.CharField("periodo", max_length=7, blank=True, null=True)
    amount = models.DecimalField(
        "monto", max_digits=14, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    due_date = models.DateField("vencimiento")
    created_at = models.DateTimeField("creado", auto_now_add=True)

    class Meta:
        db_table = "cartera_debtcharge"
        verbose_name = "cargo"
        verbose_name_plural = "cargos"
        ordering = ["due_date"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ck_charge_amount"),
        ]
        indexes = [
            models.Index(fields=["debt", "due_date"], name="ix_charge_debt_due"),
        ]

    def __str__(self):
        return f"{self.concept} {self.amount}"
