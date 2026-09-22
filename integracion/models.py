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

from crm.campos import Categoria
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


# 1 min, 5, 30, 2 h, 6 h y 24 h. Despues queda para reenvio a mano. Son las
# mismas del contrato (seccion 8.1) y las mismas que usa DataBridge.
ESPERAS = [
    timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30),
    timedelta(hours=2), timedelta(hours=6), timedelta(hours=24),
]


def _reintentar(fila, motivo):
    """Programa el proximo intento de una bandeja, o se rinde despues del ultimo."""
    fila.attempts += 1
    fila.last_error = (motivo or "")[:300]
    if fila.attempts >= len(ESPERAS):
        fila.status = fila.Status.FAILED
        return
    fila.status = fila.Status.PENDING
    fila.next_attempt_at = timezone.now() + ESPERAS[fila.attempts - 1]


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

    ESPERAS = ESPERAS

    batch = models.OneToOneField(
        "cartera.Batch", on_delete=models.CASCADE, related_name="forward",
        verbose_name="entrega recibida", db_column="batch_id",
    )
    external_id = models.CharField("id del lote hacia DataBridge", max_length=64, unique=True)
    status = Categoria(
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
        _reintentar(self, motivo)


# ==========================================================================
#  Eventos de vuelta: DataBridge -> APOFYX -> el cliente
# ==========================================================================

class Subscription(models.Model):
    """
    A donde APOFYX le avisa a un cliente lo que pasa con su cartera.

    El cliente da una URL y APOFYX le entrega un secreto. Con ese secreto se
    firma cada aviso, y el cliente descarta lo que no calce. Es el mismo
    contrato con que DataBridge le avisa a APOFYX, un tramo mas arriba.

    El secreto se guarda en claro porque hay que FIRMAR con el, no
    compararlo: una huella no sirve para firmar. Por eso no se muestra en el
    admin despues de emitirlo.
    """

    creditor = models.ForeignKey(
        "crm.Creditor", on_delete=models.CASCADE, related_name="subscriptions",
        verbose_name="acreedor", db_column="creditor_id",
    )
    url = models.CharField("URL", max_length=300)
    secret = models.CharField("secreto", max_length=120)
    events = models.JSONField("eventos", default=list, blank=True, help_text="Vacio = todos.")
    active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        db_table = "integracion_subscription"
        verbose_name = "suscripcion de un cliente"
        verbose_name_plural = "suscripciones de clientes"
        constraints = [
            models.UniqueConstraint(fields=["creditor", "url"], name="uq_subscription_url"),
        ]

    def __str__(self):
        return f"{self.creditor} -> {self.url}"

    @classmethod
    def registrar(cls, creditor, url, eventos=None):
        """
        Crea la suscripcion o reactiva la existente. Registrar la misma URL otra
        vez devuelve el mismo secreto: no invalida lo que el cliente ya tiene.
        """
        suscripcion, _ = cls.objects.get_or_create(
            creditor=creditor, url=url,
            defaults={"secret": "whsec_" + secrets.token_urlsafe(32)},
        )
        suscripcion.events = list(eventos or [])
        suscripcion.active = True
        suscripcion.save(update_fields=["events", "active"])
        return suscripcion

    def quiere(self, tipo):
        return not self.events or tipo in self.events


class InboundEvent(models.Model):
    """
    Un evento que llego de DataBridge.

    Se guarda siempre, lo entienda APOFYX o no: es el rastro de por que una
    deuda cambio de estado. El id del evento deduplica, porque la entrega es
    "al menos una vez" y el mismo aviso puede llegar dos veces.
    """

    event_id = models.CharField("id del evento", max_length=64, unique=True)
    type = models.CharField("tipo", max_length=30)
    occurred_at = models.DateTimeField("ocurrido", blank=True, null=True)
    debt = models.ForeignKey(
        "cartera.Debt", on_delete=models.SET_NULL, related_name="events",
        verbose_name="deuda", db_column="debt_id", blank=True, null=True,
    )
    payload = models.JSONField("evento recibido")
    result = models.CharField("resultado", max_length=80)
    received_at = models.DateTimeField("recibido", auto_now_add=True)

    class Meta:
        db_table = "integracion_inboundevent"
        verbose_name = "evento recibido"
        verbose_name_plural = "eventos recibidos"
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.type} {self.event_id}"


class OutboundEvent(models.Model):
    """
    Un evento por avisarle a un cliente: la segunda bandeja de salida.

    Nace de un evento recibido, con id propio y el lote del cliente en vez del
    de APOFYX. Se escribe en la misma transaccion que recibe, asi que si el
    cliente esta caido el evento igual queda y sale cuando responda.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Por enviar"
        DELIVERED = "delivered", "Entregado"
        FAILED = "failed", "Fallido"

    ESPERAS = ESPERAS

    event_id = models.CharField("id del evento", max_length=64)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="deliveries",
        verbose_name="suscripcion", db_column="subscription_id",
    )
    origin = models.ForeignKey(
        InboundEvent, on_delete=models.SET_NULL, related_name="forwards",
        verbose_name="evento de origen", db_column="origin_id", blank=True, null=True,
    )
    type = models.CharField("tipo", max_length=30)
    payload = models.JSONField("evento")
    status = Categoria(
        "estado", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveSmallIntegerField("intentos", default=0)
    next_attempt_at = models.DateTimeField("proximo intento", default=timezone.now)
    delivered_at = models.DateTimeField("entregado", blank=True, null=True)
    last_error = models.CharField("ultimo error", max_length=300, blank=True, null=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)

    class Meta:
        db_table = "integracion_outboundevent"
        verbose_name = "evento por avisar"
        verbose_name_plural = "eventos por avisar"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["event_id", "subscription"], name="uq_outboundevent"),
        ]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="ix_outboundevent_por_enviar"),
        ]

    def __str__(self):
        return f"{self.type} {self.event_id} ({self.get_status_display()})"

    def entregado(self):
        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        self.last_error = None

    def fallo(self, motivo):
        _reintentar(self, motivo)
