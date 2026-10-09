"""
Panel interno de APOFYX.

Lo que administra son los clientes B2B: sus datos, los accesos de sus cuentas,
su cartera entregada y sus campanas; y la conexion de APOFYX con la plataforma
de pagos. Pagos no hay: el dinero lo mueve DataBridge, y a APOFYX le llega el
aviso (docs seccion 2.2).

Todas las vistas exigen una sesion del PERSONAL (is_staff). Las empresas
tienen su propio portal (portal_views.py): una cuenta de empresa no ve el
panel, aunque haya iniciado sesion.
"""

from collections import Counter
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from assistant.models import Conversation, Message
from cartera.models import Batch, Debt, DebtCharge
from integracion.models import Forward, InboundEvent
from integracion.plataforma import ConexionFallida, conectar, conexion, desconectar, direccion_de_avisos
from .forms import (TRAMOS_DESCUENTO, CampanaForm, ConexionPlataformaForm, CreditorContactForm, CreditorForm,
                    DescuentoCampanaForm)
from .models import (
    Campaign, CampaignFunnelSnapshot, Creditor, CreditorContact, Lead,
)

# Cuantas filas por pagina en los listados. Con la cartera de demostracion no
# se nota, pero sin tope una base real dejaria la pagina inservible.
POR_PAGINA = 25

#  Las deudas que APOFYX esta cobrando: las otras ya se pagaron o volvieron al acreedor.
EN_GESTION = (Debt.Status.OPEN, Debt.Status.REPACTED, Debt.Status.DISPUTED)

#  Como se nombran en el panel, con tilde (las etiquetas del modelo van sin): en
#  plural para los totales, en singular para cada deuda.
ESTADOS_EN_PANEL = [
    (Debt.Status.OPEN, "En gestión"),
    (Debt.Status.REPACTED, "En convenio"),
    (Debt.Status.PAID, "Pagadas"),
    (Debt.Status.WITHDRAWN, "Retiradas o devueltas"),
]
ESTADO_DE_UNA = {
    Debt.Status.OPEN: "En gestión",
    Debt.Status.REPACTED: "En convenio",
    Debt.Status.PAID: "Pagada",
    Debt.Status.DISPUTED: "Disputada",
}


def es_personal(user):
    return user.is_active and user.is_staff


#  Una cuenta de empresa que llega aca vuelve al login del equipo, que no la deja
#  entrar: el panel es del personal.
personal_requerido = user_passes_test(es_personal, login_url="panel:login")


class EntrarPersonalForm(AuthenticationForm):
    """El login del panel: solo el personal de APOFYX."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Usuario o contraseña incorrectos.",
        "no_es_personal": "Esa cuenta no es del equipo de APOFYX. Las empresas entran por su portal.",
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError(self.error_messages["no_es_personal"], code="no_es_personal")


def estado_de(deuda):
    """El estado de una deuda en el panel. Una devuelta por mora se distingue de una que retiro el acreedor."""
    if deuda.status == Debt.Status.WITHDRAWN:
        return "Devuelta" if deuda.withdrawn_reason == "fuera_de_mandato" else "Retirada"
    return ESTADO_DE_UNA.get(deuda.status, deuda.get_status_display())


def adjuntar_cartera(empresas):
    """
    Deja en cada empresa un atributo .cartera: cuantas deudas tiene en gestion,
    el ticket medio en pesos y el corte de su ultima entrega.

    Sale de la cartera real, deuda por deuda. Dos consultas para toda la
    pagina, no dos por empresa. Se adjunta al objeto —y no se devuelve un
    diccionario aparte— porque las plantillas de Django no saben indexar por
    clave.
    """
    empresas = list(empresas)
    #  Por id y no por el queryset: el de una pagina lleva LIMIT, y MySQL no
    #  acepta un IN sobre una subconsulta con LIMIT.
    ids = [e.pk for e in empresas]
    vivas = {fila["creditor_id"]: fila for fila in (
        Debt.objects.filter(creditor_id__in=ids, status__in=EN_GESTION)
        .values("creditor_id").annotate(registros=Count("id"), corte=Max("last_batch__cut_off")))}
    #  El ticket, sobre las deudas en pesos: un promedio que mezclara pesos con
    #  UF no significaria nada.
    pesos = {fila["debt__creditor_id"]: fila["total"] / fila["deudas"] for fila in (
        DebtCharge.objects.filter(debt__creditor_id__in=ids, debt__status__in=EN_GESTION,
                                  debt__currency=Debt.Currency.CLP)
        .values("debt__creditor_id").annotate(total=Sum("amount"), deudas=Count("debt", distinct=True)))}
    for empresa in empresas:
        fila = vivas.get(empresa.pk)
        empresa.cartera = {
            "registros": fila["registros"] if fila else 0,
            "ticket": pesos.get(empresa.pk, 0),
            "periodo": fila["corte"] if fila else None,
        }
    return empresas


def condonado_por_deuda(empresa):
    """
    Los intereses de mora que se condonaron por pronto pago, por deuda: los
    trae cada pago.confirmado en `descuento` (contrato §8.2).
    """
    condonado = Counter()
    pagos = InboundEvent.objects.filter(type="pago.confirmado", debt__creditor=empresa).only("debt_id", "payload")
    for pago in pagos:
        try:
            valor = Decimal(str(((pago.payload or {}).get("datos") or {}).get("descuento") or 0))
        except InvalidOperation:
            continue
        if valor > 0:
            condonado[pago.debt_id] += valor
    return condonado


def cartera_recibida(empresa):
    """
    La cartera que el cliente entrego: sus entregas, que paso con cada deuda y
    cuanto queda por cobrar. None si nunca entrego nada.
    """
    entregas = list(Batch.objects.filter(creditor=empresa).select_related("forward").order_by("-cut_off", "-id")[:6])
    if not entregas:
        return None
    for entrega in entregas:
        #  Una entrega que no se reenvia no tiene Forward, y el acceso inverso
        #  revienta: se deja explicito para la plantilla.
        entrega.reenvio = getattr(entrega, "forward", None)
    deudas = (Debt.objects.filter(creditor=empresa).select_related("debtor", "last_batch")
              .prefetch_related("charges").order_by("status", "external_id"))
    condonado = condonado_por_deuda(empresa)
    por_estado = Counter()
    informado = {Debt.Currency.CLP: 0, Debt.Currency.UF: 0}
    filas = []
    for deuda in deudas:
        cargos = list(deuda.charges.all())
        saldo = sum((c.amount for c in cargos), 0)
        en_gestion = deuda.status in EN_GESTION
        if en_gestion:
            informado[deuda.currency] += saldo
        por_estado[deuda.status] += 1
        mas_antiguo = min((c.due_date for c in cargos), default=deuda.last_batch.cut_off)
        filas.append({
            "deuda": deuda, "saldo": saldo, "en_gestion": en_gestion,
            "estado": estado_de(deuda),
            "mora": (deuda.last_batch.cut_off - mas_antiguo).days,
            "condonado": condonado.get(deuda.pk),
        })
    estados = [(etiqueta, por_estado[valor]) for valor, etiqueta in ESTADOS_EN_PANEL]
    if por_estado[Debt.Status.DISPUTED]:
        estados.append(("Disputadas", por_estado[Debt.Status.DISPUTED]))
    return {
        "entregas": entregas,
        "deudas": filas,
        "estados": estados,
        "informado_clp": informado[Debt.Currency.CLP],
        "informado_uf": informado[Debt.Currency.UF],
    }


def accesos_pendientes(empresa=None):
    """Las cuentas de empresa que esperan que el personal las apruebe."""
    pendientes = CreditorContact.objects.filter(portal_access=CreditorContact.Access.PENDING)
    if empresa is not None:
        pendientes = pendientes.filter(creditor=empresa)
    return pendientes.select_related("creditor").order_by("created_at")


@personal_requerido
def dashboard(request):
    """Resumen: cuantos clientes hay, cuanta cartera, quien espera acceso y como rinden las campanas."""
    empresas = adjuntar_cartera(list(Creditor.objects.all()))
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
        "accesos_pendientes": accesos_pendientes(),
        "esperando_campana": (Forward.objects.filter(status=Forward.Status.WAITING_CAMPAIGN)
                              .select_related("batch__creditor")),
        "plataforma": conexion(),
        "embudo": embudo,
        "tasas": {
            "entrega": porcentaje(embudo["entregados"], embudo["enviados"]),
            "apertura": porcentaje(embudo["abiertos"], embudo["entregados"]),
            "clic": porcentaje(embudo["clics"], embudo["abiertos"]),
        },
        "ultimos_leads": Lead.objects.all()[:6],
        "cobertura_asistente": (
            Message.objects.filter(speaker=Message.Speaker.ASSISTANT)
            .values("answer_engine").annotate(total=Count("id")).order_by("-total")
        ),
        "conversaciones": Conversation.objects.count(),
    }
    return render(request, "panel/dashboard.html", contexto)


@personal_requerido
def clientes(request):
    """Listado de empresas cliente, con busqueda y filtro por estado."""
    empresas = Creditor.objects.all()

    busqueda = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()

    if busqueda:
        empresas = empresas.filter(
            Q(trade_name__icontains=busqueda)
            | Q(legal_name__icontains=busqueda)
            | Q(tax_id__icontains=busqueda)
        )
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
        "estados": Creditor.Status.choices,
        "busqueda": busqueda,
        "estado_elegido": estado,
        "hay_filtros": bool(busqueda or estado),
    }
    return render(request, "panel/clientes.html", contexto)


@personal_requerido
def cliente_detalle(request, pk):
    """Ficha de una empresa: datos, contactos y accesos, cartera y campanas."""
    empresa = get_object_or_404(
        Creditor.objects.prefetch_related("contacts", "campaigns__snapshots"),
        pk=pk,
    )

    adjuntar_cartera([empresa])

    # El embudo de cada campana viene de la propiedad del modelo, que ya suma
    # sus mediciones y calcula las tasas.
    campanas = [
        {"campana": c, "embudo": c.embudo,
         "descuento": [((c.mora_discount or {}).get(t, 0), etiqueta) for t, etiqueta in TRAMOS_DESCUENTO],
         "form_descuento": DescuentoCampanaForm(empresa=empresa, campana=c, auto_id=f"d{c.pk}_%s")}
        for c in empresa.campaigns.all().order_by("-starts_on")
    ]

    contexto = {
        "activo": "clientes",
        "empresa": empresa,
        "campanas": campanas,
        "leads": empresa.origin_leads.all()[:5],
        "recibida": cartera_recibida(empresa),
        "esperando_campana": Forward.objects.filter(batch__creditor=empresa,
                                                    status=Forward.Status.WAITING_CAMPAIGN).select_related("batch"),
        "en_curso": [c for c in empresa.campaigns.all() if c.status == Campaign.Status.RUNNING],
        "form_contacto": CreditorContactForm(),
        "estados": Creditor.Status.choices,
        "estados_campana": Campaign.Status.choices,
    }
    return render(request, "panel/cliente_detalle.html", contexto)


@personal_requerido
def leads(request):
    """Contactos entrantes, del formulario y del asistente."""
    lista = Lead.objects.select_related("converted_creditor")

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

@personal_requerido
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


@personal_requerido
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


@personal_requerido
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


@personal_requerido
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


@personal_requerido
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


@personal_requerido
@require_POST
def contacto_eliminar(request, pk, contacto_pk):
    """
    Elimina un contacto.

    Aca si se borra de verdad: un contacto no arrastra historico, y mantener
    a una persona que ya no trabaja ahi es peor que no tenerla. Si tenia cuenta
    en el portal, la cuenta queda sin empresa y ya no puede entrar.
    """
    empresa = get_object_or_404(Creditor, pk=pk)
    contacto = get_object_or_404(CreditorContact, pk=contacto_pk, creditor=empresa)
    nombre = contacto.full_name
    contacto.delete()
    messages.success(request, f"{nombre} fue eliminado.")
    return redirect("panel:cliente_detalle", pk=empresa.pk)


# ==========================================================================
#  Accesos al portal de empresas
# ==========================================================================

@personal_requerido
@require_POST
def acceso_aprobar(request, pk, contacto_pk):
    """
    Aprueba la cuenta de un contacto. Si la empresa estaba en incorporacion,
    queda activa: el personal ya la reviso.
    """
    empresa = get_object_or_404(Creditor, pk=pk)
    contacto = get_object_or_404(CreditorContact, pk=contacto_pk, creditor=empresa, user__isnull=False)
    contacto.portal_access = CreditorContact.Access.GRANTED
    contacto.save(update_fields=["portal_access", "updated_at"])
    if empresa.status == Creditor.Status.ONBOARDING:
        empresa.status = Creditor.Status.ACTIVE
        empresa.save(update_fields=["status", "updated_at"])
    messages.success(request, f"{contacto.full_name} ya puede entrar al portal de {empresa.trade_name}.")
    return redirect(request.POST.get("volver") or reverse("panel:cliente_detalle", args=[empresa.pk]))


@personal_requerido
@require_POST
def acceso_revocar(request, pk, contacto_pk):
    """Le quita el acceso al portal. La cuenta queda, sin poder entrar."""
    empresa = get_object_or_404(Creditor, pk=pk)
    contacto = get_object_or_404(CreditorContact, pk=contacto_pk, creditor=empresa, user__isnull=False)
    contacto.portal_access = CreditorContact.Access.REVOKED
    contacto.save(update_fields=["portal_access", "updated_at"])
    messages.success(request, f"{contacto.full_name} ya no puede entrar al portal.")
    return redirect("panel:cliente_detalle", pk=empresa.pk)


# ==========================================================================
#  Campanas
# ==========================================================================

@personal_requerido
def campana_nueva(request, pk):
    """
    Una campana sobre la cartera de la empresa. Una entrega que esperaba
    campana y la empresa ahora tiene exactamente una en curso, sale sola.
    """
    empresa = get_object_or_404(Creditor, pk=pk)
    form = CampanaForm(request.POST or None, empresa=empresa)
    if request.method == "POST" and form.is_valid():
        campana = form.save(commit=False)
        campana.creditor = empresa
        if Campaign.objects.filter(creditor=empresa, name=campana.name).exists():
            form.add_error("name", "Esta empresa ya tiene una campaña con ese nombre.")
        else:
            form.save()
            messages.success(request, f"La campaña {campana.name} quedó creada.")
            if form.advertencia:
                messages.warning(request, form.advertencia)
            _despachar_esperando(request, empresa)
            return redirect("panel:cliente_detalle", pk=empresa.pk)

    return render(request, "panel/campana_form.html", {
        "activo": "clientes", "form": form, "empresa": empresa,
    })


@personal_requerido
@require_POST
def campana_estado(request, pk, campana_pk):
    """En curso, pausada o finalizada."""
    empresa = get_object_or_404(Creditor, pk=pk)
    campana = get_object_or_404(Campaign, pk=campana_pk, creditor=empresa)
    nuevo = request.POST.get("estado")
    if nuevo not in dict(Campaign.Status.choices):
        messages.error(request, "Ese estado no existe.")
    else:
        campana.status = nuevo
        campana.save(update_fields=["status", "updated_at"])
        messages.success(request, f"{campana.name} quedó {campana.get_status_display().lower()}.")
        #  La plataforma de pagos ejecuta la campana: se entera ya, no con la proxima cartera.
        from integracion.reenvio import sincronizar_campana

        error = sincronizar_campana(campana)
        if isinstance(error, str):
            messages.warning(request, "No se pudo avisar a la plataforma de pagos: se le avisa con la próxima "
                                      f"cartera. ({error})")
        if nuevo == Campaign.Status.RUNNING:
            _despachar_esperando(request, empresa)
    return redirect("panel:cliente_detalle", pk=empresa.pk)


@personal_requerido
@require_POST
def campana_descuento(request, pk, campana_pk):
    """
    Cambia el descuento por tramo de una campana. Nunca pasa lo que autoriza la
    empresa, y DataBridge, que lo aplica al cobrar, se entera al instante.
    """
    empresa = get_object_or_404(Creditor, pk=pk)
    campana = get_object_or_404(Campaign, pk=campana_pk, creditor=empresa)
    form = DescuentoCampanaForm(request.POST, empresa=empresa, campana=campana)
    if not form.is_valid():
        errores = [e for lista in form.errors.values() for e in lista]
        messages.error(request, f"No se guardó el descuento de {campana.name}: {errores[0]}")
        return redirect("panel:cliente_detalle", pk=empresa.pk)
    campana.mora_discount = form.descuento()
    campana.save(update_fields=["mora_discount", "updated_at"])
    messages.success(request, f"El descuento de {campana.name} quedó guardado.")
    from integracion.reenvio import sincronizar_campana

    error = sincronizar_campana(campana)
    if isinstance(error, str):
        messages.warning(request, "No se pudo avisar a la plataforma de pagos: se le avisa con la próxima "
                                  f"cartera. ({error})")
    return redirect("panel:cliente_detalle", pk=empresa.pk)


@personal_requerido
@require_POST
def entregas_asignar(request, pk):
    """Asigna una campana a las entregas de la empresa que la esperaban, y las reenvia."""
    empresa = get_object_or_404(Creditor, pk=pk)
    campana = get_object_or_404(Campaign, pk=request.POST.get("campana"), creditor=empresa)
    esperando = Forward.objects.filter(batch__creditor=empresa, status=Forward.Status.WAITING_CAMPAIGN)
    Batch.objects.filter(forward__in=esperando).update(campaign=campana)
    _despachar_esperando(request, empresa)
    return redirect("panel:cliente_detalle", pk=empresa.pk)


def _despachar_esperando(request, empresa):
    """Reintenta ya las entregas de la empresa que esperaban campana."""
    from integracion.reenvio import despachar

    for forward in Forward.objects.filter(batch__creditor=empresa, status=Forward.Status.WAITING_CAMPAIGN):
        resultado = despachar(forward.pk)
        if resultado.status == Forward.Status.SENT:
            messages.success(request, f"La entrega {forward.batch.external_id} se reenvió a la plataforma de pagos.")


# ==========================================================================
#  La conexion con la plataforma de pagos
# ==========================================================================

@personal_requerido
def plataforma(request):
    """
    Conecta APOFYX con la plataforma de pagos: la direccion y la clave que la
    plataforma le emitio. Al conectar se comprueba la clave y se suscribe a los
    avisos; desde ese momento vale, sin reiniciar nada.
    """
    actual = conexion()
    if request.method == "POST" and request.POST.get("accion") == "desconectar":
        desconectar()
        messages.success(request, "APOFYX quedó desconectada de la plataforma de pagos.")
        return redirect("panel:plataforma")

    inicial = {"url_avisos": direccion_de_avisos(request)}
    if actual is not None:
        inicial["url"] = actual.url
    form = ConexionPlataformaForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        try:
            fila = conectar(form.cleaned_data["url"], form.cleaned_data["api_key"],
                            form.cleaned_data["url_avisos"])
        except ConexionFallida as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"APOFYX quedó conectada con {fila.platform_name}.")
            return redirect("panel:plataforma")

    return render(request, "panel/plataforma.html", {
        "activo": "plataforma", "form": form, "actual": actual,
        "esperando": Forward.objects.exclude(status=Forward.Status.SENT).select_related("batch__creditor")[:20],
    })
