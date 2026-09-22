"""Rutas del contrato de integracion. La version va en la ruta: /api/v1/."""

from django.urls import path

from . import views

app_name = "integracion"

urlpatterns = [
    path("v1/carteras", views.carteras, name="carteras"),
]
