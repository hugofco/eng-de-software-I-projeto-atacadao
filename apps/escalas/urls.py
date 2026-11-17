from django.urls import path

from . import views

app_name = "escalas"

urlpatterns = [
    path("", views.visao_geral, name="visao_geral"),
    path("funcionario/<int:pk>/", views.editar, name="editar"),
    path("minha/", views.minha, name="minha"),
    path("ocorrencias/", views.ocorrencias, name="ocorrencias"),
    path("remanejar/", views.remanejar, name="remanejar"),
]
