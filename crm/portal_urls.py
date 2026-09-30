"""Portal de empresas: el acceso de las empresas cliente. Sesion de un contacto con el acceso aprobado."""

from django.urls import path

from . import portal_views

app_name = "portal"

urlpatterns = [
    path("registro/", portal_views.registro, name="registro"),
    path("entrar/", portal_views.Entrar.as_view(), name="entrar"),
    path("salir/", portal_views.Salir.as_view(), name="salir"),

    path("", portal_views.inicio, name="inicio"),
    path("conexion/", portal_views.conexion, name="conexion"),
    path("subir/", portal_views.subir, name="subir"),
    path("datos/", portal_views.datos, name="datos"),
    path("datos/contactos/nuevo/", portal_views.contacto, name="contacto_nuevo"),
    path("datos/contactos/<int:contacto_pk>/", portal_views.contacto, name="contacto_editar"),
    path("datos/contactos/<int:contacto_pk>/eliminar/", portal_views.contacto_eliminar, name="contacto_eliminar"),
]
