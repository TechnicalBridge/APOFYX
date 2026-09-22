"""Panel de administracion de clientes. Requiere sesion iniciada."""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import panel_views

app_name = "panel"

urlpatterns = [
    path("entrar/", auth_views.LoginView.as_view(
        template_name="panel/login.html", redirect_authenticated_user=True,
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

    path("leads/", panel_views.leads, name="leads"),
]
