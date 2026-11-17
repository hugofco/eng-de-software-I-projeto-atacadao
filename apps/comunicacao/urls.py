from django.urls import path

from . import views

app_name = "comunicacao"

urlpatterns = [
    path("enviar/", views.enviar, name="enviar"),
    path("meus/", views.meus_comunicados, name="meus"),
    path("mensagem/", views.nova_mensagem, name="nova_mensagem"),
    path("caixa/", views.caixa_de_entrada, name="caixa"),
    path("caixa/<int:pk>/lida/", views.marcar_lida, name="lida"),
]
