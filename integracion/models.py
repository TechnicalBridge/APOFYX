"""
El borde de APOFYX: por donde entra la cartera de sus clientes y por donde
sale hacia DataBridge.

Esta app esta aislada a proposito de `crm` y de `cartera`. Es la unica que sabe
como se habla con afuera, asi que el dia que el contrato cambie de version, lo
que se toca es esto y no el resto del sistema.

Apagada por defecto: sin claves emitidas, nadie puede enviar nada y APOFYX
sigue funcionando con la carga a mano del panel.
"""

import hashlib
import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone


class ApiKey(models.Model):
    """
    La credencial con la que un acreedor entrega su cartera.

    No se guarda la clave, se guarda su huella SHA-256. Si alguien se lleva
    esta tabla no se lleva las claves, y APOFYX tampoco puede recordarsela a
    nadie: si se pierde, se emite otra. `prefix` existe para poder decir cual
    es sin revelarla.
    """

    creditor = models.ForeignKey(
        "crm.Creditor", on_delete=models.CASCADE, related_name="api_keys",
        verbose_name="acreedor", db_column="creditor_id",
    )
    name = models.CharField("nombre", max_length=80, help_text="Para que se emitio.")
    key_hash = models.CharField("huella de la clave", max_length=64, unique=True)
    prefix = models.CharField("prefijo visible", max_length=12)
    created_at = models.DateTimeField("emitida", auto_now_add=True)
    last_used_at = models.DateTimeField("ultimo uso", blank=True, null=True)
    revoked_at = models.DateTimeField("revocada", blank=True, null=True)

    class Meta:
        db_table = "integracion_apikey"
        verbose_name = "clave de API"
        verbose_name_plural = "claves de API"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["key_hash"], name="ix_apikey_hash"),
        ]

    def __str__(self):
        estado = "revocada" if self.revoked_at else "vigente"
        return f"{self.prefix}… {self.creditor.trade_name} ({estado})"

    @property
    def vigente(self):
        return self.revoked_at is None

    @staticmethod
    def huella(clave):
        return hashlib.sha256((clave or "").encode("utf-8")).hexdigest()

    @classmethod
    def emitir(cls, creditor, name):
        """
        Crea la clave y la devuelve UNA sola vez, junto al registro.

        El llamador tiene que mostrarla en ese momento: despues ya no existe en
        ninguna parte.
        """
        clave = f"apx_{secrets.token_urlsafe(32)}"
        registro = cls.objects.create(
            creditor=creditor, name=name,
            key_hash=cls.huella(clave), prefix=clave[:12],
        )
        return clave, registro

    @classmethod
    def autenticar(cls, clave):
        """El acreedor dueno de la clave, o None si no sirve."""
        if not clave:
            return None
        registro = cls.objects.filter(
            key_hash=cls.huella(clave), revoked_at__isnull=True
        ).select_related("creditor").first()
        if registro is None:
            return None
        # Sirve para detectar claves olvidadas y para saber si un cliente dejo
        # de enviar; se escribe sin tocar updated_at de nada mas.
        cls.objects.filter(pk=registro.pk).update(last_used_at=timezone.now())
        return registro


class Forward(models.Model):
    """
    Una cartera por pasarle a DataBridge: la bandeja de salida.

    POR QUE NO SE MANDA Y LISTO
    Si el reenvio ocurriera dentro de la misma operacion que recibe la cartera
    del cliente, una caida de DataBridge haria fallar la recepcion, y el
    cliente veria un error por algo que no es suyo. Aca la recepcion termina
    bien, el reenvio queda anotado en la misma transaccion, y sale cuando
    DataBridge responda. Si no responde, se reintenta.

    Una fila por entrega recibida. `external_id` es el numero con que APOFYX
    le presenta ese lote a DataBridge: cada emisor numera los suyos, y el de
    Patrimonio no sirve porque el emisor ahora es APOFYX.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Por enviar"
        WAITING_CAMPAIGN = "waiting", "Esperando campana"
        SENT = "sent", "Entregada"
        FAILED = "failed", "Fallida"

    # 1 min, 5, 30, 2 h, 6 h y 24 h. Despues queda para reenvio a mano.
    ESPERAS = [
        timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30),
        timedelta(hours=2), timedelta(hours=6), timedelta(hours=24),
    ]

    batch = models.OneToOneField(
        "cartera.Batch", on_delete=models.CASCADE, related_name="forward",
        verbose_name="entrega recibida", db_column="batch_id",
    )
    external_id = models.CharField("id del lote hacia DataBridge", max_length=64, unique=True)
    status = models.CharField(
        "estado", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveSmallIntegerField("intentos", default=0)
    next_attempt_at = models.DateTimeField("proximo intento", default=timezone.now)
    sent_at = models.DateTimeField("entregada", blank=True, null=True)
    last_error = models.CharField("ultimo error", max_length=300, blank=True, null=True)
    response = models.JSONField("respuesta de DataBridge", default=dict, blank=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        db_table = "integracion_forward"
        verbose_name = "reenvio a DataBridge"
        verbose_name_plural = "reenvios a DataBridge"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "waiting", "sent", "failed"]),
                name="ck_forward_status",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="ix_forward_por_enviar"),
        ]

    def __str__(self):
        return f"{self.external_id} ({self.get_status_display()})"

    def entregada(self, respuesta):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.response = respuesta
        self.last_error = None

    def fallo(self, motivo):
        """Programa el proximo intento, o se rinde despues del ultimo."""
        self.attempts += 1
        self.last_error = (motivo or "")[:300]
        if self.attempts >= len(self.ESPERAS):
            self.status = self.Status.FAILED
            return
        self.status = self.Status.PENDING
        self.next_attempt_at = timezone.now() + self.ESPERAS[self.attempts - 1]
