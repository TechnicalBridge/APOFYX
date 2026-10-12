"""Panel del personal de APOFYX. Requiere una sesion del personal (is_staff)."""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import panel_views

app_name = "panel"

urlpatterns = [
    #  Sin redirect_authenticated_user: una cuenta de empresa con sesion que
    #  llegara aca rebotaria para siempre entre el login y el panel.
    path("entrar/", auth_views.LoginView.as_view(
        template_name="panel/login.html", authentication_form=panel_views.EntrarPersonalForm,
    ), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),

    path("", panel_views.dashboard, name="dashboard"),

    path("clientes/", panel_views.clientes, name="clientes"),
    path("clientes/nuevo/", panel_views.cliente_nuevo, name="cliente_nuevo"),
    path("clientes/<int:pk>/", panel_views.cliente_detalle, name="cliente_detalle"),
    path("clientes/<int:pk>/editar/", panel_views.cliente_editar, name="cliente_editar"),
    path("clientes/<int:pk>/estado/", panel_views.cliente_estado, name="cliente_estado"),

    path("clientes/<int:pk>/contactos/nuevo/",
         panel_views.contacto_nuevo, name="contacto_nuevo"),
    path("clientes/<int:pk>/contactos/<int:contacto_pk>/editar/",
         panel_views.contacto_editar, name="contacto_editar"),
    path("clientes/<int:pk>/contactos/<int:contacto_pk>/eliminar/",
         panel_views.contacto_eliminar, name="contacto_eliminar"),
    path("clientes/<int:pk>/contactos/<int:contacto_pk>/aprobar/",
         panel_views.acceso_aprobar, name="acceso_aprobar"),
    path("clientes/<int:pk>/contactos/<int:contacto_pk>/revocar/",
         panel_views.acceso_revocar, name="acceso_revocar"),

    path("clientes/<int:pk>/campanas/nueva/", panel_views.campana_nueva, name="campana_nueva"),
    path("clientes/<int:pk>/campanas/<int:campana_pk>/estado/",
         panel_views.campana_estado, name="campana_estado"),
    path("clientes/<int:pk>/campanas/<int:campana_pk>/descuento/",
         panel_views.campana_descuento, name="campana_descuento"),
    path("clientes/<int:pk>/entregas/asignar/", panel_views.entregas_asignar, name="entregas_asignar"),

    path("plataforma/", panel_views.plataforma, name="plataforma"),

    path("leads/", panel_views.leads, name="leads"),
]
