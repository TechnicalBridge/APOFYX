"""Rutas raiz del proyecto."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("assistant.urls")),
    path("api/", include("integracion.urls")),
    path("panel/", include("crm.panel_urls")),
    path("", include("crm.urls")),
]
