"""Roteamento raiz: cada módulo expõe suas próprias URLs (namespace por app)."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("tarefas/", include("apps.tarefas.urls")),
    path("escalas/", include("apps.escalas.urls")),
    path("ponto/", include("apps.ponto.urls")),
    path("comunicacao/", include("apps.comunicacao.urls")),
]
