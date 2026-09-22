"""
Le pide a DataBridge que le avise a APOFYX los eventos de sus carteras.

    python manage.py suscribirse_a_databridge https://apofyx.cl/api/v1/eventos

DataBridge responde con el secreto con que va a firmar los avisos. Va al .env
como DATABRIDGE_SECRETO_EVENTOS: sin el, APOFYX rechaza todo evento, porque no
tendria como saber que viene de DataBridge.
"""

from django.core.management.base import BaseCommand, CommandError

from ...reenvio import ClienteDataBridge, ErrorDataBridge, configurado


class Command(BaseCommand):
    help = "Registra en DataBridge la URL por donde APOFYX recibe los eventos."

    def add_arguments(self, parser):
        parser.add_argument("url", help="La URL publica de /api/v1/eventos de este APOFYX")

    def handle(self, *args, **opciones):
        if not configurado():
            raise CommandError("Falta DATABRIDGE_URL o DATABRIDGE_CLAVE en el .env")
        try:
            respuesta = ClienteDataBridge().enviar("/api/v1/suscripciones", {"url": opciones["url"]})
        except ErrorDataBridge as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(f"DataBridge avisara los eventos a {respuesta['url']}"))
        self.stdout.write("")
        self.stdout.write("Agregar al .env de APOFYX:")
        self.stdout.write(f"    DATABRIDGE_SECRETO_EVENTOS={respuesta['secreto']}")
