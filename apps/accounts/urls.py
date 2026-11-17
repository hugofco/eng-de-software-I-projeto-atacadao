from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("entrar/", views.EntrarView.as_view(), name="login"),
    path("sair/", LogoutView.as_view(), name="logout"),  # exige POST (Django ≥ 5)
    path("senha/", views.TrocarSenhaView.as_view(), name="trocar_senha"),
    path("funcionarios/", views.lista, name="lista"),
    path("funcionarios/novo/", views.novo, name="novo"),
    path("funcionarios/<int:pk>/editar/", views.editar, name="editar"),
    path("funcionarios/<int:pk>/status/", views.alterar_status, name="status"),
]
