"""
Registra a donde avisarle a un cliente lo que pasa con su cartera.

    python manage.py suscribir_cliente 76418902-7 http://localhost:3001/api/eventos

Muestra el secreto con que APOFYX va a firmar los avisos. El cliente lo
configura de su lado —en Patrimonio es EVENTOS_SECRET— para verificar que cada
aviso viene de APOFYX. Repetir el comando con la misma URL devuelve el mismo
secreto.
"""

from django.core.management.base import BaseCommand, CommandError

from crm.models import Creditor
from crm.rut import es_valido, normalizar

from ...eventos import ESTADO_POR_EVENTO
from ...models import Subscription

TIPOS = sorted({*ESTADO_POR_EVENTO, "pago.confirmado"})


class Command(BaseCommand):
    help = "Registra la URL a la que APOFYX le avisa los eventos a un cliente."

    def add_arguments(self, parser):
        parser.add_argument("rut", help="RUT del acreedor, como 76418902-7")
        parser.add_argument("url", help="Donde recibe los eventos, por ejemplo http://localhost:3001/api/eventos")
        parser.add_argument("--eventos", nargs="*", choices=TIPOS, default=[],
                            help="Solo estos tipos. Sin la opcion, todos.")

    def handle(self, *args, **opciones):
        rut = normalizar(opciones["rut"])
        if not es_valido(rut):
            raise CommandError(f"{opciones['rut']} no es un RUT valido")
        acreedor = Creditor.objects.filter(tax_id=rut).first()
        if acreedor is None:
            raise CommandError(f"No hay ningun acreedor con RUT {rut}")
        url = opciones["url"].strip()
        if not url.startswith(("http://", "https://")):
            raise CommandError("La URL tiene que empezar con http:// o https://")

        suscripcion = Subscription.registrar(acreedor, url, opciones["eventos"])
        self.stdout.write(self.style.SUCCESS(f"{acreedor} recibira sus eventos en {url}"))
        self.stdout.write(f"Eventos: {', '.join(suscripcion.events) or 'todos'}")
        self.stdout.write("")
        self.stdout.write("Secreto para configurar en el cliente (en Patrimonio, EVENTOS_SECRET):")
        self.stdout.write(f"    {suscripcion.secret}")
