"""
Entrega lo que quedo en las dos bandejas de salida.

    python manage.py despachar_reenvios

- Las carteras por pasarle a DataBridge.
- Los eventos por avisarle a los clientes.

Pensado para correr cada minuto desde el programador de tareas. Lo que no se
entrego en el primer intento se reintenta aca, con espera creciente: 1 min, 5,
30, 2 h, 6 h y 24 h. Despues queda como fallido y visible en el admin, para
reenviarlo a mano.
"""

from django.core.management.base import BaseCommand

from ...eventos import despachar_eventos_pendientes
from ...models import Forward, OutboundEvent
from ...reenvio import configurado, despachar_pendientes


class Command(BaseCommand):
    help = "Entrega las carteras pendientes a DataBridge y los eventos pendientes a los clientes."

    def handle(self, *args, **opciones):
        self._carteras()
        self._eventos()

    def _carteras(self):
        if not configurado():
            self.stdout.write("Carteras: DataBridge no esta configurado, no hay nada que reenviar.")
            return

        resultados = [f for f in despachar_pendientes() if f is not None]
        if not resultados:
            self.stdout.write("Carteras: no hay reenvios pendientes.")
            return

        for forward in resultados:
            if forward.status == Forward.Status.SENT:
                aceptadas = forward.response.get("aceptadas")
                self.stdout.write(self.style.SUCCESS(
                    f"{forward.external_id}: entregada ({aceptadas} aceptadas)"))
            elif forward.status == Forward.Status.WAITING_CAMPAIGN:
                self.stdout.write(self.style.WARNING(
                    f"{forward.external_id}: espera que se le asigne campana"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"{forward.external_id}: {forward.get_status_display()} — {forward.last_error}"))

    def _eventos(self):
        resultados = [e for e in despachar_eventos_pendientes() if e is not None]
        if not resultados:
            self.stdout.write("Eventos: no hay avisos pendientes.")
            return

        for evento in resultados:
            destino = evento.subscription.creditor
            if evento.status == OutboundEvent.Status.DELIVERED:
                self.stdout.write(self.style.SUCCESS(f"{evento.type} a {destino}: entregado"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"{evento.type} a {destino}: {evento.get_status_display()} — {evento.last_error}"))
