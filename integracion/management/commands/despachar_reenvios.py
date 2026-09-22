"""
Entrega a DataBridge las carteras que quedaron en la bandeja.

    python manage.py despachar_reenvios

Pensado para correr cada pocos minutos desde el programador de tareas. Lo que
DataBridge no recibio en el primer intento se reintenta aca, con espera
creciente: 1 min, 5, 30, 2 h, 6 h y 24 h. Despues queda como fallida y
visible en el admin, para reenviarla a mano.
"""

from django.core.management.base import BaseCommand

from ...models import Forward
from ...reenvio import configurado, despachar_pendientes


class Command(BaseCommand):
    help = "Entrega a DataBridge las carteras pendientes de reenvio."

    def handle(self, *args, **opciones):
        if not configurado():
            self.stdout.write("DataBridge no esta configurado: no hay nada que despachar.")
            return

        resultados = [f for f in despachar_pendientes() if f is not None]
        if not resultados:
            self.stdout.write("No hay reenvios pendientes.")
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
