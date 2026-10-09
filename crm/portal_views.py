"""
El portal de empresas: lo que ve una empresa cliente de APOFYX.

Una empresa se registra sola, el personal aprueba su acceso, y desde aqui:

- ve la cartera que entrego y que paso con cada deuda;
- conecta su sistema: emite y revoca sus claves de API, y registra donde
  recibe los avisos de pago;
- si no tiene sistema, sube su cartera en la planilla del contrato;
- revisa sus datos y sus contactos.

Nada de esto pasa por la consola ni por el personal, salvo aprobar el acceso.
Las sesiones son las de Django, guardadas en la base (django_session).
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from cartera.models import Batch
from integracion import planilla
from integracion.intake import CarteraInvalida, recibir_cartera
from integracion.models import ApiKey, OutboundEvent, Subscription
from integracion.reenvio import sincronizar_mandato
from .forms import (CreditorContactForm, DescuentoMaximoForm, EntrarEmpresaForm, RegistroEmpresaForm,
                    SubirCarteraForm)
from .models import Creditor, CreditorContact
from .panel_views import cartera_recibida


def empresa_requerida(vista):
    """Solo un contacto con el acceso aprobado. Deja la empresa en request.empresa."""
    @wraps(vista)
    def envuelta(request, *args, **kwargs):
        contacto = getattr(request.user, "contacto", None) if request.user.is_authenticated else None
        if contacto is None or not contacto.puede_entrar:
            return redirect(f"{reverse_lazy('portal:entrar')}?next={request.path}")
        request.contacto = contacto
        request.empresa = contacto.creditor
        return vista(request, *args, **kwargs)
    return envuelta


class Entrar(auth_views.LoginView):
    template_name = "portal/entrar.html"
    authentication_form = EntrarEmpresaForm
    next_page = reverse_lazy("portal:inicio")


class Salir(auth_views.LogoutView):
    next_page = reverse_lazy("portal:entrar")


def registro(request):
    """
    Una empresa pide su cuenta. Con un RUT nuevo se crea la empresa, en
    incorporacion; con uno que ya es cliente, la persona se suma a esa empresa.
    En los dos casos el acceso queda por aprobar.
    """
    form = RegistroEmpresaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        with transaction.atomic():
            empresa, nueva = Creditor.objects.get_or_create(tax_id=datos["tax_id"], defaults={
                "legal_name": datos["legal_name"], "trade_name": datos["trade_name"],
                "commune": datos["commune"] or None, "region": datos["region"] or None,
                "website": datos["website"] or None, "status": Creditor.Status.ONBOARDING,
            })
            usuario = get_user_model().objects.create_user(
                username=datos["email"], email=datos["email"], password=datos["password1"],
                first_name=datos["full_name"][:150],
            )
            contacto = CreditorContact.objects.filter(creditor=empresa, email__iexact=datos["email"]).first()
            if contacto is None:
                contacto = CreditorContact(creditor=empresa, email=datos["email"],
                                           is_primary=not empresa.contacts.exists())
            contacto.full_name = datos["full_name"]
            contacto.job_title = datos["job_title"] or contacto.job_title
            contacto.phone = datos["phone"] or contacto.phone
            contacto.user = usuario
            contacto.portal_access = CreditorContact.Access.PENDING
            contacto.save()
        return render(request, "portal/registro_listo.html", {"empresa": empresa, "nueva": nueva})
    return render(request, "portal/registro.html", {"form": form})


@empresa_requerida
def inicio(request):
    """Mi cartera: las entregas y que paso con cada deuda."""
    return render(request, "portal/inicio.html", {
        "activo": "cartera", "empresa": request.empresa, "recibida": cartera_recibida(request.empresa),
    })


@empresa_requerida
def conexion(request):
    """Conectar mi sistema: las claves de API y donde recibe los avisos."""
    empresa = request.empresa
    clave_nueva = secreto_nuevo = None

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "emitir":
            nombre = (request.POST.get("nombre") or "").strip()[:80] or "Mi sistema"
            clave_nueva, _ = ApiKey.emitir(empresa, nombre)
        elif accion == "revocar":
            clave = get_object_or_404(ApiKey, pk=request.POST.get("clave"), creditor=empresa)
            clave.revocar()
            messages.success(request, f"La clave {clave.prefix}… quedó revocada.")
            return redirect("portal:conexion")
        elif accion == "avisos":
            url = (request.POST.get("url") or "").strip()
            if not url.startswith(("http://", "https://")) or len(url) > 300:
                messages.error(request, "La dirección tiene que partir con http:// o https://")
            else:
                secreto_nuevo = Subscription.registrar(empresa, url).secret
        elif accion == "quitar_avisos":
            Subscription.objects.filter(pk=request.POST.get("suscripcion"), creditor=empresa).update(active=False)
            messages.success(request, "Ya no le avisaremos a esa dirección.")
            return redirect("portal:conexion")

    return render(request, "portal/conexion.html", {
        "activo": "conexion", "empresa": empresa,
        "claves": empresa.api_keys.order_by("-created_at"),
        "suscripciones": empresa.subscriptions.filter(active=True),
        "avisos": (OutboundEvent.objects.filter(subscription__creditor=empresa)
                   .order_by("-created_at")[:10]),
        "clave_nueva": clave_nueva, "secreto_nuevo": secreto_nuevo,
        "base": request.build_absolute_uri("/api/v1/").rstrip("/"),
    })


@empresa_requerida
def subir(request):
    """Subir la cartera en la planilla del contrato, para la empresa sin sistema propio."""
    empresa = request.empresa
    respuesta = None
    form = SubirCarteraForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        corte = form.cleaned_data["fecha_corte"]
        lote_id = form.cleaned_data["lote_id_externo"].strip() or _proximo_lote(empresa, corte)
        try:
            cartera = planilla.leer(form.cleaned_data["archivo"].read(), lote_id, corte.isoformat(), empresa.tax_id)
            respuesta = recibir_cartera(empresa, cartera, source=Batch.Source.FILE)
        except CarteraInvalida as fallo:
            form.add_error("archivo" if fallo.codigo == "csv_invalido" else None, fallo.mensaje)
    return render(request, "portal/subir.html", {
        "activo": "subir", "empresa": empresa, "form": form, "respuesta": respuesta,
    })


def _proximo_lote(empresa, corte):
    """CSV-2026-09-30-1, -2, ...: el primero libre para esa fecha."""
    base = f"CSV-{corte.isoformat()}-"
    usados = set(Batch.objects.filter(creditor=empresa, external_id__startswith=base)
                 .values_list("external_id", flat=True))
    n = 1
    while f"{base}{n}" in usados:
        n += 1
    return f"{base}{n}"


@empresa_requerida
def datos(request):
    """
    Los datos de la empresa, sus contactos y lo que autoriza condonar de la
    mora. Si cambia ese maximo, DataBridge se entera al instante: desde ese
    momento ninguna campana ofrece mas que eso.
    """
    empresa = request.empresa
    antes = empresa.max_mora_discount
    form = DescuentoMaximoForm(request.POST or None, instance=empresa)
    if request.method == "POST" and form.is_valid():
        form.save()
        if empresa.max_mora_discount == antes:
            messages.success(request, "Guardado.")
        else:
            avisado = sincronizar_mandato(empresa)
            if avisado is True:
                messages.success(request, "Guardado. DataBridge ya lo sabe: desde ahora ninguna campaña ofrece más que eso.")
            elif avisado is None:
                messages.success(request, "Guardado. DataBridge lo recibe con su primera cartera.")
            else:
                messages.warning(request, "Guardado, pero DataBridge no respondió: se le vuelve a informar con su "
                                          "próxima cartera.")
        return redirect("portal:datos")
    return render(request, "portal/datos.html", {
        "activo": "datos", "empresa": empresa, "form_descuento": form,
        "contactos": empresa.contacts.all(),
    })


@empresa_requerida
def contacto(request, contacto_pk=None):
    """Agregar o editar un contacto de la propia empresa."""
    empresa = request.empresa
    existente = get_object_or_404(CreditorContact, pk=contacto_pk, creditor=empresa) if contacto_pk else None
    form = CreditorContactForm(request.POST or None, instance=existente)
    if request.method == "POST" and form.is_valid():
        nuevo = form.save(commit=False)
        nuevo.creditor = empresa
        nuevo.save()
        messages.success(request, f"{nuevo.full_name} quedó guardado.")
        return redirect("portal:datos")
    return render(request, "portal/contacto.html", {
        "activo": "datos", "empresa": empresa, "form": form, "contacto": existente,
    })


@empresa_requerida
@require_POST
def contacto_eliminar(request, contacto_pk):
    """Quita un contacto. El propio no: sin el, nadie podria entrar."""
    contacto = get_object_or_404(CreditorContact, pk=contacto_pk, creditor=request.empresa)
    if contacto.pk == request.contacto.pk:
        messages.error(request, "No puede eliminar su propio contacto.")
    else:
        contacto.delete()
        messages.success(request, f"{contacto.full_name} fue eliminado.")
    return redirect("portal:datos")

