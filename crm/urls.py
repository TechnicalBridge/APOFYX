"""Sitio publico de apofyx.cl."""

from django.urls import path

from . import views

app_name = "site"

urlpatterns = [
    path("", views.home, name="home"),
    path("contacto/", views.contacto, name="contacto"),
    path("gracias/", views.gracias, name="gracias"),
]
