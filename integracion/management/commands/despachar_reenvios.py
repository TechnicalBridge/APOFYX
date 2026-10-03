"""
Entrega lo que quedo en las dos bandejas de salida.

    python manage.py despachar_reenvios              una vez
    python manage.py despachar_reenvios --cada 60    sin parar, cada 60 segundos

- Las carteras por pasarle a DataBridge.
- Los eventos por avisarle a los clientes.

Lo que no se entrego en el primer intento se reintenta aca, con espera
creciente: 1 min, 5, 30, 2 h, 6 h y 24 h. Despues queda como fallido y visible
en el admin, para reenviarlo a mano.

Con --cada lo corre el contenedor `despachador` del docker-compose: sin el, una
cartera o un aviso que no salio porque DataBridge o el cliente estaban caidos
se quedaba en la bandeja hasta que alguien corriera el comando a mano.
"""

import argparse
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from ...eventos import despachar_eventos_pendientes
from ...models import Forward, OutboundEvent
from ...reenvio import configurado, despachar_pendientes


class Command(BaseCommand):
    help = "Entrega las carteras pendientes a DataBridge y los eventos pendientes a los clientes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cada", type=int, metavar="SEGUNDOS",
            help="No termina: vuelve a revisar las bandejas cada tantos segundos (al menos 5).",
        )
        #  Para las pruebas: cuantas vueltas da antes de terminar.
        parser.add_argument("--vueltas", type=int, help=argparse.SUPPRESS)

    def handle(self, *args, **opciones):
        cada = opciones.get("cada")
        if not cada:
            self._carteras(silencioso=False)
            self._eventos(silencioso=False)
            return
        if cada < 5:
            raise CommandError("--cada tiene que ser de al menos 5 segundos")

        self.stdout.write(f"Despachador: revisa las bandejas cada {cada} segundos.")
        vueltas = opciones.get("vueltas")
        while vueltas is None or vueltas > 0:
            #  Un proceso que vive dias: la conexion a la base se puede haber
            #  cerrado (MySQL se reinicio, o paso su wait_timeout).
            close_old_connections()
            try:
                self._carteras(silencioso=True)
                self._eventos(silencioso=True)
            except Exception as error:  # noqa: BLE001 — una vuelta mala no detiene al despachador
                self.stderr.write(f"Despachador: esta vuelta fallo ({error}); se reintenta en {cada} s.")
            if vueltas is not None:
                vueltas -= 1
                if vueltas == 0:
                    break
            time.sleep(cada)

    def _carteras(self, silencioso):
        if not configurado():
            if not silencioso:
                self.stdout.write("Carteras: DataBridge no esta configurado, no hay nada que reenviar.")
            return

        resultados = [f for f in despachar_pendientes() if f is not None]
        if not resultados and not silencioso:
            self.stdout.write("Carteras: no hay reenvios pendientes.")

        for forward in resultados:
            if forward.status == Forward.Status.SENT:
                aceptadas = forward.response.get("aceptadas")
                self.stdout.write(self.style.SUCCESS(
                    f"{forward.external_id}: entregada ({aceptadas} aceptadas)"))
            elif forward.status == Forward.Status.WAITING_CAMPAIGN:
                #  Sin parar se revisa cada vuelta: avisarlo cada vez seria ruido.
                if not silencioso:
                    self.stdout.write(self.style.WARNING(
                        f"{forward.external_id}: espera que se le asigne campaña"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"{forward.external_id}: {forward.get_status_display()} — {forward.last_error}"))

    def _eventos(self, silencioso):
        resultados = [e for e in despachar_eventos_pendientes() if e is not None]
        if not resultados and not silencioso:
            self.stdout.write("Eventos: no hay avisos pendientes.")

        for evento in resultados:
            destino = evento.subscription.creditor
            if evento.status == OutboundEvent.Status.DELIVERED:
                self.stdout.write(self.style.SUCCESS(f"{evento.type} a {destino}: entregado"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"{evento.type} a {destino}: {evento.get_status_display()} — {evento.last_error}"))
