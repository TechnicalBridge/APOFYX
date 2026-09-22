"""
Emite la clave de API con la que un acreedor entrega su cartera.

    python manage.py emitir_clave 76418902-7 "Patrimonio Inmuebles"

La clave se muestra UNA vez. En la base queda solo su huella, asi que nadie
—ni APOFYX— puede volver a leerla: si se pierde, se emite otra y se revoca la
anterior.
"""

from django.core.management.base import BaseCommand, CommandError

from crm.models import Creditor
from crm.rut import es_valido, normalizar

from ...models import ApiKey


class Command(BaseCommand):
    help = "Emite una clave de API para que un acreedor entregue su cartera."

    def add_arguments(self, parser):
        parser.add_argument("rut", help="RUT del acreedor, como 76418902-7")
        parser.add_argument("nombre", help="Para que se emite, por ejemplo 'Servidor de Patrimonio'")
        parser.add_argument(
            "--revocar-anteriores", action="store_true",
            help="Revoca las claves vigentes de ese acreedor antes de emitir la nueva.",
        )

    def handle(self, *args, **opciones):
        rut = normalizar(opciones["rut"])
        if not es_valido(rut):
            raise CommandError(f"{rut} no es un RUT valido (revisa el digito verificador).")

        try:
            acreedor = Creditor.objects.get(tax_id=rut)
        except Creditor.DoesNotExist:
            raise CommandError(
                f"No hay ninguna empresa acreedora con RUT {rut}. "
                "Crea primero el cliente en el panel."
            )

        if opciones["revocar_anteriores"]:
            from django.utils import timezone

            revocadas = ApiKey.objects.filter(
                creditor=acreedor, revoked_at__isnull=True
            ).update(revoked_at=timezone.now())
            if revocadas:
                self.stdout.write(f"Revocadas {revocadas} clave(s) anterior(es).")

        clave, registro = ApiKey.emitir(acreedor, opciones["nombre"])

        self.stdout.write(self.style.SUCCESS(f"\nClave emitida para {acreedor.trade_name}:\n"))
        self.stdout.write(f"    {clave}\n")
        self.stdout.write(
            "\nGuardala ahora: no se puede volver a mostrar.\n"
            f"En la base queda como {registro.prefix}... y se usa asi:\n\n"
            "    Authorization: Bearer <la clave>\n"
            "    POST /api/v1/carteras\n"
        )
