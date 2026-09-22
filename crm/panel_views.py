"""
Panel interno de APOFYX.

Lo unico que administra son los clientes B2B: sus datos, su cartera entregada y
el rendimiento de sus campanas. No hay deudores ni pagos, porque APOFYX no los
toca (docs seccion 2.2).

Todas las vistas exigen sesion iniciada.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from assistant.models import Conversation, Message
from .forms import CreditorContactForm, CreditorForm
from .models import (
    Campaign, CampaignFunnelSnapshot, Creditor, CreditorContact, Industry, Lead,
)

# Cuantas filas por pagina en los listados. Con la cartera de demostracion no
# se nota, pero sin tope una base real dejaria la pagina inservible.
POR_PAGINA = 25


def adjuntar_cartera(empresas):
    """
    Deja en cada empresa un atributo .cartera con su ultimo periodo.

    Cada empresa tiene una fila por tramo de mora, asi que hay que agregarlas
    antes de mostrarlas; y el ticket medio se pondera por cantidad de
    registros, no es el promedio simple de los tres tramos.

    Se calcula en Python sobre lo que ya trajo prefetch_related, en vez de una
    consulta por empresa. Se adjunta al objeto —y no se devuelve un diccionario
    aparte— porque las plantillas de Django no saben indexar por clave.
    """
    for empresa in empresas:
        tramos = list(empresa.handovers.all())
        if not tramos:
            empresa.cartera = {"registros": 0, "ticket": 0, "periodo": None, "tramos": []}
            continue
        ultimo = max(t.period_month for t in tramos)
        del_periodo = [t for t in tramos if t.period_month == ultimo]
        total = sum(t.debtor_count for t in del_periodo)
        empresa.cartera = {
            "registros": total,
            "ticket": (
                sum(t.average_debt_clp * t.debtor_count for t in del_periodo) / total
                if total else 0
            ),
            "periodo": ultimo,
            "tramos": sorted(del_periodo, key=lambda t: t.overdue_bracket),
        }
    return empresas


@login_required
def dashboard(request):
    """Resumen: cuantos clientes hay, cuanta cartera y como rinden las campanas."""
    empresas = adjuntar_cartera(list(Creditor.objects.prefetch_related("handovers")))
    cartera_total = sum(e.cartera["registros"] for e in empresas)

    embudo = CampaignFunnelSnapshot.objects.aggregate(
        enviados=Sum("messages_sent"), entregados=Sum("messages_delivered"), abiertos=Sum("messages_opened"),
        respondidos=Sum("replies_received"), clics=Sum("link_clicks"),
        fraudes=Sum("fraud_reports"), bajas=Sum("optout_requests"),
    )
    embudo = {k: (v or 0) for k, v in embudo.items()}

    def porcentaje(parte, total):
        return round(100 * parte / total, 1) if total else 0

    contexto = {
        "activo": "resumen",
        "clientes_activos": sum(1 for e in empresas if e.status == Creditor.Status.ACTIVE),
        "clientes_total": len(empresas),
        "cartera_total": cartera_total,
        "campanas_en_curso": Campaign.objects.filter(
            status=Campaign.Status.RUNNING
        ).count(),
        "leads_nuevos": Lead.objects.filter(status=Lead.Status.NEW).count(),
        "embudo": embudo,
        "tasas": {
            "entrega": porcentaje(embudo["entregados"], embudo["enviados"]),
            "apertura": porcentaje(embudo["abiertos"], embudo["entregados"]),
            "clic": porcentaje(embudo["clics"], embudo["abiertos"]),
        },
        "rubros": (
            Industry.objects.annotate(total=Count("creditors"))
            .filter(total__gt=0).order_by("-total")
        ),
        "ultimos_leads": Lead.objects.select_related("industry")[:6],
        "cobertura_asistente": (
            Message.objects.filter(speaker=Message.Speaker.ASSISTANT)
            .values("answer_engine").annotate(total=Count("id")).order_by("-total")
        ),
        "conversaciones": Conversation.objects.count(),
    }
    return render(request, "panel/dashboard.html", contexto)


@login_required
def clientes(request):
    """Listado de empresas cliente, con busqueda y filtros."""
    empresas = Creditor.objects.select_related("industry").prefetch_related("handovers")

    busqueda = (request.GET.get("q") or "").strip()
    rubro = (request.GET.get("rubro") or "").strip()
    estado = (request.GET.get("estado") or "").strip()

    if busqueda:
        empresas = empresas.filter(
            Q(trade_name__icontains=busqueda)
            | Q(legal_name__icontains=busqueda)
            | Q(tax_id__icontains=busqueda)
        )
    if rubro:
        empresas = empresas.filter(industry__slug=rubro)
    if estado:
        empresas = empresas.filter(status=estado)

    pagina = Paginator(empresas.order_by("trade_name"), POR_PAGINA).get_page(
        request.GET.get("pagina")
    )
    adjuntar_cartera(pagina.object_list)

    contexto = {
        "activo": "clientes",
        "pagina": pagina,
        "empresas": pagina.object_list,
        "total": pagina.paginator.count,
        "rubros": Industry.objects.filter(is_active=True),
        "estados": Creditor.Status.choices,
        "busqueda": busqueda,
        "rubro_elegido": rubro,
        "estado_elegido": estado,
        "hay_filtros": bool(busqueda or rubro or estado),
    }
    return render(request, "panel/clientes.html", contexto)


@login_required
def cliente_detalle(request, pk):
    """Ficha de una empresa: datos, contactos, cartera y campanas."""
    empresa = get_object_or_404(
        Creditor.objects.select_related("industry").prefetch_related(
            "contacts", "handovers", "campaigns__snapshots"
        ),
        pk=pk,
    )

    adjuntar_cartera([empresa])

    # El embudo de cada campana viene de la propiedad del modelo, que ya suma
    # sus mediciones y calcula las tasas.
    campanas = [
        {"campana": c, "embudo": c.embudo}
        for c in empresa.campaigns.all().order_by("-starts_on")
    ]

    contexto = {
        "activo": "clientes",
        "empresa": empresa,
        "campanas": campanas,
        "leads": empresa.origin_leads.all()[:5],
        "form_contacto": CreditorContactForm(),
        "estados": Creditor.Status.choices,
    }
    return render(request, "panel/cliente_detalle.html", contexto)


@login_required
def leads(request):
    """Contactos entrantes, del formulario y del asistente."""
    lista = Lead.objects.select_related("industry", "converted_creditor")

    estado = (request.GET.get("estado") or "").strip()
    origen = (request.GET.get("origen") or "").strip()
    if estado:
        lista = lista.filter(status=estado)
    if origen:
        lista = lista.filter(source=origen)

    pagina = Paginator(lista, POR_PAGINA).get_page(request.GET.get("pagina"))

    contexto = {
        "activo": "leads",
        "pagina": pagina,
        "leads": pagina.object_list,
        "total": pagina.paginator.count,
        "estados": Lead.Status.choices,
        "origenes": Lead.Source.choices,
        "estado_elegido": estado,
        "origen_elegido": origen,
    }
    return render(request, "panel/leads.html", contexto)


# ==========================================================================
#  Alta, edicion y baja
#
#  La "baja" no borra: cambia el estado a 'churned'. Una empresa arrastra
#  cartera, campanas y metricas, y borrarla se llevaria el historico por
#  delante. El borrado real, si alguna vez hace falta, vive en el admin.
# ==========================================================================

@login_required
def cliente_nuevo(request):
    """Alta de una empresa cliente."""
    form = CreditorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        empresa = form.save()
        messages.success(request, f"{empresa.trade_name} quedo registrada.")
        return redirect("panel:cliente_detalle", pk=empresa.pk)

    return render(request, "panel/cliente_form.html", {
        "activo": "clientes", "form": form, "es_nueva": True,
    })


@login_required
def cliente_editar(request, pk):
    """Edicion de los datos de una empresa."""
    empresa = get_object_or_404(Creditor, pk=pk)
    form = CreditorForm(request.POST or None, instance=empresa)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Datos actualizados.")
        return redirect("panel:cliente_detalle", pk=empresa.pk)

    return render(request, "panel/cliente_form.html", {
        "activo": "clientes", "form": form, "empresa": empresa, "es_nueva": False,
    })


@login_required
@require_POST
def cliente_estado(request, pk):
    """Cambia el estado de una empresa. Es la baja, sin perder el historico."""
    empresa = get_object_or_404(Creditor, pk=pk)
    nuevo = request.POST.get("estado")

    if nuevo not in dict(Creditor.Status.choices):
        messages.error(request, "Ese estado no existe.")
    else:
        empresa.status = nuevo
        empresa.save(update_fields=["status", "updated_at"])
        messages.success(
            request, f"{empresa.trade_name} quedo como {empresa.get_status_display()}."
        )
    return redirect("panel:cliente_detalle", pk=empresa.pk)


@login_required
def contacto_nuevo(request, pk):
    """Agrega un contacto a la empresa."""
    empresa = get_object_or_404(Creditor, pk=pk)
    form = CreditorContactForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        contacto = form.save(commit=False)
        contacto.creditor = empresa
        contacto.save()   # el save() del modelo degrada al principal anterior
        messages.success(request, f"{contacto.full_name} quedo agregado.")
        return redirect("panel:cliente_detalle", pk=empresa.pk)

    return render(request, "panel/contacto_form.html", {
        "activo": "clientes", "form": form, "empresa": empresa, "es_nuevo": True,
    })


@login_required
def contacto_editar(request, pk, contacto_pk):
    """Edicion de un contacto."""
    empresa = get_object_or_404(Creditor, pk=pk)
    contacto = get_object_or_404(CreditorContact, pk=contacto_pk, creditor=empresa)
    form = CreditorContactForm(request.POST or None, instance=contacto)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Contacto actualizado.")
        return redirect("panel:cliente_detalle", pk=empresa.pk)

    return render(request, "panel/contacto_form.html", {
        "activo": "clientes", "form": form, "empresa": empresa,
        "contacto": contacto, "es_nuevo": False,
    })


@login_required
@require_POST
def contacto_eliminar(request, pk, contacto_pk):
    """
    Elimina un contacto.

    Aca si se borra de verdad: un contacto no arrastra historico, y mantener
    a una persona que ya no trabaja ahi es peor que no tenerla.
    """
    empresa = get_object_or_404(Creditor, pk=pk)
    contacto = get_object_or_404(CreditorContact, pk=contacto_pk, creditor=empresa)
    nombre = contacto.full_name
    contacto.delete()
    messages.success(request, f"{nombre} fue eliminado.")
    return redirect("panel:cliente_detalle", pk=empresa.pk)
