"""
Vistas del sitio publico de APOFYX.

MVT clasico: la vista consulta los modelos y entrega el contexto; la plantilla
se encarga de mostrarlo. Nada de datos escritos a mano en el HTML: rubros,
clientes y cifras salen de la base.
"""

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import redirect, render

from .forms import LeadForm
from .models import PortfolioHandover, CampaignFunnelSnapshot, Creditor, Industry, Lead


# Los pasos del servicio son texto editorial, no datos: viven aca y no en la
# base, porque no cambian por cliente ni los administra nadie desde el panel.
PASOS = [
    {
        "numero": "01",
        "titulo": "Nos entrega su cartera",
        "texto": "Sube un archivo CSV desde su panel o conecta su sistema por API. "
                 "Normalizamos RUT, telefonos y correos, y eliminamos duplicados.",
    },
    {
        "numero": "02",
        "titulo": "Priorizamos con un modelo",
        "texto": "Un modelo de propension ordena la cartera segun probabilidad de "
                 "pago, para partir por donde rinde mas.",
    },
    {
        "numero": "03",
        "titulo": "Contactamos por canales digitales",
        "texto": "WhatsApp, SMS y correo, con una cadencia programada y respetando "
                 "las ventanas horarias que exige la ley.",
    },
    {
        "numero": "04",
        "titulo": "Un asistente responde",
        "texto": "Si el deudor escribe, un asistente automatico responde sus dudas "
                 "y le entrega el medio de pago que usted defina.",
    },
    {
        "numero": "05",
        "titulo": "Usted sigue el rendimiento",
        "texto": "Panel con entregas, aperturas, respuestas y clics por campana, "
                 "actualizado todos los dias.",
    },
]


def _cifras():
    """
    Cifras agregadas para la portada.

    Salen de la base, no estan escritas en la plantilla: si cambian los datos,
    cambia el sitio.
    """
    ultimo_periodo = (
        PortfolioHandover.objects.order_by("-period_month")
        .values_list("period_month", flat=True)
        .first()
    )

    cartera = 0
    if ultimo_periodo:
        cartera = (
            PortfolioHandover.objects.filter(period_month=ultimo_periodo)
            .aggregate(total=Sum("debtor_count"))["total"]
            or 0
        )

    totales = CampaignFunnelSnapshot.objects.aggregate(
        enviados=Sum("messages_sent"), entregados=Sum("messages_delivered")
    )
    enviados = totales["enviados"] or 0
    entregados = totales["entregados"] or 0

    return {
        "empresas": Creditor.objects.filter(status=Creditor.Status.ACTIVE).count(),
        "cartera": cartera,
        "mensajes": enviados,
        # La tasa de entrega es la cifra que APOFYX si puede medir con certeza.
        "tasa_entrega": round(100 * entregados / enviados, 1) if enviados else 0,
        "rubros": Industry.objects.filter(is_active=True).count(),
    }


def _contexto_portada(form=None):
    """
    Contexto completo de la portada. Lo comparten home() y contacto().

    No se exponen planes ni precios: el sitio no vende tarifas, lleva al
    formulario de contacto. Los planes siguen existiendo como dato interno de
    cada cliente, pero solo se ven en el panel.
    """
    return {
        "rubros": Industry.objects.filter(is_active=True),
        "clientes": Creditor.objects.filter(
            status=Creditor.Status.ACTIVE
        ).order_by("trade_name"),
        "cifras": _cifras(),
        "pasos": PASOS,
        "form": form if form is not None else LeadForm(),
    }


def home(request):
    """Portada: problema, solucion, proceso, rubros, cumplimiento y contacto."""
    return render(request, "site/home.html", _contexto_portada())


def contacto(request):
    """Recibe el formulario de la portada y graba un lead real en MySQL."""
    if request.method != "POST":
        return redirect("site:home")

    form = LeadForm(request.POST)
    if form.is_valid():
        lead = form.save(commit=False)
        lead.source = Lead.Source.FORM
        lead.save()
        return redirect("site:gracias")

    # Con errores se vuelve a la portada con el formulario tal como quedo, para
    # que el visitante no pierda lo que ya escribio.
    messages.error(request, "Revise los campos marcados y vuelva a enviar.")
    respuesta = render(request, "site/home.html", _contexto_portada(form))
    respuesta.status_code = 400
    return respuesta



def gracias(request):
    """Confirmacion tras enviar el formulario."""
    return render(request, "site/gracias.html")
